# dB-based variant of solver_server.py — runs on port 5051
import math
import threading
import time
from math import ceil
from collections import deque, Counter
from flask import Flask, request, jsonify
from flask_cors import CORS
from z3 import Int, And, Or, Not, Implies, Sum, If, Solver, Optimize, Bool, sat, unknown

app = Flask(__name__)
CORS(app)

# Shared by both phases' Z3 timeout and by /progress's elapsed/max display,
# so the two can never drift apart.
SOLVE_TIMEOUT_MS = 240000

# Z3's default Context is process-global and not thread-safe. Two overlapping
# requests (e.g. a double-click on "Run Solver" before the button disables)
# can both call into Z3 at once and corrupt its internal AST state, crashing
# with nondeterministic errors (access violations, "unreachable", "ast is not
# an expression"). This lock serializes all Z3 access so that can't happen.
_solve_lock = threading.Lock()

# Progress reporting for the frontend: /solve blocks for the whole solve, so a
# separate /progress GET (served on another thread — see threaded=True below)
# lets the UI poll what T the solver is currently on. Plain dict + lock rather
# than anything fancier since there's only ever one solve in flight at a time.
# started_at is a time.monotonic() timestamp for the current check() call, used
# to compute elapsed time on demand in the /progress route.
_progress_lock = threading.Lock()
_progress = {"phase": None, "T": None, "T_min": None, "T_max": None, "started_at": None}


def _set_progress(**kwargs):
    with _progress_lock:
        _progress.update(kwargs)


def _clear_progress():
    with _progress_lock:
        _progress.update({"phase": None, "T": None, "T_min": None, "T_max": None, "started_at": None})


SCALE = 100  # multiply all dB values by 100 and round to int for Z3 integer arithmetic


def dB_increase(baseline_val, n, aircraft_dB):
    """dB increase at a station with baseline_val ambient, n aircraft at aircraft_dB each."""
    if n == 0:
        return 0.0
    combined = 10 * math.log10(10 ** (baseline_val / 10) + n * 10 ** (aircraft_dB / 10))
    return combined - baseline_val


def build_scaled_table(M, N, baseline, aircraft_dB):
    """
    scaled_table[m][n] = round(dB_increase(baseline[m], n, aircraft_dB) * SCALE)
    Covers n = 0..N (maximum possible count at any station is N aircraft total).
    """
    return [
        [round(dB_increase(baseline[m], n, aircraft_dB) * SCALE) for n in range(N + 1)]
        for m in range(M)
    ]


def make_dB_expr(count_expr, m, scaled_table, n_max):
    """
    Returns a Z3 ArithRef: the scaled dB increase at station m given count_expr aircraft.
    Uses an If-chain over the counts 0..n_max.
    count_expr is a Z3 ArithRef (integer aircraft count at station m at some timestep).

    Callers pass n_max = D_count[m] rather than the global maximum count: the D cap
    already forces count_expr <= D_count[m], so higher branches are unreachable and
    only lengthen the chain.
    """
    expr = scaled_table[m][0]   # n=0 → 0 increase
    for n in range(1, n_max + 1):
        expr = If(count_expr == n, scaled_table[m][n], expr)
    return expr


def _active_output_matrices(paths, start_positions, end_positions, N, M, T, baseline, aircraft_dB,
                            multipliers=None):
    """Build count and dB matrices for output using the active-noise window:
    first move timestep through first arrival — matches the Z3 active[i][t] =
    moved[i][t] AND NOT arrived[i][t-1] definition exactly (moved[] flips true
    at t_fm, arrived[] flips true at t_arr, so active is true for t in [t_fm, t_arr]).
    multipliers[i] scales how many virtual aircraft aircraft i represents in the output."""
    mult = multipliers if multipliers is not None else [1] * N
    count = [[0] * T for _ in range(M)]
    for i in range(N):
        s0, e0 = start_positions[i], end_positions[i]
        if s0 == e0:
            continue
        p = paths[i]
        t_fm = next((t for t in range(T) if p[t] != s0), None)
        if t_fm is None:
            continue
        t_arr = next((t for t in range(T) if p[t] == e0), T - 1)
        for t in range(t_fm, t_arr + 1):
            count[p[t] - 1][t] += mult[i]
    noise = [
        [dB_increase(baseline[m], count[m][t], aircraft_dB) for t in range(T)]
        for m in range(M)
    ]
    return count, noise


def min_moves(adjacency, src, dst, M):
    """BFS: minimum moves from src to dst (1-indexed). Returns inf if unreachable."""
    if src == dst:
        return 0
    visited = [False] * (M + 1)
    visited[src] = True
    queue = deque([(src, 0)])
    while queue:
        node, moves = queue.popleft()
        for nb in range(1, M + 1):
            if nb == node:
                continue
            if adjacency[node - 1][nb - 1] == 1 and not visited[nb]:
                if nb == dst:
                    return moves + 1
                visited[nb] = True
                queue.append((nb, moves + 1))
    return float('inf')


def _compute_d_counts(M, N, D_scaled, scaled_table):
    """Max active aircraft count per station satisfying the dB-increase cap D
    (baseline-independent — D bounds the aircraft-caused increase, not the total level)."""
    result = []
    for m in range(M):
        max_n = 0
        for n in range(1, N + 1):
            if scaled_table[m][n] <= D_scaled:
                max_n = n
            else:
                break
        result.append(max_n)
    return result


def _add_noise_constraints(solver, cnt_vars, dB_exprs, M, D_count, U_scaled, tag):
    """
    Add the D cap and the U disparity constraint for one timestep.

    D is enforced on counts: dB increase is monotone in the aircraft count, so
    bounding the count at D_count[m] is exactly equivalent to bounding the increase
    at D, and costs M constraints.

    U was previously a table over every ordered station pair and every count value —
    O(M^2 * D_count) Implies per timestep, which accounted for roughly 95% of all
    constraints in the model and was why 5x5-sized problems timed out. It is replaced
    here by a max/min encoding, using the identity

        |dB(m1) - dB(m2)| <= U  for every pair   <=>   max(dB) - min(dB) <= U

    so two auxiliary integers and 2M+1 constraints say the same thing. This is sound
    and complete: dbmax is forced at or above the true maximum and dbmin at or below
    the true minimum, so bounding their difference bounds the true spread; conversely
    any assignment whose true spread fits within U is satisfiable by pinning the two
    auxiliaries to the actual extremes.

    (The earlier note that make_dB_expr causes O(N^2) case expansion referred to
    subtracting two If-chains for every station pair. Nothing here does that: each
    dB expression appears in exactly two comparisons and never against another chain.)

    cnt_vars[m] must be simple Z3 Int variables (not complex Sum expressions).
    dB_exprs[m] is the scaled dB increase at station m implied by cnt_vars[m].
    tag disambiguates the auxiliary variable names across timesteps and phases.
    """
    for m in range(M):
        solver.add(And(0 <= cnt_vars[m], cnt_vars[m] <= D_count[m]))

    if M < 2:
        return  # disparity is vacuous with a single station

    dbmax = Int(f"dbmax_{tag}")
    dbmin = Int(f"dbmin_{tag}")
    for m in range(M):
        solver.add(dbmax >= dB_exprs[m])
        solver.add(dbmin <= dB_exprs[m])
    solver.add(dbmax - dbmin <= U_scaled)


def find_min_T(N, M, D, U, adjacency, start_positions, end_positions, baseline, aircraft_dB,
               multipliers=None):
    scaled_table = build_scaled_table(M, N, baseline, aircraft_dB)
    D_scaled = round(D * SCALE)
    U_scaled = round(U * SCALE)

    # Per-aircraft multipliers: D/U hard constraints must be checked against the
    # same weighted counts used for the displayed noise matrix, or the shown
    # dB levels can exceed D/U even though Z3's own (unweighted) constraints
    # were satisfied.
    int_mult = [max(1, round(m)) for m in multipliers] if multipliers else [1] * N
    max_weighted_count = sum(int_mult)
    scaled_table_w = build_scaled_table(M, max_weighted_count, baseline, aircraft_dB)

    # ── Algebraic pre-checks (exact or O(M²), no Z3 needed) ─────────────────

    # D is an absolute dB-INCREASE cap: dB_increase[m] ≤ D at all times, independent
    # of that station's ambient baseline. (Baseline is never compared against D —
    # a station with 0 aircraft has 0 increase and can never violate D on its own.)

    # Pigeonhole: some station must hold ≥⌈N/M⌉ aircraft at every timestep.
    # Best case: the station whose dB increase for ⌈N/M⌉ aircraft is lowest
    # (this is baseline-dependent — a louder station's added aircraft noise is
    # masked more by its own ambient level, so it can yield a *lower* increase).
    # If even that exceeds D, no distribution can satisfy the cap.
    min_forced_count = ceil(N / M)
    best_m = min(range(M), key=lambda m: scaled_table[m][min_forced_count])
    if scaled_table[best_m][min_forced_count] > D_scaled:
        level = scaled_table[best_m][min_forced_count] / SCALE
        return {
            "status": "unsat", "reason": "noise_cap",
            "detail": (
                f"Even distributing {N} aircraft across {M} stations forces ≥{min_forced_count} "
                f"at some station; even the most tolerant station "
                f"(baseline {baseline[best_m]:.1f} dBA) would see a {level:.1f} dB increase, "
                f"exceeding D={D} dB"
            )
        }

    # Start-position D check only: t=0 aircraft are parked (active[i][0] = False always),
    # so they produce zero noise and can never violate U. The solver can also delay departure
    # to stagger active windows, so a U check on start positions would be overly strict.
    start_counts = Counter(start_positions)
    start_dB = [scaled_table[m][start_counts.get(m + 1, 0)] for m in range(M)]
    for m, inc_scaled in enumerate(start_dB):
        if inc_scaled > D_scaled:
            station = m + 1
            level = inc_scaled / SCALE
            return {
                "status": "unsat", "reason": "start_conflict",
                "detail": (
                    f"Station {station} has {start_counts[station]} aircraft at t=0, "
                    f"a {level:.1f} dB increase which exceeds D={D} dB"
                )
            }

    # End-position D + U check: final-timestep positions are also fixed.
    end_counts = Counter(end_positions)
    end_dB = [scaled_table[m][end_counts.get(m + 1, 0)] for m in range(M)]
    for m, inc_scaled in enumerate(end_dB):
        if inc_scaled > D_scaled:
            station = m + 1
            level = inc_scaled / SCALE
            return {
                "status": "unsat", "reason": "end_conflict",
                "detail": (
                    f"Station {station} has {end_counts[station]} aircraft at their final position, "
                    f"a {level:.1f} dB increase which exceeds D={D} dB"
                )
            }
    # End-position U check removed: aircraft that arrive before T-1 are already silent
    # (ha[i][T-2]=True → active[i][T-1]=False), so assuming all end positions are
    # simultaneously active overstates the noise and produces false unsat rejections.

    # BFS reachability per aircraft
    individual_mins = [
        min_moves(adjacency, start_positions[i], end_positions[i], M)
        for i in range(N)
    ]
    if any(m == float('inf') for m in individual_mins):
        return {
            "status": "unsat", "reason": "unreachable",
            "detail": "One or more aircraft cannot reach their destination via the given adjacency"
        }

    T_lower = max(2, max(individual_mins) + 1)

    def valid_next(src_1indexed):
        s0 = src_1indexed - 1
        return [dst + 1 for dst in range(M) if adjacency[s0][dst] == 1]

    # Precompute the count-based D table now (it only depends on M/D/baseline, not
    # on T) so max_d_count is known before sizing the T search budget below.
    D_count = _compute_d_counts(M, max_weighted_count, D_scaled, scaled_table_w)
    max_d_count = max(D_count) if D_count else 0

    # T search budget: sized from the same constraint-volume metric that guards
    # against Z3 blowing up. A flat budget crashed Z3 with an out-of-memory error
    # for large N (e.g. N=30, M=16 reached ~246k constraints at T_hard_cap=32 and
    # OOM'd), so the budget must shrink for problems where each extra timestep is
    # expensive, while still giving small problems plenty of room to search.
    #
    # Per timestep the model now emits O(M * max_d_count) If-chain nodes for the dB
    # expressions plus O(M * N) terms for the weighted count sums. It used to emit
    # O(M^2 * max_d_count) Implies for the pairwise U table, so this metric dropped
    # by roughly a factor of M when that table was replaced by the max/min encoding
    # in _add_noise_constraints — which is why problems that used to be rejected as
    # noise_domain_too_large now fit comfortably.
    #
    # The volume ceiling was lowered from 80_000 to 40_000 alongside that change.
    # The old number was tuned against the old (M^2) cost model, and keeping it with
    # the new metric would have admitted roughly 628 weighted aircraft-units at
    # M=25 — far beyond anything that has actually been solved. 40_000 still admits
    # ~308 units against the 25 the old formula allowed, so the workshop gains the
    # headroom it needs while the accepted range stays inside tested territory.
    SAFE_CONSTRAINT_VOLUME = 40_000
    per_timestep_cost = max(1, M * (max_d_count + N))
    T_hard_cap_by_memory = SAFE_CONSTRAINT_VOLUME // per_timestep_cost
    if T_hard_cap_by_memory < T_lower:
        return {
            "status": "unsat", "reason": "noise_domain_too_large",
            "detail": (
                f"Noise-constraint search space too large to solve reliably even at the "
                f"minimum feasible T={T_lower} (stations can hold up to {max_d_count} "
                f"weighted aircraft-units under the current D). This is usually caused by "
                f"a generous D combined with large N or aircraft multipliers. Lower D, "
                f"reduce aircraft multipliers, or reduce N/M to continue."
            )
        }
    T_hard_cap = min(T_lower + 40, max(T_lower + 3, T_hard_cap_by_memory))

    # Build permanent base state up to T_lower (Suggestion 3: encode once)
    L = [[Int(f"L_{i}_{t}") for t in range(T_lower)] for i in range(N)]
    s = Solver()
    s.set("timeout", SOLVE_TIMEOUT_MS)  # yields unknown instead of crashing

    # Bounds
    for i in range(N):
        for t in range(T_lower):
            s.add(And(1 <= L[i][t], L[i][t] <= M))

    # Start pins (T-independent — always hard)
    s.add([L[i][0] == start_positions[i] for i in range(N)])

    # Movement constraints t = 0 … T_lower-2
    for i in range(N):
        for t in range(T_lower - 1):
            for src in range(1, M + 1):
                dsts = valid_next(src)
                s.add(Implies(L[i][t] == src, Or([L[i][t + 1] == dst for dst in dsts])))

    # Active-noise tracking booleans
    # moved[i][t]:   aircraft i has left its start station by time t
    # arrived[i][t]: aircraft i has reached its end station by time t
    # active[i][t]:  aircraft i contributes noise at t (moved and not yet arrived before t)
    moved   = [[Bool(f"mv_{i}_{t}")  for t in range(T_lower)] for i in range(N)]
    arrived = [[Bool(f"ar_{i}_{t}")  for t in range(T_lower)] for i in range(N)]
    active  = [[Bool(f"act_{i}_{t}") for t in range(T_lower)] for i in range(N)]
    for i in range(N):
        s.add(moved[i][0]   == False)
        s.add(arrived[i][0] == (start_positions[i] == end_positions[i]))
        s.add(active[i][0]  == False)
        for t in range(1, T_lower):
            s.add(moved[i][t]   == Or(moved[i][t-1],   Not(L[i][t] == start_positions[i])))
            s.add(arrived[i][t] == Or(arrived[i][t-1], L[i][t] == end_positions[i]))
            s.add(active[i][t]  == And(moved[i][t], Not(arrived[i][t-1])))

    # Noise cap + global disparity for t = 0 … T_lower-1
    # C_by_t[t][m] = weighted active aircraft count at station m at time t
    # (D_count/max_d_count were already computed above, before T_hard_cap sizing)
    C_by_t = []
    for t in range(T_lower):
        C_t = [Sum([If(And(L[i][t] == m + 1, active[i][t]), int_mult[i], 0) for i in range(N)]) for m in range(M)]
        C_by_t.append(C_t)
        cnt_t = [Int(f"cnt_{m}_{t}") for m in range(M)]
        for m in range(M):
            s.add(cnt_t[m] == C_t[m])
        dB_t = [make_dB_expr(cnt_t[m], m, scaled_table_w, D_count[m]) for m in range(M)]
        _add_noise_constraints(s, cnt_t, dB_t, M, D_count, U_scaled, f"p1_{t}")

    T_current = T_lower

    for _ in range(T_lower, T_hard_cap + 1):
        _set_progress(phase="phase1", T=T_current, T_min=T_lower, T_max=T_hard_cap, started_at=time.monotonic())

        # Assumption booleans — same names reused safely because the Implies
        # constraints referencing them are pushed/popped each iteration.
        end_asms = [Bool(f"end_{i}") for i in range(N)]

        s.push()
        for i in range(N):
            s.add(Implies(end_asms[i], L[i][T_current - 1] == end_positions[i]))

        result = s.check(*end_asms)

        if str(result) == "unknown":
            s.pop()
            return {
                "status": "unsat", "reason": "timeout",
                "detail": (
                    f"Solver timed out at T={T_current} — problem may be too large "
                    f"(N={N}, M={M}). Try reducing N or M, or relaxing D/U."
                )
            }

        if result == sat:
            model = s.model()
            paths = [
                [model[L[i][t]].as_long() for t in range(T_current)]
                for i in range(N)
            ]
            count_matrix, noise_matrix_dB = _active_output_matrices(
                paths, start_positions, end_positions, N, M, T_current, baseline, aircraft_dB,
                multipliers=multipliers
            )
            s.pop()
            return {"status": "sat", "T": T_current, "paths": paths,
                    "countMatrix": count_matrix, "noiseMatrix": noise_matrix_dB}

        # ── Suggestion 2: unsat-core early exit ─────────────────────────────
        # If no endpoint assumption appears in the core, the infeasibility is
        # structural (noise/movement constraints alone conflict) and increasing
        # T will never help — stop immediately.
        core = s.unsat_core()
        s.pop()

        if not any(a in core for a in end_asms):
            return {
                "status": "unsat", "reason": "structural",
                "detail": "Constraints are unsatisfiable regardless of T — try relaxing D or U"
            }

        if T_current >= T_hard_cap:
            break

        # ── Suggestion 3: extend base by exactly one timestep ───────────────
        new_t = T_current  # 0-indexed new final timestep

        for i in range(N):
            L[i].append(Int(f"L_{i}_{new_t}"))
            moved[i].append(Bool(f"mv_{i}_{new_t}"))
            arrived[i].append(Bool(f"ar_{i}_{new_t}"))
            active[i].append(Bool(f"act_{i}_{new_t}"))

        s.add([And(1 <= L[i][new_t], L[i][new_t] <= M) for i in range(N)])

        for i in range(N):
            for src in range(1, M + 1):
                dsts = valid_next(src)
                s.add(Implies(L[i][new_t - 1] == src, Or([L[i][new_t] == dst for dst in dsts])))

        for i in range(N):
            s.add(moved[i][new_t]   == Or(moved[i][new_t-1],   Not(L[i][new_t] == start_positions[i])))
            s.add(arrived[i][new_t] == Or(arrived[i][new_t-1], L[i][new_t] == end_positions[i]))
            s.add(active[i][new_t]  == And(moved[i][new_t], Not(arrived[i][new_t-1])))

        C_new = [Sum([If(And(L[i][new_t] == m + 1, active[i][new_t]), int_mult[i], 0) for i in range(N)]) for m in range(M)]
        C_by_t.append(C_new)
        cnt_new = [Int(f"cnt_{m}_{new_t}") for m in range(M)]
        for m in range(M):
            s.add(cnt_new[m] == C_new[m])
        dB_new = [make_dB_expr(cnt_new[m], m, scaled_table_w, D_count[m]) for m in range(M)]
        _add_noise_constraints(s, cnt_new, dB_new, M, D_count, U_scaled, f"p1_{new_t}")

        T_current += 1

    return {"status": "unsat", "reason": "timeout", "detail": f"No solution found within T={T_hard_cap} — try reducing N or M, or relaxing D/U"}


def optimize_objectives(N, T, M, D, U, adjacency, start_positions, end_positions,
                        optimize_util, optimize_prior, optimize_prop,
                        protected_stations, proportional_stations,
                        w_util, w_prior, w_prop,
                        soft_T, w_time,
                        prop_alloc,
                        station_transit_weights,
                        util_noise_mode,
                        aircraft_multipliers,
                        baseline, aircraft_dB):
    """Phase-2 optimizer: rebuild all constraints in a fresh Optimize instance and
    minimize a weighted combination of transit time and protected-station noise (dB).

    NOTE: z3.Optimize is slower than z3.Solver. For large N, T, or M this phase
    may take several seconds. T is fixed to the value found in phase 1.
    """
    _set_progress(phase="phase2", T=T, T_min=None, T_max=None, started_at=time.monotonic())

    D_scaled = round(D * SCALE)
    U_scaled = round(U * SCALE)

    # Per-aircraft multipliers: how many virtual aircraft each real aircraft represents.
    # D/U hard constraints are checked against these same weighted counts (see below)
    # so the displayed noise matrix can never exceed what's actually enforced.
    int_mult = [max(1, round(m)) for m in aircraft_multipliers] if aircraft_multipliers else [1] * N
    max_weighted_count = sum(int_mult)
    # Weighted dB table covers 0..max_weighted_count aircraft
    scaled_table_w = build_scaled_table(M, max_weighted_count, baseline, aircraft_dB)

    # ── Metric normalization ──────────────────────────────────────────────────
    # All metrics are divided by their theoretical maximums so that weights
    # operate on a comparable scale regardless of N, T, M, D.
    #
    # Transit and T-penalty: count-based, unchanged from the count-based solver.
    # Prioritarian and proportional: dB-based; bounded by all-N-aircraft case
    # at the loudest station.
    # Station-weighted transit: scale floats to integers (0.01 precision).
    W_SCALE = 100
    if station_transit_weights is not None:
        int_tw = [round(w * W_SCALE) for w in station_transit_weights]
        max_tw = max(int_tw) if int_tw else W_SCALE
    else:
        int_tw = None
        max_tw = W_SCALE  # uniform weight=1 → scaled = 100
    max_transit   = sum(int_mult) * (T - 1) * max(1, max_tw)
    max_T_penalty = N * (T - 1)

    # Use scaled (integer) units for dB normalization bounds so all objective
    # terms live in the same numeric range as the Z3 dB expressions (×SCALE).
    # Mixing unscaled dB bounds with scaled Z3 expressions would make the dB
    # objectives SCALE× heavier than the count-based utilitarian term.
    max_dB_scaled_per_station = max(scaled_table_w[m][max_weighted_count] for m in range(M))
    max_protected_dB    = len(protected_stations)    * T * max_dB_scaled_per_station
    max_proportional_dB = len(proportional_stations) * T * max_dB_scaled_per_station
    # When station-weighted, each term in total_util_noise is additionally scaled by
    # int_tw[m] (see below), so the normalization bound needs the same max_tw factor
    # the transit-cost path already applies to max_transit.
    max_util_noise_dB   = M * T * max_dB_scaled_per_station * (max(1, max_tw) if int_tw is not None else 1)

    # After normalization, all coefficients are dimensionless and comparable,
    # so w_util = w_prior = w_prop = w_time = 1.0 gives genuinely equal weighting.
    if optimize_util:
        if util_noise_mode:
            eff_w_util = (w_util / max_util_noise_dB) if max_util_noise_dB > 0 else 0.0
        else:
            eff_w_util = (w_util / max_transit)       if max_transit       > 0 else 0.0
    else:
        eff_w_util = 0.0
    eff_w_prior = (w_prior / max_protected_dB)    if (optimize_prior and max_protected_dB    > 0) else 0.0
    eff_w_prop  = (w_prop  / max_proportional_dB) if (optimize_prop  and max_proportional_dB > 0) else 0.0
    eff_w_time  = (w_time  / max_T_penalty)       if (soft_T         and max_T_penalty        > 0) else 0.0

    def valid_next(src_1indexed):
        s0 = src_1indexed - 1
        return [dst + 1 for dst in range(M) if adjacency[s0][dst] == 1]

    # Global disparity: all station pairs, not just adjacent ones
    all_pairs = [(m1, m2) for m1 in range(M) for m2 in range(m1 + 1, M)]

    opt = Optimize()
    opt.set("timeout", SOLVE_TIMEOUT_MS)  # cap; without this Optimize() can hang indefinitely

    # Location variables — "o_" prefix avoids name clashes with phase-1 variables
    L = [[Int(f"o_L_{i}_{t}") for t in range(T)] for i in range(N)]

    # Bounds
    for i in range(N):
        for t in range(T):
            opt.add(And(1 <= L[i][t], L[i][t] <= M))

    # Start and end pins
    for i in range(N):
        opt.add(L[i][0] == start_positions[i])
        opt.add(L[i][T - 1] == end_positions[i])

    # Movement constraints
    for i in range(N):
        for t in range(T - 1):
            for src in range(1, M + 1):
                dsts = valid_next(src)
                opt.add(Implies(L[i][t] == src, Or([L[i][t + 1] == dst for dst in dsts])))

    # Active-noise tracking booleans (mirrors find_min_T logic)
    ha     = [[Bool(f"o_ha_{i}_{t}")  for t in range(T)] for i in range(N)]
    moved  = [[Bool(f"o_mv_{i}_{t}")  for t in range(T)] for i in range(N)]
    active = [[Bool(f"o_act_{i}_{t}") for t in range(T)] for i in range(N)]
    for i in range(N):
        opt.add(ha[i][0]     == (L[i][0] == end_positions[i]))
        opt.add(moved[i][0]  == False)
        opt.add(active[i][0] == False)
        for t in range(1, T):
            opt.add(ha[i][t]     == Or(ha[i][t - 1],     L[i][t] == end_positions[i]))
            opt.add(moved[i][t]  == Or(moved[i][t - 1],  Not(L[i][t] == start_positions[i])))
            opt.add(active[i][t] == And(moved[i][t], Not(ha[i][t - 1])))

    # Noise cap and global disparity (counting only active aircraft).
    # Built from the weighted table so D/U hard constraints are checked against
    # the same weighted counts used for the displayed noise matrix below.
    D_count = _compute_d_counts(M, max_weighted_count, D_scaled, scaled_table_w)

    # Guard: a generous D combined with large aircraft multipliers can push D_count
    # close to max_weighted_count for every station. Per timestep the model emits
    # O(M * D_count) If-chain nodes plus O(M * N) count-sum terms; the old pairwise
    # U table made this O(M^2 * D_count), which crashed Z3 with an access violation
    # when the product got too large. The metric now reflects what is actually
    # emitted, and the ceiling is lowered from 150_000 to 75_000 to match — see the
    # note on SAFE_CONSTRAINT_VOLUME in find_min_T for why the old number would have
    # been far too permissive under the new cost model.
    max_d_count = max(D_count) if D_count else 0
    if T * M * (max_d_count + N) > 75_000:
        raise ValueError(
            f"Noise-constraint search space too large for phase-2 optimization "
            f"(stations can hold up to {max_d_count} weighted aircraft-units under "
            f"the current D). This is usually caused by a generous D combined with "
            f"large aircraft multipliers. Lower D, reduce aircraft multipliers, "
            f"reduce T_max, or reduce N/M to continue."
        )

    wdB_by_t = []
    for t in range(T):
        # Weighted-count variables drive both the D/U hard constraints and the
        # soft dB objectives/output, so displayed noise never exceeds what's enforced.
        WC_t = [Sum([If(And(L[i][t] == m + 1, active[i][t]), int_mult[i], 0) for i in range(N)]) for m in range(M)]
        wcnt_t = [Int(f"o_wcnt_{m}_{t}") for m in range(M)]
        for m in range(M):
            opt.add(wcnt_t[m] == WC_t[m])
        # These dB expressions were already needed for the soft objectives below, so
        # the U constraint now reuses them instead of building a separate pairwise
        # table — the disparity encoding costs 2M+1 constraints on top of zero new terms.
        wdB_exprs_t = [make_dB_expr(wcnt_t[m], m, scaled_table_w, D_count[m]) for m in range(M)]
        _add_noise_constraints(opt, wcnt_t, wdB_exprs_t, M, D_count, U_scaled, f"p2_{t}")
        wdB_by_t.append(wdB_exprs_t)

    # ── Build objective terms ─────────────────────────────────────────────────
    objective_terms = []

    # Declare result variables in outer scope so the result block can read them
    transit = None
    total_transit = None
    total_util_noise = None
    protected_noise_dB = None
    proportional_noise_dB = None

    # Sticky arrival: once an aircraft reaches its destination it must stay there.
    # Without this, in soft mode aircraft can drift away between arrival and T-1.
    if soft_T:
        for i in range(N):
            for t in range(T - 1):
                opt.add(Implies(ha[i][t], L[i][t + 1] == end_positions[i]))

    if eff_w_util > 0:
        if util_noise_mode:
            # Minimize weighted dB noise sum across all stations and timesteps.
            # Uses wdB_by_t (multiplier-scaled counts) so each aircraft's
            # virtual count affects the nonlinear dB lookup correctly.
            # Station-weighted transit cost (int_tw) applies here too, the same
            # way it scales the per-station cost in the transit-time branch below.
            if int_tw is not None:
                total_util_noise = Sum([wdB_by_t[t][m] * int_tw[m] for t in range(T) for m in range(M)])
            else:
                total_util_noise = Sum([wdB_by_t[t][m] for t in range(T) for m in range(M)])
            objective_terms.append(eff_w_util * total_util_noise)
        else:
            # hm[i][t]: aircraft i has changed location at least once in t'=1..t
            # it[i][t]: aircraft i is currently accumulating transit cost at time t
            hm = [[Bool(f"o_hm_{i}_{t}") for t in range(T)] for i in range(N)]
            it = [[Bool(f"o_it_{i}_{t}") for t in range(T)] for i in range(N)]

            for i in range(N):
                opt.add(hm[i][0] == False)
                opt.add(it[i][0] == False)
                for t in range(1, T):
                    opt.add(hm[i][t] == Or(hm[i][t - 1], L[i][t] != L[i][t - 1]))
                    # Arrival timestep IS counted — gate on t-1 arrival, not t
                    opt.add(it[i][t] == And(hm[i][t], Not(ha[i][t - 1])))

            if int_tw is not None:
                def _tw_expr(L_it, weights=int_tw):
                    e = weights[0]
                    for m in range(1, M):
                        e = If(L_it == m + 1, weights[m], e)
                    return e
                transit = [Sum([If(it[i][t], _tw_expr(L[i][t]) * int_mult[i], 0) for t in range(T)]) for i in range(N)]
            else:
                transit = [Sum([If(it[i][t], W_SCALE * int_mult[i], 0) for t in range(T)]) for i in range(N)]
            total_transit = Sum(transit)
            objective_terms.append(eff_w_util * total_transit)

    if eff_w_prior > 0:
        protected_noise_dB = Sum([
            wdB_by_t[t][p - 1]
            for p in protected_stations
            for t in range(T)
        ])
        objective_terms.append(eff_w_prior * protected_noise_dB)

    if eff_w_prop > 0:
        proportional_noise_dB = Sum([
            wdB_by_t[t][b - 1]
            for b in proportional_stations
            for t in range(T)
        ])
        objective_terms.append(-eff_w_prop * proportional_noise_dB)  # negative coefficient = maximize this term

    if eff_w_time > 0:
        # Arrival time proxy: counts pre-arrival timesteps per aircraft.
        # Minimizing this pulls aircraft toward earliest feasible arrival.
        # Sum(If(Not(ha[i][t]), 1, 0) for t in 0..T-1) equals the first timestep
        # ha[i][t] becomes True (arrival time). Max value per aircraft = T - 1.
        T_penalty = Sum([
            If(Not(ha[i][t]), 1, 0)
            for i in range(N)
            for t in range(T)
        ])
        objective_terms.append(eff_w_time * T_penalty)

    # ── Proportional allocation for benefits ──────────────────────────────────
    # Soft ordering: stations with aircraft activity (start/end) should bear more
    # noise than stations merely adjacent to them, which in turn should bear more
    # than all other stations.  Implemented as a penalty on ordering violations
    # across all timesteps, normalized to [0,1] like the other objectives.
    prop_alloc_sets = None
    if prop_alloc:
        active_set = set()
        for i in range(N):
            active_set.add(start_positions[i] - 1)
            active_set.add(end_positions[i] - 1)

        adjacent_set = set()
        for m in range(M):
            if m not in active_set:
                if any(adjacency[m][a] or adjacency[a][m] for a in active_set):
                    adjacent_set.add(m)

        none_set = set(range(M)) - active_set - adjacent_set

        # (hi, lo): hi should have >= dB increase than lo at every timestep
        order_pairs = (
            [(a, adj) for a in active_set for adj in adjacent_set] +
            [(a, n)   for a in active_set for n   in none_set]     +
            [(adj, n) for adj in adjacent_set for n in none_set]
        )

        if order_pairs:
            max_prop_alloc = max(1, len(order_pairs) * T * max_dB_scaled_per_station)
            violation = Sum([
                If(wdB_by_t[t][hi] < wdB_by_t[t][lo],
                   wdB_by_t[t][lo] - wdB_by_t[t][hi], 0)
                for (hi, lo) in order_pairs
                for t in range(T)
            ])
            objective_terms.append((1.0 / max_prop_alloc) * violation)

        prop_alloc_sets = {
            "active":   sorted(s + 1 for s in active_set),
            "adjacent": sorted(s + 1 for s in adjacent_set),
            "none":     sorted(s + 1 for s in none_set),
        }

    if objective_terms:
        opt.minimize(Sum(objective_terms))

    check_result = opt.check()
    if check_result != sat:
        # Distinguish a timed-out search (unknown — Z3 ran out of the SOLVE_TIMEOUT_MS
        # budget without an answer) from a genuine unsat (which "should not happen":
        # phase-1 already confirmed sat at this T, ignoring objectives/weights).
        # Callers must not treat this as a normal phase-1 fallback silently — the
        # caller is expected to surface why phase-2 didn't produce a weighted result.
        return {"status": "phase2_failed", "reason": "timeout" if check_result == unknown else "unsat_unexpected"}

    model = opt.model()
    paths = [
        [model[L[i][t]].as_long() for t in range(T)]
        for i in range(N)
    ]
    count_matrix, noise_matrix_dB = _active_output_matrices(
        paths, start_positions, end_positions, N, M, T, baseline, aircraft_dB,
        multipliers=int_mult
    )

    result = {"status": "sat", "T": T, "paths": paths,
              "countMatrix": count_matrix, "noiseMatrix": noise_matrix_dB}
    result["T_used"] = T

    if eff_w_util > 0:
        if util_noise_mode:
            raw_util_noise = model.evaluate(total_util_noise).as_long()
            result["totalUtilNoise"] = raw_util_noise / SCALE / W_SCALE if int_tw is not None else raw_util_noise / SCALE
        else:
            result["transitTimes"] = [model.evaluate(transit[i]).as_long() for i in range(N)]
            result["totalTransit"] = model.evaluate(total_transit).as_long()

    if eff_w_prior > 0:
        result["protectedNoise"]    = model.evaluate(protected_noise_dB).as_long() / SCALE
        result["protectedStations"] = protected_stations

    if eff_w_prop > 0:
        result["proportionalNoise"]    = model.evaluate(proportional_noise_dB).as_long() / SCALE
        result["proportionalStations"] = proportional_stations

    if prop_alloc_sets is not None:
        result["stationCategories"] = prop_alloc_sets

    return result


@app.route("/solve", methods=["POST"])
def solve():
    with _solve_lock:
        _clear_progress()
        try:
            return _solve_impl()
        finally:
            _clear_progress()


@app.route("/progress", methods=["GET"])
def progress():
    # Deliberately outside _solve_lock — this must respond immediately while
    # a solve is in flight on another thread (see threaded=True below).
    with _progress_lock:
        p = dict(_progress)
    started_at = p.pop("started_at", None)
    p["elapsed_s"] = round(time.monotonic() - started_at, 1) if started_at is not None else None
    p["timeout_s"] = SOLVE_TIMEOUT_MS / 1000
    return jsonify(p)


def _solve_impl():
    data = request.get_json(force=True)
    try:
        N            = int(data["N"])
        M            = int(data["M"])
        D            = float(data["D"])
        U            = float(data["U"])
        adjacency    = data["adjacency"]
        start_positions = data["startPositions"]
        end_positions   = data["endPositions"]
        aircraft_dB  = float(data["aircraftDB"])
    except (KeyError, TypeError, ValueError) as e:
        return jsonify({"error": f"Bad input: {e}"}), 400

    if N < 1:
        return jsonify({"error": "N must be >= 1"}), 400
    if M < 1:
        return jsonify({"error": "M must be >= 1"}), 400
    if D <= 0:
        return jsonify({"error": "D must be > 0"}), 400
    if U < 0:
        return jsonify({"error": "U must be >= 0"}), 400
    if aircraft_dB <= 0:
        return jsonify({"error": "aircraftDB must be > 0"}), 400

    if not isinstance(adjacency, list) or len(adjacency) != M or \
            any(not isinstance(row, list) or len(row) != M for row in adjacency):
        return jsonify({"error": f"adjacency must be an {M}×{M} matrix of 0/1 values"}), 400

    if not isinstance(start_positions, list) or len(start_positions) != N:
        return jsonify({"error": f"startPositions must be a list of N={N} integers"}), 400
    if not isinstance(end_positions, list) or len(end_positions) != N:
        return jsonify({"error": f"endPositions must be a list of N={N} integers"}), 400
    try:
        start_positions = [int(p) for p in start_positions]
        end_positions   = [int(p) for p in end_positions]
    except (TypeError, ValueError):
        return jsonify({"error": "startPositions and endPositions must contain integers"}), 400
    if any(p < 1 or p > M for p in start_positions):
        return jsonify({"error": f"startPositions values must be in [1, M={M}]"}), 400
    if any(p < 1 or p > M for p in end_positions):
        return jsonify({"error": f"endPositions values must be in [1, M={M}]"}), 400

    baseline = data.get("baseline")
    if not isinstance(baseline, list) or len(baseline) != M:
        return jsonify({"error": f"baseline must be a list of M={M} floats"}), 400
    try:
        baseline = [float(b) for b in baseline]
    except (TypeError, ValueError):
        return jsonify({"error": "baseline values must be numeric"}), 400

    optimize_util  = data.get("optimizeUtilitarian",  False)
    optimize_prior = data.get("optimizePrioritarian", False)
    optimize_prop  = data.get("optimizeProportional", False)
    if not isinstance(optimize_util,  bool): optimize_util  = False
    if not isinstance(optimize_prior, bool): optimize_prior = False
    if not isinstance(optimize_prop,  bool): optimize_prop  = False

    try:
        w_util  = float(data.get("weightUtilitarian",  1.0))
        w_prior = float(data.get("weightPrioritarian", 1.0))
        w_prop  = float(data.get("weightProportional", 1.0))
    except (TypeError, ValueError):
        w_util, w_prior, w_prop = 1.0, 1.0, 1.0
    if w_util  < 0: w_util  = 0.0
    if w_prior < 0: w_prior = 0.0
    if w_prop  < 0: w_prop  = 0.0

    protected_stations = data.get("protectedStations", [])
    if optimize_prior:
        if not isinstance(protected_stations, list) or len(protected_stations) == 0:
            return jsonify({"error": "protectedStations must be a non-empty list when optimizePrioritarian is true"}), 400
        try:
            protected_stations = [int(p) for p in protected_stations]
        except (TypeError, ValueError):
            return jsonify({"error": "protectedStations must be a list of integers"}), 400
        if any(p < 1 or p > M for p in protected_stations):
            return jsonify({"error": f"protectedStations must be between 1 and M={M}"}), 400

    proportional_stations = data.get("proportionalStations", [])
    if optimize_prop:
        if not isinstance(proportional_stations, list) or len(proportional_stations) == 0:
            return jsonify({"error": "proportionalStations must be a non-empty list when optimizeProportional is true"}), 400
        try:
            proportional_stations = [int(b) for b in proportional_stations]
        except (TypeError, ValueError):
            return jsonify({"error": "proportionalStations must be a list of integers"}), 400
        if any(b < 1 or b > M for b in proportional_stations):
            return jsonify({"error": f"proportionalStations must be between 1 and M={M}"}), 400

    hard_T = data.get("hardT", True)
    if not isinstance(hard_T, bool): hard_T = True
    soft_T = not hard_T

    if soft_T:
        no_loop = sorted({
            end_positions[i] for i in range(N)
            if adjacency[end_positions[i] - 1][end_positions[i] - 1] != 1
        })
        if no_loop:
            return jsonify({
                "error": (
                    f"Soft T mode requires self-loops at all destination stations; "
                    f"stations {no_loop} are missing self-loops in the adjacency matrix"
                )
            }), 400

    T_max = None
    if soft_T:
        raw_T_max = data.get("T_max", None)
        if raw_T_max is not None:
            try:
                T_max = int(raw_T_max)
            except (TypeError, ValueError):
                return jsonify({"error": "T_max must be an integer"}), 400
            if T_max < 2:
                return jsonify({"error": "T_max must be >= 2"}), 400
        # If T_max is still None here, it will be auto-computed after Phase 1

    try:
        w_time = float(data.get("weightTime", 1.0))
    except (TypeError, ValueError):
        w_time = 1.0
    if w_time < 0: w_time = 0.0

    aircraft_multipliers = None
    raw_mult = data.get("aircraftMultipliers")
    if raw_mult is not None:
        if not isinstance(raw_mult, list) or len(raw_mult) != N:
            return jsonify({"error": f"aircraftMultipliers must be a list of length N={N}"}), 400
        try:
            aircraft_multipliers = [float(v) for v in raw_mult]
        except (TypeError, ValueError):
            return jsonify({"error": "aircraftMultipliers values must be numeric"}), 400
        if any(v <= 0 for v in aircraft_multipliers):
            return jsonify({"error": "aircraftMultipliers values must be positive"}), 400

    try:
        result = find_min_T(N, M, D, U, adjacency, start_positions, end_positions, baseline, aircraft_dB,
                            multipliers=aircraft_multipliers)
    except OSError as e:
        return jsonify({
            "error": f"Z3 internal error during phase-1 solve (N={N} may be too large for the dB solver): {e}"
        }), 500
    except Exception as e:
        return jsonify({"error": f"Unexpected solver error: {e}"}), 500

    if soft_T:
        if result["status"] != "sat":
            return jsonify(result)

        T_lower = result["T"]

        if T_max is None:
            # Auto T_max: gives the optimizer at least as much extra room as the minimum T itself
            T_max = max(T_lower * 2, T_lower + 5)
        elif T_max < T_lower:
            return jsonify({
                "status": "unsat",
                "reason": "T_max_too_small",
                "detail": f"T_max={T_max} is smaller than the minimum feasible T={T_lower} — increase T_max or relax D/U"
            })

    prop_alloc = data.get("proportionalAllocation", False)
    if not isinstance(prop_alloc, bool): prop_alloc = False

    util_noise_mode = bool(data.get("utilNoiseMode", False))

    station_transit_weights = None
    if optimize_util:
        raw_stw = data.get("stationTransitWeights")
        if raw_stw is not None:
            if not isinstance(raw_stw, list) or len(raw_stw) != M:
                return jsonify({"error": f"stationTransitWeights must be a list of length M={M}"}), 400
            try:
                station_transit_weights = [float(w) for w in raw_stw]
            except (TypeError, ValueError):
                return jsonify({"error": "stationTransitWeights values must be numeric"}), 400
            if any(w < 0 for w in station_transit_weights):
                return jsonify({"error": "stationTransitWeights values must be non-negative"}), 400

    should_optimize = optimize_util or optimize_prior or optimize_prop or soft_T or prop_alloc
    if result["status"] != "sat" or not should_optimize:
        return jsonify(result)

    T_for_phase2 = result["T"] if hard_T else T_max

    overlap_warning = None
    if optimize_prior and optimize_prop:
        overlap = sorted(set(protected_stations) & set(proportional_stations))
        if overlap:
            overlap_warning = (
                f"protectedStations and proportionalStations overlap at stations {overlap}"
                " — solver will find weighted compromise"
            )

    try:
        opt_result = optimize_objectives(
            N, T_for_phase2, M, D, U, adjacency, start_positions, end_positions,
            optimize_util, optimize_prior, optimize_prop,
            protected_stations, proportional_stations,
            w_util, w_prior, w_prop,
            soft_T, w_time,
            prop_alloc,
            station_transit_weights,
            util_noise_mode,
            aircraft_multipliers,
            baseline, aircraft_dB
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except OSError as e:
        return jsonify({
            "error": f"Z3 internal error during phase-2 optimization (N={N} may be too large): {e}"
        }), 500
    except Exception as e:
        return jsonify({"error": f"Unexpected optimization error: {e}"}), 500

    if opt_result["status"] == "phase2_failed":
        # Fall back to phase-1's plain (unweighted, unoptimized) feasible result so
        # the user still gets a route — but flag it clearly: silently serving this
        # without a warning would make it look like the weighted optimization ran
        # and simply chose to ignore the weights/objectives, when actually it never
        # produced a result at all.
        if opt_result["reason"] == "timeout":
            detail = (
                f"Phase-2 optimization timed out (after {SOLVE_TIMEOUT_MS // 1000}s) at "
                f"T={T_for_phase2} without finding a weighted solution — showing the plain "
                f"feasible route instead, which does NOT reflect your weights or objectives. "
                f"Try tightening D/U, lowering T_max, reducing the station weight, or reducing "
                f"N/aircraft multipliers."
            )
        else:
            detail = (
                f"Phase-2 optimization unexpectedly found no solution at T={T_for_phase2} "
                f"despite phase-1 confirming feasibility — showing the plain feasible route "
                f"instead, which does NOT reflect your weights or objectives."
            )
        result["warning"] = f"{overlap_warning} · {detail}" if overlap_warning else detail
        return jsonify(result)
    opt_result["T_min"] = result["T"]
    if overlap_warning:
        opt_result["warning"] = overlap_warning
    return jsonify(opt_result)


if __name__ == "__main__":
    # threaded=True so GET /progress can be served while a POST /solve is in
    # flight. This is safe: /progress never touches Z3 or _solve_lock, only
    # the separate lightweight _progress_lock.
    app.run(port=5051, debug=True, threaded=True)
