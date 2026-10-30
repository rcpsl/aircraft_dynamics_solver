# dB-based variant of solver_server.py — runs on port 5051
import math
import threading
import time
from math import ceil
from collections import deque
from flask import Flask, request, jsonify
from flask_cors import CORS
from z3 import (Int, And, Or, Not, Implies, Sum, If, Solver, Optimize, Bool, sat, unknown,
                main_ctx, Z3Exception)

app = Flask(__name__)
CORS(app)

# Which objective scheme this solver applies, reported on every phase-2 reply.
#
# "lex" since 2026-08-27: the chosen fairness principle is minimized FIRST and
# arrival time only breaks ties among routings that already achieve the principle's
# optimum. Before that this file was "weighted" — one weighted sum in which arrival
# time outvoted the principle roughly 31:1, because the normalization divisors are
# loose by very different amounts (the time penalty reached 68.8% of its normalized
# range against the utilitarian term's 2.2%).
#
# The field stays in the reply because the two schemes give different answers where
# the principle and the clock genuinely trade, and a stored result is not
# interpretable without knowing which produced it. See the minimize() block below.
OBJECTIVE_MODE = "lex"

# Shared by both phases' Z3 timeout and by /progress's elapsed/max display,
# so the two can never drift apart.
# 2026-07-30: raised from 240s. At 4 minutes phase 2 was giving up on configs it
# could still have solved, and a phase-2 timeout is not a slow answer — it falls
# back to phase 1's UNWEIGHTED route, so the group is shown a routing that ignores
# the choices they just made. Waiting longer is much cheaper than that, now that
# /cancel means nobody is trapped by a long wait.
SOLVE_TIMEOUT_MS = 600000
SOLVE_TIMEOUT_CAP_MS = 1800000   # ceiling for the per-request override
# Each request may send "timeoutMs" to override the default. Only one solve runs
# at a time (_solve_lock), so a module-level "currently active" value is
# unambiguous and avoids threading a parameter through both phases' long
# signatures — which bench scripts call directly.
_active_timeout_ms = SOLVE_TIMEOUT_MS


def _timeout_ms():
    return _active_timeout_ms


def _set_timeout(raw):
    """Apply a request's timeoutMs, ignoring anything unusable rather than
    failing the solve over it. Clamped so a typo cannot wedge the single solve
    lock for hours, and floored at 5s so it cannot be set to something that
    times out before Z3 has started."""
    global _active_timeout_ms
    try:
        ms = int(raw)
    except (TypeError, ValueError):
        _active_timeout_ms = SOLVE_TIMEOUT_MS
        return
    _active_timeout_ms = max(5000, min(SOLVE_TIMEOUT_CAP_MS, ms))

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


# ---------------------------------------------------------------------------
# Cancellation (2026-07-30). A workshop participant who changes their mind while
# a multi-minute solve is running should not have to wait it out — and, more importantly,
# their next choice should not queue behind a solve nobody wants any more, since
# _solve_lock serializes everything.
#
# /cancel must never take _solve_lock (the doomed solve is holding it), so it
# reaches the running solve two ways, and both are needed:
#   1. main_ctx().interrupt() — makes the check() currently executing inside Z3
#      give up and return unknown. Without this, a cancel during a long check
#      would not be noticed until that check finished, which is the whole wait.
#   2. _cancel_gen — polled between Z3 calls. Covers the gaps the interrupt
#      cannot reach: phase 1's T-increment loop, and the handover to phase 2.
#
# Generation-stamped so a cancel that lands just as its solve finishes cannot
# carry over and kill the next request queued behind it.
# ---------------------------------------------------------------------------
_cancel_lock = threading.Lock()
_solve_gen = 0        # bumped when a solve starts; identifies "the current solve"
_cancel_gen = -1      # the generation a client asked to abandon
_in_check = False     # True only while Z3 is inside a check() call
_solve_running = False
_solve_client_id = None   # the clientRequestId of the solve currently running


class SolveCancelled(Exception):
    """Raised on the solve thread once the client has abandoned this request."""


def _begin_solve(client_id=None):
    global _solve_gen, _solve_running, _solve_client_id
    with _cancel_lock:
        _solve_gen += 1
        _solve_running = True
        _solve_client_id = client_id
        return _solve_gen


def _end_solve():
    global _solve_running, _solve_client_id
    with _cancel_lock:
        _solve_running = False
        _solve_client_id = None


def _check_cancelled():
    """Bail out if this solve has been cancelled. Safe to call anywhere on the
    solve thread: _solve_lock guarantees only one solve exists at a time, so
    'the current generation' is unambiguous."""
    with _cancel_lock:
        cancelled = _cancel_gen == _solve_gen
    if cancelled:
        raise SolveCancelled()


def _guarded_check(fn):
    """Run a Z3 check, flagging to /cancel that an interrupt would land on
    something. Interrupting while no check is running would leave the context's
    cancel flag set with nothing to consume it — see _drain_interrupt."""
    global _in_check
    with _cancel_lock:
        _in_check = True
    try:
        return fn()
    finally:
        with _cancel_lock:
            _in_check = False


def _best_so_far(opt, L, N, T):
    """Z3's incumbent model after a phase-2 timeout, or None if there isn't one.

    A timeout does not mean the search found nothing. Optimize keeps the best
    solution it has reached and typically spends its last stretch only trying to
    prove that solution optimal, so on timeout there is usually a model in hand
    which satisfies every hard constraint — the D/U caps, adjacency, arrival — and
    is merely unproven. Serving that beats the alternative, which is falling back
    to phase 1's route with no objective applied at all.

    Optimize.model() raises when no solution was ever found, and can also hand back
    one with location variables unassigned, so every L[i][t] is read here rather
    than trusted.
    """
    try:
        model = opt.model()
    except Z3Exception:
        return None
    for i in range(N):
        for t in range(T):
            if model[L[i][t]] is None:
                return None
    return model


def _model_is_feasible(opt, L, model, N, T):
    """Replay a salvaged model against the hard constraints and confirm it holds.

    The entire case for serving _best_so_far's incumbent is that it satisfies every
    hard constraint — the D/U noise caps above all. Z3 is only ever expected to hold
    a satisfying assignment as its incumbent, but "expected to" is not good enough
    for a number a room full of people will read as a guarantee, so it is checked.

    Cheap, because pinning the aircraft positions determines every other variable by
    propagation. Any verdict other than sat — including this check itself timing out
    — counts as failure: an unverified route must not be served.
    """
    s = Solver()
    for a in opt.assertions():
        s.add(a)
    for i in range(N):
        for t in range(T):
            s.add(L[i][t] == model[L[i][t]].as_long())
    s.set("timeout", 30000)
    return _guarded_check(s.check) == sat


def _enumerate_alternatives(opt, L, wcnt_by_t, T_penalty, pins, seed_model, K, distinct_on,
                            N, T, M, start_positions, end_positions,
                            baseline, aircraft_dB, int_mult):
    """Up to K distinct routings satisfying every hard constraint, the first being
    seed_model's own. Returns (list, why_it_stopped).

    Equal and Sufficientarian set no objective at all (see _principle_name): their
    rule is the hard D/U cap, so EVERY routing inside the cap satisfies the principle
    equally and the single answer /solve returns is picked by the arrival-time
    tie-break and then by Z3's search order. Returning several makes that
    arbitrariness visible instead of implying a preference the principle never
    expressed. It works for the objective-bearing principles too, where `pins` keeps
    the alternatives at the optimum the served answer reached.

    Built on a plain Solver seeded from opt.assertions() — the same copy
    _model_is_feasible relies on — which carries the D/U caps, adjacency, the
    start/end pins, the active-noise tracking and sticky arrival, but NOT the
    minimize directives, which is exactly why the enumeration is free to wander
    among equally-good answers. `pins` puts back as much of the objective as is
    wanted.

    distinct_on decides what "different" means, and the difference is not cosmetic.
    Identical aircraft are interchangeable: the 5x5 dashboard's default demand sends
    4+4+2+2+2+2 aircraft over six shared start/end pairs, so one routing has
    4! * 4! * 2!^4 = 9216 relabellings, and blocking on L PERMITS all of them — a
    relabelling satisfies the clause while changing nothing anyone hears. Whether Z3
    actually returns them is down to its search order, and on small cases tried here
    it did not, so this is a risk the default removes rather than a measured failure.
    Blocking on the weighted-count matrix instead — the variable the D/U caps are
    enforced on and the one the noise output is computed from — makes the guarantee
    unconditional: two alternatives differ in what some community hears at some
    timestep, or they are not two alternatives.

    "paths" is kept for the case where the aircraft are genuinely distinguishable
    (per-aircraft multipliers, or a question about one operator's trajectory), where
    two routings with the same count matrix are still different answers.
    """
    s = Solver()
    for a in opt.assertions():
        s.add(a)
    for p in pins:
        s.add(p)
    # A fresh full budget, not the remainder of phase 2's: the enumeration is opt-in
    # and a caller asking for it has accepted that it costs another solve.
    s.set("timeout", _timeout_ms())

    def block(model):
        """A clause forbidding this model's projection, so the next check must differ
        somewhere that matters. model_completion because Z3 may leave a variable it
        no longer cares about unassigned, and a None here would crash the loop."""
        if distinct_on == "paths":
            return Or([L[i][t] != model.evaluate(L[i][t], model_completion=True).as_long()
                       for i in range(N) for t in range(T)])
        return Or([wcnt_by_t[t][m] != model.evaluate(wcnt_by_t[t][m], model_completion=True).as_long()
                   for t in range(T) for m in range(M)])

    out = []
    model = seed_model
    while True:
        paths = [
            [model.evaluate(L[i][t], model_completion=True).as_long() for t in range(T)]
            for i in range(N)
        ]
        count_matrix, noise_matrix_dB = _active_output_matrices(
            paths, start_positions, end_positions, N, M, T, baseline, aircraft_dB,
            multipliers=int_mult
        )
        entry = {"paths": paths, "countMatrix": count_matrix, "noiseMatrix": noise_matrix_dB}
        if T_penalty is not None:
            entry["arrivalPenalty"] = model.evaluate(T_penalty, model_completion=True).as_long()
        out.append(entry)

        if len(out) >= K:
            return out, "limit"
        s.add(block(model))
        _check_cancelled()
        verdict = _guarded_check(s.check)
        if verdict == sat:
            model = s.model()
            continue
        # An interrupt also reads as unknown, so ask before blaming the clock.
        _check_cancelled()
        # "exhausted" is a real answer and a strong one: it says no other routing
        # meets the conditions, so the one served is not an arbitrary pick after all.
        return out, ("timeout" if verdict == unknown else "exhausted")


def _principle_name(optimize_prox, optimize_prior, optimize_util,
                    util_noise_mode, weighted_by_people):
    """The objective phase 2 was asked to optimize, in the dashboard's own words.

    Returns None when there was no objective at all: Equal and Sufficientarian set
    none, their rule being the hard D/U cap that phase 1 already enforced. That
    distinction decides what a message about phase 2 should say, so it must not be
    flattened into a generic "your fairness choices" — it would send an Equal user
    hunting for a problem that is not there.

    The People toggle is not an objective of its own — it switches
    optimizeUtilitarian on and supplies stationTransitWeights — so it shows up here
    as a qualifier on whichever utilitarian branch is live, not as an entry.
    """
    if optimize_prox:
        name = "the Proportional (proximity) objective"
    elif optimize_prior:
        name = "the Prioritarian (protected-community) objective"
    elif optimize_util and util_noise_mode:
        name = ("the Utilitarian objective (total noise"
                + (", weighted by population)" if weighted_by_people else ")"))
    elif optimize_util:
        name = ("the People objective (travel time"
                + (", weighted by population)" if weighted_by_people else ")"))
    else:
        return None
    # Prioritarian/Proportional with People on carry a second live term. Say so, or
    # the reader is told one objective was affected when two were.
    if weighted_by_people and (optimize_prox or optimize_prior):
        name += " or the People objective alongside it"
    return name


def _drain_interrupt():
    """Absorb a stray interrupt before starting a solve.

    /cancel decides to interrupt and then calls into Z3; if the running check
    finishes in between, the cancel flag stays set on the context and would kill
    the first check of the NEXT solve, which would surface as a bogus timeout.
    A throwaway check on an empty solver consumes it in microseconds."""
    try:
        Solver().check()
    except Exception:
        pass


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
    Covers n = 0..N, where N is the largest count a station could ever hold. With
    per-aircraft multipliers that is sum(int_mult), not the aircraft count, which
    is why callers pass max_weighted_count rather than N.
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


def proximity_weights_from_vertiports(adjacency, vertiport_stations, M, base, max_layer=None):
    """Derive per-station proximity weights by BFS layering outward from the vertiports.

    Layer 0 is the vertiports themselves, layer k the stations first reachable in k
    moves; station weight is base**layer, so vertiports are the *cheapest* tiles and
    cost grows with distance.  Minimizing occupancy x weight therefore pulls traffic
    inward and concentrates burden on the tiles nearest the vertiports.

    BFS follows out-edges ("stations a vertiport tile can directly go to"), matching
    how the principle is specified.  On a symmetric grid that is the same as an
    undirected walk; clients needing a different metric (e.g. Manhattan rather than
    the 8-neighbour flight adjacency) should pass an explicit weight vector instead.

    `max_layer`, if given, clamps the exponent so deep graphs cannot blow the weights
    up exponentially.  Stations unreachable from every vertiport sit one layer beyond
    the deepest reachable one (clamped the same way), making them the most expensive.

    Returns (weights, layers), both length-M lists indexed 0-based.
    """
    layers = [None] * M
    frontier = []
    for v in vertiport_stations:
        if layers[v - 1] is None:
            layers[v - 1] = 0
            frontier.append(v - 1)

    depth = 0
    while frontier:
        depth += 1
        nxt = []
        for a in frontier:
            for b in range(M):
                # self-loops are ubiquitous here (soft T requires them) and would
                # otherwise re-enter the source; the visited check absorbs them.
                if adjacency[a][b] and layers[b] is None:
                    layers[b] = depth
                    nxt.append(b)
        frontier = nxt

    reachable = [l for l in layers if l is not None]
    unreachable_layer = (max(reachable) + 1) if reachable else 0
    layers = [unreachable_layer if l is None else l for l in layers]
    if max_layer is not None:
        layers = [min(l, max_layer) for l in layers]

    return [float(base) ** l for l in layers], layers


def _max_weighted_price(price_table, int_pw, D_count, budget, M, T):
    """Exact maximum of  Sum_m price_table[m][n_m] * int_pw[m]  over one timestep,
    subject to  Sum_m n_m <= budget  and  n_m <= D_count[m],  times T.

    Used to normalize the proximity objective in "noise" mode. The obvious bound —
    M * T * max_price * max_pw, which is what the utilitarian-noise path uses —
    describes every one of the M stations simultaneously carrying the whole fleet.
    That needs M * budget aircraft-units when only `budget` exist, and on the 5x5 map
    it overstates the reachable maximum by 16x. Dividing by it would leave the
    proximity term unable to exceed ~6% of its nominal range while the soft-T
    penalty, whose N*(T-1) bound IS tight, reaches 55-69% of its own — so
    "weightProximity 1.0, weightTime 1.0" would silently behave like 0.06 vs 1.0.
    Nothing would error; the routes would just stop responding to the weights.
    (Under the lexicographic scheme below the time term can no longer outvote the
    principle, but the divisor still sets how two live principle terms trade — People
    alongside Proportional — so it still has to be tight.)

    A bounded knapsack DP rather than the greedy marginal allocation the concavity
    of the dB curve would otherwise license, because build_scaled_table ROUNDS to
    integer centi-dB and rounding destroys concavity: baseline 65 dB gives the row
    [0, 4, 9, 13, 17, 21], whose marginals are 4, 5, 4, 4, 4 — the second aircraft
    appears to add more than the first, where the true marginals fall 4.32, 4.28,
    4.24. Greedy then undershoots the real maximum (found by brute force on random
    cases), and undershooting is the harmful direction: too small a divisor
    over-weights the term instead of under-weighting it. The DP assumes nothing
    about the curve's shape and is exact, so the normalization is tight as well as
    sound. O(M * budget^2) — a few thousand operations at 5x5 scale.

    Reachability is NOT modelled: the winning arrangement may be unreachable within
    T moves, which leaves the result a valid upper bound on what the solver can
    actually attain, only slightly loose.
    """
    if not int_pw or budget <= 0 or T <= 0:
        return 0
    # dp[b] = best single-timestep total using the stations seen so far and at most
    # b aircraft-units. Initialised to 0 across the whole range, which is what makes
    # the constraint "<= budget" rather than "== budget".
    dp = [0] * (budget + 1)
    for m in range(M):
        cap = min(budget, D_count[m])
        if cap <= 0:
            continue
        row, w = price_table[m], int_pw[m]
        nxt = dp[:]
        for b in range(1, budget + 1):
            best = dp[b]
            for k in range(1, min(b, cap) + 1):
                cand = dp[b - k] + w * row[k]
                if cand > best:
                    best = cand
            nxt[b] = best
        dp = nxt
    return dp[budget] * T


def min_moves(adjacency, src, dst, M, allowed=None):
    """BFS: minimum moves from src to dst (1-indexed). Returns inf if unreachable.

    `allowed`, if given, is a predicate on 1-indexed stations that every node
    *after* the source must satisfy. The source itself is exempt: an aircraft
    sitting on its start station has moved[i][t] False, so it is not active and
    adds no noise there. That exemption ends the moment it departs — moved[] is
    sticky — so a station the walk returns to must satisfy `allowed` like any
    other, which is why the filter is applied on arrival at a node rather than
    on departure from it. The destination is included: active[i][t] is still
    True on the arrival timestep (arrived[i][t-1] has not flipped yet).
    """
    if src == dst:
        return 0
    ok = allowed if allowed is not None else (lambda _m: True)
    visited = [False] * (M + 1)
    visited[src] = True
    queue = deque([(src, 0)])
    while queue:
        node, moves = queue.popleft()
        for nb in range(1, M + 1):
            if nb == node:
                continue
            if adjacency[node - 1][nb - 1] == 1 and not visited[nb] and ok(nb):
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

    U uses a max/min encoding, from the identity

        |dB(m1) - dB(m2)| <= U  for every pair   <=>   max(dB) - min(dB) <= U

    so two auxiliary integers and 2M+1 constraints replace what used to be a table
    over every ordered station pair and every count value — O(M^2 * D_count) Implies
    per timestep, roughly 95% of all constraints in the model, and the reason
    5x5-sized problems timed out. The encoding is sound and complete: dbmax is forced
    at or above the true maximum and dbmin at or below the true minimum, so bounding
    their difference bounds the true spread; conversely any assignment whose true
    spread fits within U is satisfiable by pinning the two auxiliaries to the actual
    extremes.

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

    # There is deliberately no start- or end-position D pre-check.
    #
    # Both used to exist and both contradicted the active-noise model. A start
    # station never accumulates noise — an aircraft that has not departed has
    # moved[i][t] False, hence active[i][t] False — so the start check fired on a
    # quantity the model never computes, and rejected every realistic vertiport
    # layout, where a corridor's whole fleet shares one origin. Aircraft that arrive
    # before T-1 are already silent (ha[i][T-2] True → active[i][T-1] False), so the
    # end check overstated destination noise; under soft T, where arriving early is
    # the norm, it was wrong more often still. Neither is a sound necessary
    # condition, so neither has a weaker version worth keeping.
    #
    # The per-aircraft D-admissible reachability test below replaces them: same
    # O(M²) cost, but it only asserts things the model actually enforces. It earns
    # its keep on more than error quality — without it a tight D turns into a
    # multi-minute Z3 search that ends in a timeout rather than a usable answer.

    # Precompute the count-based D table now (it only depends on M/D/baseline, not
    # on T) so it is available to the reachability check below and max_d_count is
    # known before sizing the T search budget further down.
    D_count = _compute_d_counts(M, max_weighted_count, D_scaled, scaled_table_w)
    max_d_count = max(D_count) if D_count else 0

    # BFS reachability per aircraft, restricted to D-admissible stations.
    #
    # D_count[m] == 0 means station m cannot host even one weighted aircraft-unit
    # without breaching D, so no active aircraft may ever occupy it; more generally
    # aircraft i alone needs D_count[m] >= int_mult[i]. Routing each aircraft over
    # the subgraph of stations that clear its own multiplier is a sound *necessary*
    # condition — it ignores every interaction between aircraft, so it can only
    # under-constrain, never reject a feasible instance. That is what the deleted
    # start/end pre-checks got wrong: they asserted co-location facts the model
    # never computes. This one asserts only what the model does enforce.
    #
    # It also tightens T_lower, since a detour around an inadmissible station is a
    # genuine lower bound on that aircraft's move count.
    plain_mins = [
        min_moves(adjacency, start_positions[i], end_positions[i], M)
        for i in range(N)
    ]
    if any(m == float('inf') for m in plain_mins):
        return {
            "status": "unsat", "reason": "unreachable",
            "detail": "One or more aircraft cannot reach their destination via the given adjacency"
        }

    individual_mins = [
        min_moves(adjacency, start_positions[i], end_positions[i], M,
                  allowed=lambda m, need=int_mult[i]: D_count[m - 1] >= need)
        for i in range(N)
    ]
    if any(m == float('inf') for m in individual_mins):
        i = next(i for i in range(N) if individual_mins[i] == float('inf'))
        dest = end_positions[i]
        need = int_mult[i]
        if D_count[dest - 1] < need:
            why = (
                f"its destination station {dest} (baseline {baseline[dest-1]:.1f} dBA) "
                f"admits at most {D_count[dest-1]} weighted aircraft-units under D={D} dB, "
                f"but the aircraft carries {need}. An aircraft is still active on the "
                f"timestep it arrives, so the destination must be able to hold it."
            )
        else:
            blocked = sum(1 for m in range(M) if D_count[m] < need)
            why = (
                f"every route from station {start_positions[i]} to station {dest} passes "
                f"through a station that cannot hold it: {blocked} of {M} stations admit "
                f"fewer than {need} weighted aircraft-units under D={D} dB."
            )
        return {
            "status": "unsat", "reason": "noise_cap",
            "detail": f"Aircraft {i + 1} has no route that respects D: {why} Raise D to continue."
        }

    T_lower = max(2, max(individual_mins) + 1)

    def valid_next(src_1indexed):
        s0 = src_1indexed - 1
        return [dst + 1 for dst in range(M) if adjacency[s0][dst] == 1]

    # T search budget: sized from the same constraint-volume metric that guards
    # against Z3 blowing up. A flat budget crashed Z3 with an out-of-memory error
    # for large N (e.g. N=30, M=16 reached ~246k constraints at T_hard_cap=32 and
    # OOM'd), so the budget must shrink for problems where each extra timestep is
    # expensive, while still giving small problems plenty of room to search.
    #
    # Per timestep the model emits O(M * max_d_count) If-chain nodes for the dB
    # expressions plus O(M * N) terms for the weighted count sums. The pairwise U
    # table that made this O(M^2 * max_d_count) is gone (see _add_noise_constraints),
    # which is why problems that used to be rejected as noise_domain_too_large now
    # fit comfortably.
    #
    # The ceiling is 40_000 against that metric, not the 80_000 tuned for the old
    # M^2 cost model: keeping the old number would have admitted roughly 628 weighted
    # aircraft-units at M=25, far beyond anything that has actually been solved.
    # 40_000 admits ~308 against the 25 the old formula allowed, so the workshop
    # gains the headroom it needs while the accepted range stays inside tested
    # territory.
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

    # Build the permanent base state up to T_lower once. The search loop below
    # extends it by a single timestep per iteration instead of re-encoding.
    L = [[Int(f"L_{i}_{t}") for t in range(T_lower)] for i in range(N)]
    s = Solver()
    s.set("timeout", _timeout_ms())  # yields unknown instead of crashing

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
        # Between checks the interrupt has nothing to land on, so poll instead.
        _check_cancelled()
        _set_progress(phase="phase1", T=T_current, T_min=T_lower, T_max=T_hard_cap, started_at=time.monotonic())

        # Assumption booleans — same names reused safely because the Implies
        # constraints referencing them are pushed/popped each iteration.
        end_asms = [Bool(f"end_{i}") for i in range(N)]

        s.push()
        for i in range(N):
            s.add(Implies(end_asms[i], L[i][T_current - 1] == end_positions[i]))

        result = _guarded_check(lambda: s.check(*end_asms))

        if str(result) == "unknown":
            s.pop()
            # An interrupt also surfaces as unknown, so ask before blaming the
            # clock — reporting a cancel as a timeout would send the dashboard
            # off to retry at reduced demand for a solve nobody is waiting on.
            _check_cancelled()
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

        # ── unsat-core early exit ───────────────────────────────────────────
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

        # ── extend the base encoding by exactly one timestep ────────────────
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
                        optimize_util, optimize_prior, optimize_prox,
                        protected_stations, proximity_weights,
                        w_util, w_prior, w_prox,
                        soft_T, w_time,
                        station_transit_weights,
                        util_noise_mode,
                        aircraft_multipliers,
                        baseline, aircraft_dB,
                        proximity_mode="noise", proximity_noise_ref=None,
                        enumerate_n=0, enumerate_distinct="counts",
                        enumerate_at_optimum=True):
    """Phase-2 optimizer: rebuild all constraints in a fresh Optimize instance and
    minimize a weighted combination of transit time and protected-station noise (dB).

    T is fixed for this phase, but not always to phase 1's answer: _solve_impl passes
    phase 1's minimum under hard T and T_max under soft T, where sticky arrival lets
    aircraft finish early inside a longer horizon.

    NOTE: z3.Optimize is slower than z3.Solver and this phase carries the objective
    terms as well, so at large N, T, or M it dominates the wall clock — it is the
    phase that runs the timeout budget out.
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

    # Noise cap and global disparity (counting only active aircraft).
    # Built from the weighted table so D/U hard constraints are checked against
    # the same weighted counts used for the displayed noise matrix below.
    D_count = _compute_d_counts(M, max_weighted_count, D_scaled, scaled_table_w)

    # Guard: a generous D combined with large aircraft multipliers can push D_count
    # close to max_weighted_count for every station. Per timestep the model emits
    # O(M * D_count) If-chain nodes plus O(M * N) count-sum terms; back when the
    # pairwise U table made this O(M^2 * D_count), too large a product crashed Z3
    # with an access violation. The metric reflects what is actually emitted, and
    # the 75_000 ceiling matches it — see the note on SAFE_CONSTRAINT_VOLUME in
    # find_min_T for why the old 150_000 would be far too permissive here.
    max_d_count = max(D_count) if D_count else 0
    if T * M * (max_d_count + N) > 75_000:
        raise ValueError(
            f"Noise-constraint search space too large for phase-2 optimization "
            f"(stations can hold up to {max_d_count} weighted aircraft-units under "
            f"the current D). This is usually caused by a generous D combined with "
            f"large aircraft multipliers. Lower D, reduce aircraft multipliers, "
            f"reduce T_max, or reduce N/M to continue."
        )

    # (D_count and its guard are computed here, well before the constraints they
    # feed, because the proximity normalization below needs the per-station cap —
    # and the volume guard is a precondition worth failing before Optimize() exists.)

    # ── Metric normalization ──────────────────────────────────────────────────
    # All metrics are divided by their theoretical maximums so that weights
    # operate on a comparable scale regardless of N, T, M, D.
    #
    # Transit and T-penalty: count-based, unchanged from the count-based solver.
    # Prioritarian: dB-based; bounded by all-N-aircraft case
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

    # Proximity: per-station weight x the burden that station carries. Weights arrive
    # as floats (base**layer, or a client-supplied vector), so scale them to integers
    # the same way the station-weighted transit path does, keeping the Z3 term in
    # integer arithmetic.
    P_SCALE = 100
    if proximity_weights is not None:
        int_pw = [round(w * P_SCALE) for w in proximity_weights]
    else:
        int_pw = None

    # What "burden" means is the proximity_mode:
    #
    #   "noise" (the default since 2026-09-03) — weight x the dB INCREASE the station
    #     suffers. This is the burden a community actually experiences, and it is what
    #     the term prices. Measured against the old count term over 30 rankings
    #     (proximity_noise_experiment/README.md): never a louder peak, 4.8-5.6 dB
    #     quieter in 11 of 28, and traffic over 45 dB tiles pinned to its floor of 4
    #     aircraft-timesteps every time. Two consequences worth knowing, because
    #     neither is a bug:
    #       * dB is CONCAVE in the count, so stacking aircraft on one tile is
    #         cheaper than spreading them (3 on a 45 dB tile costs 6.02 dB, three
    #         separate tiles cost 9.03). The objective therefore concentrates
    #         traffic, where the count mode was indifferent to concentration.
    #       * the increase depends on the station's own baseline — one aircraft adds
    #         3.01 dB at a 45 dB tile and 0.043 dB at a 65 dB tile, a ~160x implicit
    #         price gradient favouring already-loud tiles. If the caller ALSO prices
    #         ambient noise inside proximity_weights (the 5x5 dashboard does, as one
    #         of four participant-ranked factors), ambient is counted twice and the
    #         copy the participant cannot control is the stronger one: the curve fits
    #         an ambient rank weight of ~0.88 where the participant's maximum is 0.40,
    #         so the ranking moves the routing much less than it does under count.
    #         proximity_noise_ref exists for exactly that case. The same gradient is
    #         also what Z3 prunes with, which is why this mode is ~28x slower.
    #
    #   "count" — weight x occupancy, the original term: every aircraft-unit-timestep
    #     on a station costs that station's weight, linearly, regardless of baseline
    #     or of who else is there. Separable across aircraft, so far cheaper for
    #     Optimize (median 38 s against noise mode's 1029 s on the 5x5 payload), and
    #     it leaves the participants' ranking the strongest force in the objective.
    #     Kept as the escape hatch for a session that must finish inside the timeout,
    #     and to reproduce any answer stored before 2026-09-03.
    #
    # proximity_noise_ref, if set, prices every station off ONE reference baseline
    # instead of its own. That keeps the concavity (burden still is not linear in
    # overflights) while removing the implicit ambient gradient, leaving ambient
    # wholly in the caller's weight vector.
    if proximity_mode not in ("noise", "count"):
        raise ValueError(f"proximity_mode must be 'noise' or 'count', got {proximity_mode!r}")
    if proximity_mode == "count":
        prox_price_table = None   # the Z3 term is the count variable itself
    elif proximity_noise_ref is None:
        prox_price_table = scaled_table_w          # per-station, mode A
    else:
        ref_row = [round(dB_increase(proximity_noise_ref, n, aircraft_dB) * SCALE)
                   for n in range(max_weighted_count + 1)]
        prox_price_table = [ref_row] * M           # one shared curve, mode B

    if int_pw is None:
        max_proximity = 0
    elif proximity_mode == "count":
        # Every aircraft-unit occupies exactly one station per active timestep, for
        # at most T timesteps, at worst on the costliest station. Greedy over the
        # linear table n -> n gives the same answer; spelled out to keep this mode
        # bit-identical to what it produced before the noise term existed.
        max_proximity = sum(int_mult) * T * max(int_pw)
    else:
        max_proximity = _max_weighted_price(
            prox_price_table, int_pw, D_count, sum(int_mult), M, T
        )

    # A zero bound means the term would vanish from the objective without any
    # complaint — all-zero weights, or a reference baseline so high that no station
    # can be made to cost anything. That is the silent-failure mode this whole
    # normalization block is trying to avoid, so say it out loud instead.
    if optimize_prox and w_prox > 0 and max_proximity <= 0:
        raise ValueError(
            "The proximity objective would have no effect: its maximum possible "
            "value is zero. Check that proximityWeights were supplied and are not "
            "all zero"
            + (f" and that proximityNoiseRef={proximity_noise_ref} is a plausible "
               f"ambient level in dB" if proximity_noise_ref is not None else "")
            + "."
        )

    # Use scaled (integer) units for dB normalization bounds so all objective
    # terms live in the same numeric range as the Z3 dB expressions (×SCALE).
    # Mixing unscaled dB bounds with scaled Z3 expressions would make the dB
    # objectives SCALE× heavier than the count-based utilitarian term.
    max_dB_scaled_per_station = max(scaled_table_w[m][max_weighted_count] for m in range(M))
    max_protected_dB    = len(protected_stations)    * T * max_dB_scaled_per_station
    # When station-weighted, each term in total_util_noise is additionally scaled by
    # int_tw[m] (see below), so the normalization bound needs the same max_tw factor
    # the transit-cost path already applies to max_transit.
    max_util_noise_dB   = M * T * max_dB_scaled_per_station * (max(1, max_tw) if int_tw is not None else 1)

    # After normalization, all coefficients are dimensionless and comparable,
    # so w_util = w_prior = w_time = 1.0 gives genuinely equal weighting.
    if optimize_util:
        if util_noise_mode:
            eff_w_util = (w_util / max_util_noise_dB) if max_util_noise_dB > 0 else 0.0
        else:
            eff_w_util = (w_util / max_transit)       if max_transit       > 0 else 0.0
    else:
        eff_w_util = 0.0
    eff_w_prior = (w_prior / max_protected_dB)    if (optimize_prior and max_protected_dB    > 0) else 0.0
    eff_w_prox  = (w_prox  / max_proximity)       if (optimize_prox  and max_proximity        > 0) else 0.0
    eff_w_time  = (w_time  / max_T_penalty)       if (soft_T         and max_T_penalty        > 0) else 0.0

    def valid_next(src_1indexed):
        s0 = src_1indexed - 1
        return [dst + 1 for dst in range(M) if adjacency[s0][dst] == 1]

    opt = Optimize()
    opt.set("timeout", _timeout_ms())  # cap; without this Optimize() can hang indefinitely

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

    wdB_by_t = []
    wcnt_by_t = []
    # Only populated when the proximity term needs a dB curve OTHER than each
    # station's own — i.e. proximity_noise_ref is set. Mode A reuses wdB_by_t, so it
    # adds no Z3 nodes at all; mode B pays for a second If-chain per station-timestep.
    prox_dB_by_t = []
    need_prox_table = (eff_w_prox > 0 and proximity_mode == "noise"
                       and proximity_noise_ref is not None)
    for t in range(T):
        # Weighted-count variables drive both the D/U hard constraints and the
        # soft dB objectives/output, so displayed noise never exceeds what's enforced.
        WC_t = [Sum([If(And(L[i][t] == m + 1, active[i][t]), int_mult[i], 0) for i in range(N)]) for m in range(M)]
        wcnt_t = [Int(f"o_wcnt_{m}_{t}") for m in range(M)]
        for m in range(M):
            opt.add(wcnt_t[m] == WC_t[m])
        # These dB expressions are needed for the soft objectives below anyway, and
        # the U constraint reuses them rather than building a table of its own, so
        # the disparity encoding costs 2M+1 constraints and no new terms.
        wdB_exprs_t = [make_dB_expr(wcnt_t[m], m, scaled_table_w, D_count[m]) for m in range(M)]
        _add_noise_constraints(opt, wcnt_t, wdB_exprs_t, M, D_count, U_scaled, f"p2_{t}")
        wdB_by_t.append(wdB_exprs_t)
        wcnt_by_t.append(wcnt_t)
        if need_prox_table:
            prox_dB_by_t.append([
                make_dB_expr(wcnt_t[m], m, prox_price_table, D_count[m]) for m in range(M)
            ])

    # ── Build objective terms ─────────────────────────────────────────────────
    objective_terms = []

    # Declare result variables in outer scope so the result block can read them
    transit = None
    total_transit = None
    total_util_noise = None
    protected_noise_dB = None
    proximity_cost = None
    # Hoisted for the same reason, plus one more: the result block reports it, and
    # it is never built at all when the arrival tie-break is off (soft_T false, or
    # w_time 0).
    T_penalty = None

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

    if eff_w_prox > 0:
        # Both burden measures come off wcnt_by_t[t][m], the multiplier-weighted count
        # of *active* aircraft on station m at t — the same variable that drives the
        # D/U caps and the displayed count matrix — so the burden being priced here is
        # exactly the burden being reported.
        #
        #   count mode: wcnt itself. Each aircraft-unit-timestep on m costs int_pw[m],
        #     which is what "1 time step on a tile costs that tile's weight" means once
        #     aircraft multipliers are folded in.
        #   noise mode: the dB increase wcnt implies, which is wdB_by_t (per-station)
        #     or prox_dB_by_t (one reference baseline). Note the units differ by
        #     SCALE between the two modes; the reported value below divides
        #     accordingly, and max_proximity was computed in matching units.
        if proximity_mode == "count":
            prox_burden = wcnt_by_t
        else:
            prox_burden = prox_dB_by_t if need_prox_table else wdB_by_t
        proximity_cost = Sum([
            prox_burden[t][m] * int_pw[m]
            for t in range(T)
            for m in range(M)
        ])
        objective_terms.append(eff_w_prox * proximity_cost)

    # Counted here, before the arrival tie-break is built, so that "was a principle
    # optimized?" answers the question the caller means. objective_terms holds only
    # principle terms at this point; arrival time is minimized separately below and
    # deliberately never joins this list.
    n_principle_terms = len(objective_terms)

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

    # ---- LEXICOGRAPHIC: principle first, arrival time only as a tie-break ----
    #
    # This file used to fold eff_w_time * T_penalty into one weighted sum with the
    # principle terms. That let arrival time trade against the fairness objective,
    # and because the normalization divisors are loose by very different amounts the
    # time term outvoted the principle roughly 31:1 on the measured payload (68.8% of
    # its normalized range against the utilitarian term's 2.2%). Z3 was mostly just
    # minimizing arrival time.
    #
    # Z3's Optimize defaults to priority='lex' and applies objectives in CALL ORDER,
    # so minimizing the principle first makes it strictly dominant: the time tier can
    # only choose among solutions that already achieve the principle's optimum. It
    # provably cannot cost a single unit of fairness.
    #
    # The principle tier stays a weighted sum rather than becoming further tiers,
    # because when the People toggle is on with a non-Utilitarian principle BOTH
    # optimize_prox/prior and optimize_util are set, and the 0.3 vs 1.0 weighting
    # between them is a deliberate dashboard choice (see buildSolveRequest). Only
    # time is demoted; the weights that were meant to trade against each other
    # still do.
    #
    # Consequences worth knowing:
    #   - w_time no longer sets a magnitude, only whether the tie-break runs at all.
    #     Its normalization (max_T_penalty) is now used solely to decide eff_w_time > 0.
    #   - With a single principle term live, that term's weight cannot move the
    #     argmin. Scaling weightProximity/weightPrioritarian/weightUtilitarian alone
    #     is mathematically inert. Two live terms (People alongside a principle)
    #     still trade at their stated ratio.
    #   - weightTime 0 is the one input where this is identical to the old weighted
    #     scheme: eff_w_time == 0 means T_penalty is never built, so there is no
    #     second tier to add.
    #
    # Measured before adopting (lex_objective_experiment/, 2026-08-25): fairness is
    # EXACTLY equal to the weighted scheme on Proportional, Prioritarian, Equal and
    # Sufficientarian; ~1.4x slower on Proportional, ~2x FASTER on Prioritarian, even
    # on the other two. On Utilitarian + People the two genuinely diverge and lex
    # reaches a 5.5-7.5% better noise value, but did not prove optimality within a
    # 1800s cap where the weighted scheme proves it in 202-658s. That case now relies
    # on the best-so-far salvage below.
    if objective_terms:
        opt.minimize(Sum(objective_terms))
    if T_penalty is not None:
        opt.minimize(T_penalty)

    # Building the phase-2 encoding above is itself slow at large N; check before
    # committing to the search rather than after.
    _check_cancelled()
    check_result = _guarded_check(opt.check)
    partial = False
    if check_result != sat:
        _check_cancelled()   # an interrupt reads as unknown; don't call it a timeout
        # Distinguish a timed-out search (unknown — Z3 ran out of the SOLVE_TIMEOUT_MS
        # budget without an answer) from a genuine unsat (which "should not happen":
        # phase-1 already confirmed sat at this T, ignoring objectives/weights).
        # Callers must not treat this as a normal phase-1 fallback silently — the
        # caller is expected to surface why phase-2 didn't produce a weighted result.
        #
        # But a timeout is only a real failure when Z3 never reached a solution.
        # When it did, that incumbent has the objective applied and satisfies every
        # hard constraint; it is unproven, not invalid. Return it marked partial
        # rather than discarding the whole of phase 2's work for phase 1's route.
        model = _best_so_far(opt, L, N, T) if check_result == unknown else None
        if model is not None and not _model_is_feasible(opt, L, model, N, T):
            # An interrupt makes that replay return unknown too, and a cancelled solve
            # must read as cancelled rather than as an unverifiable model.
            _check_cancelled()
            model = None          # could not be verified; fall back rather than serve it
        if model is None:
            return {"status": "phase2_failed",
                    "reason": "timeout" if check_result == unknown else "unsat_unexpected"}
        partial = True
    else:
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

    # ── Alternative routings (opt-in, `enumerate` in the request) ─────────────
    # Off by default, so a request that does not ask for it gets a byte-identical
    # reply and the dashboard's response cache is unaffected.
    #
    # enumerate_at_optimum pins each RAW principle metric and the arrival penalty to
    # the value this model reached, rather than pinning the weighted sum. That is
    # deliberately stronger: pinning the sum would let two live terms trade against
    # each other and call the result "equally good", when the point of the list is to
    # show routings that are equally good on every term at once. For Equal and
    # Sufficientarian there are no principle metrics, so this reduces to pinning
    # arrival time — the only thing that chose the answer in the first place.
    if enumerate_n > 0:
        pins = []
        if enumerate_at_optimum:
            for expr in (total_util_noise, total_transit, protected_noise_dB,
                         proximity_cost, T_penalty):
                if expr is not None:
                    pins.append(expr == model.evaluate(expr, model_completion=True).as_long())
        alternatives, why = _enumerate_alternatives(
            opt, L, wcnt_by_t, T_penalty, pins, model, enumerate_n, enumerate_distinct,
            N, T, M, start_positions, end_positions, baseline, aircraft_dB, int_mult
        )
        result["alternatives"]         = alternatives
        result["alternativesStatus"]   = why
        result["alternativesDistinct"] = enumerate_distinct
        result["alternativesAtOptimum"] = bool(enumerate_at_optimum and pins)

    if eff_w_util > 0:
        if util_noise_mode:
            raw_util_noise = model.evaluate(total_util_noise).as_long()
            result["totalUtilNoise"] = raw_util_noise / SCALE / W_SCALE if int_tw is not None else raw_util_noise / SCALE
        else:
            # UNITS WARNING, deliberately not fixed. These two go out RAW while
            # totalUtilNoise on the line above is divided by SCALE and W_SCALE — so
            # totalTransit reads 8300 where the natural value is 83. It is wrong and
            # it is load-bearing: dB45_collection/ has already stamped raw values into
            # its published CSVs and its scripts read them back at this scale, so
            # rescaling here would silently invalidate that whole collection. The 5x5
            # dashboard sidesteps it by measuring trip length from the returned paths
            # instead (see its comment at ~:1628). Divide at the point of display, or
            # migrate dB45_collection first.
            result["transitTimes"] = [model.evaluate(transit[i]).as_long() for i in range(N)]
            result["totalTransit"] = model.evaluate(total_transit).as_long()

    if eff_w_prior > 0:
        result["protectedNoise"]    = model.evaluate(protected_noise_dB).as_long() / SCALE
        result["protectedStations"] = protected_stations

    if eff_w_prox > 0:
        raw_prox = model.evaluate(proximity_cost).as_long()
        # count mode sums plain counts (P_SCALE only); noise mode sums ×SCALE dB
        # expressions, so it carries both scales.
        result["proximityCost"] = (raw_prox / P_SCALE if proximity_mode == "count"
                                   else raw_prox / SCALE / P_SCALE)
        # Echo how the burden was priced: the same request payload produces different
        # numbers under different modes, and a stored result with no mode on it cannot
        # be told apart from a pre-2026-09-03 one.
        result["proximityMode"] = proximity_mode
        if proximity_noise_ref is not None:
            result["proximityNoiseRef"] = proximity_noise_ref

    # ---- Reported by both solvers, so neither can be told from the other by the
    # shape of its reply; objectiveMode is the one field whose VALUE differs.
    #   optimality           "optimal" = proven best. "partial" = best reached
    #                        before the clock ran out: the objective is applied,
    #                        just not proven best. (A phase-2 failure, handled in
    #                        solve(), reports "none".)
    #   principleOptimized   False for Equal and Sufficientarian, which set no
    #                        objective — it separates a result that is at its
    #                        principle's optimum from one where no principle was
    #                        ever being optimized. The two look alike in a routing.
    #   arrivalPenalty       pre-arrival aircraft-timesteps summed over the fleet.
    #                        The ONE field that is not always present: it is omitted
    #                        when the arrival term is off in either solver, and on a
    #                        phase-2 failure, where there is no phase-2 model to
    #                        evaluate it against.
    result["objectiveMode"]      = OBJECTIVE_MODE
    result["optimality"]         = "partial" if partial else "optimal"
    result["principleOptimized"] = n_principle_terms > 0
    if T_penalty is not None:
        result["arrivalPenalty"] = model.evaluate(T_penalty).as_long()

    return result


@app.route("/solve", methods=["POST"])
def solve():
    with _solve_lock:
        body = request.get_json(silent=True) or {}
        _clear_progress()
        _drain_interrupt()
        _set_timeout(body.get("timeoutMs"))
        gen = _begin_solve(body.get("clientRequestId"))
        try:
            return _solve_impl()
        except SolveCancelled:
            # 200, not an error status: the client asked for this. It has usually
            # dropped the connection by now, but bench scripts and curl still get
            # a straight answer instead of a stack trace.
            return jsonify({
                "status": "cancelled", "reason": "cancelled", "generation": gen,
                "detail": "Solve cancelled at the client's request",
            })
        finally:
            _end_solve()
            _clear_progress()


@app.route("/cancel", methods=["POST"])
def cancel():
    """Abandon the solve currently running. Deliberately outside _solve_lock —
    that lock is held by the very solve being cancelled, so waiting for it would
    deadlock until the solve finished, which is exactly what this avoids.

    Optional body {"clientRequestId": "..."} names the solve the caller means to
    stop. This matters: the client fires /cancel and then sends its replacement
    /solve, and if the doomed solve happens to finish in between, an unqualified
    cancel would land on the innocent replacement instead. With an id, a mismatch
    is simply refused."""
    global _cancel_gen
    want = (request.get_json(silent=True) or {}).get("clientRequestId")
    with _cancel_lock:
        if not _solve_running:
            return jsonify({"cancelled": False, "detail": "no solve in flight"})
        if want is not None and _solve_client_id is not None and want != _solve_client_id:
            return jsonify({"cancelled": False,
                            "detail": "the solve now running is a different request"})
        if _cancel_gen == _solve_gen:
            return jsonify({"cancelled": True, "generation": _solve_gen,
                            "detail": "already cancelled; it is unwinding"})
        _cancel_gen = _solve_gen
        gen, interrupt_now = _solve_gen, _in_check
    # Only interrupt if Z3 is actually inside a check. Otherwise the flag would
    # sit on the context unconsumed; the _check_cancelled() polls will catch this
    # one at the next gap, and _drain_interrupt clears up any that slips through.
    if interrupt_now:
        main_ctx().interrupt()
    return jsonify({"cancelled": True, "generation": gen})


@app.route("/progress", methods=["GET"])
def progress():
    # Deliberately outside _solve_lock — this must respond immediately while
    # a solve is in flight on another thread (see threaded=True below).
    with _progress_lock:
        p = dict(_progress)
    started_at = p.pop("started_at", None)
    p["elapsed_s"] = round(time.monotonic() - started_at, 1) if started_at is not None else None
    p["timeout_s"] = _timeout_ms() / 1000
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
    optimize_prox  = data.get("optimizeProximity",    False)
    if not isinstance(optimize_util,  bool): optimize_util  = False
    if not isinstance(optimize_prior, bool): optimize_prior = False
    if not isinstance(optimize_prox,  bool): optimize_prox  = False

    try:
        w_util  = float(data.get("weightUtilitarian",  1.0))
        w_prior = float(data.get("weightPrioritarian", 1.0))
        w_prox  = float(data.get("weightProximity",    1.0))
    except (TypeError, ValueError):
        w_util, w_prior, w_prox = 1.0, 1.0, 1.0
    if w_util  < 0: w_util  = 0.0
    if w_prior < 0: w_prior = 0.0
    if w_prox  < 0: w_prox  = 0.0

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

    # ── Proximity weights ─────────────────────────────────────────────────────
    # Two ways in, explicit wins: a client-supplied per-station vector, or a
    # vertiport list the server layers outward from with base**layer. The explicit
    # form is what a frontend uses when it wants a different distance metric than
    # the flight adjacency (Manhattan, say) — the solver never needs to know which.
    proximity_weights  = None
    derived_proximity  = False
    proximity_mode      = "noise"
    proximity_noise_ref = None
    if optimize_prox:
        raw_pw = data.get("proximityWeights")
        if raw_pw is not None:
            if not isinstance(raw_pw, list) or len(raw_pw) != M:
                return jsonify({"error": f"proximityWeights must be a list of length M={M}"}), 400
            try:
                proximity_weights = [float(w) for w in raw_pw]
            except (TypeError, ValueError):
                return jsonify({"error": "proximityWeights values must be numeric"}), 400
            if any(w < 0 for w in proximity_weights):
                return jsonify({"error": "proximityWeights values must be non-negative"}), 400
        else:
            vertiport_stations = data.get("vertiportStations", [])
            if not isinstance(vertiport_stations, list) or len(vertiport_stations) == 0:
                return jsonify({"error": "vertiportStations must be a non-empty list when optimizeProximity is true (or pass proximityWeights directly)"}), 400
            try:
                vertiport_stations = [int(v) for v in vertiport_stations]
            except (TypeError, ValueError):
                return jsonify({"error": "vertiportStations must be a list of integers"}), 400
            if any(v < 1 or v > M for v in vertiport_stations):
                return jsonify({"error": f"vertiportStations must be between 1 and M={M}"}), 400

            try:
                prox_base = float(data.get("proximityBase", 3.0))
            except (TypeError, ValueError):
                return jsonify({"error": "proximityBase must be numeric"}), 400
            if prox_base <= 0:
                return jsonify({"error": "proximityBase must be > 0"}), 400

            raw_ml = data.get("proximityMaxLayer", None)
            prox_max_layer = None
            if raw_ml is not None:
                try:
                    prox_max_layer = int(raw_ml)
                except (TypeError, ValueError):
                    return jsonify({"error": "proximityMaxLayer must be an integer"}), 400
                if prox_max_layer < 0:
                    return jsonify({"error": "proximityMaxLayer must be >= 0"}), 400

            proximity_weights, proximity_layers = proximity_weights_from_vertiports(
                adjacency, vertiport_stations, M, prox_base, prox_max_layer
            )
            derived_proximity = True

        # How the burden is priced. Defaults to "noise" — weight x the dB increase the
        # station suffers — so a client that sends nothing gets the noise term, which
        # is Proportional's shipped behaviour since 2026-09-03. "count" reproduces the
        # older weight x occupancy term: cheaper for Z3 by roughly 28x, and the mode in
        # which the participants' ranking has the most influence over the routing. See
        # the long note in optimize_objectives for the trade.
        proximity_mode = data.get("proximityMode", "noise")
        if proximity_mode not in ("noise", "count"):
            return jsonify({"error": "proximityMode must be 'noise' or 'count'"}), 400

        # Optional: price every station off ONE ambient level instead of its own, so
        # the dB curve stops re-expressing a caller's ambient-noise weighting. See the
        # long note in optimize_objectives for why that matters.
        raw_ref = data.get("proximityNoiseRef", None)
        if raw_ref is not None:
            if proximity_mode != "noise":
                return jsonify({"error": "proximityNoiseRef only applies when proximityMode is 'noise'"}), 400
            try:
                proximity_noise_ref = float(raw_ref)
            except (TypeError, ValueError):
                return jsonify({"error": "proximityNoiseRef must be numeric"}), 400
            # Range-checked because the failure is silent, not loud: a reference far
            # above the aircraft level makes every station's increase round to zero,
            # which would quietly delete the objective rather than raise anything.
            if not (0 < proximity_noise_ref <= 200):
                return jsonify({"error": "proximityNoiseRef must be an ambient level in dB, in (0, 200]"}), 400

        # base**layer grows fast on a deep graph; a runaway vector would swamp every
        # other objective and bloat the Z3 coefficients rather than fail outright.
        if max(proximity_weights) > 1e7:
            return jsonify({
                "error": (
                    f"proximity weights reach {max(proximity_weights):.3g}, which would dominate all "
                    f"other objectives — lower proximityBase or set proximityMaxLayer"
                )
            }), 400

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

    # ── Alternative-routing enumeration (opt-in) ──────────────────────────────
    # `enumerate`: how many routings to return, the first being the one /solve would
    # have returned on its own. 0 (the default) keeps the reply exactly as it was.
    # Capped because every extra routing is another Z3 check and the reply carries a
    # full count and noise matrix per entry.
    enumerate_n = data.get("enumerate", 0)
    try:
        enumerate_n = int(enumerate_n)
    except (TypeError, ValueError):
        return jsonify({"error": "enumerate must be an integer"}), 400
    if enumerate_n < 0:
        return jsonify({"error": "enumerate must be >= 0"}), 400
    if enumerate_n > 50:
        return jsonify({"error": "enumerate must be <= 50"}), 400

    enumerate_distinct = data.get("enumerateDistinct", "counts")
    if enumerate_distinct not in ("counts", "paths"):
        return jsonify({"error": "enumerateDistinct must be 'counts' or 'paths'"}), 400

    enumerate_at_optimum = data.get("enumerateAtOptimum", True)
    if not isinstance(enumerate_at_optimum, bool):
        enumerate_at_optimum = True

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
    except SolveCancelled:
        raise   # not an error — must reach solve()'s handler, not become a 500
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

    # enumerate_n is in here because the enumeration lives in phase 2: under hard T
    # with no objective, phase 2 would otherwise be skipped entirely and a caller
    # asking for alternatives would silently get one route.
    should_optimize = (optimize_util or optimize_prior or optimize_prox or soft_T
                       or enumerate_n > 0)
    if result["status"] != "sat" or not should_optimize:
        return jsonify(result)

    T_for_phase2 = result["T"] if hard_T else T_max

    try:
        opt_result = optimize_objectives(
            N, T_for_phase2, M, D, U, adjacency, start_positions, end_positions,
            optimize_util, optimize_prior, optimize_prox,
            protected_stations, proximity_weights,
            w_util, w_prior, w_prox,
            soft_T, w_time,
            station_transit_weights,
            util_noise_mode,
            aircraft_multipliers,
            baseline, aircraft_dB,
            proximity_mode=proximity_mode,
            proximity_noise_ref=proximity_noise_ref,
            enumerate_n=enumerate_n,
            enumerate_distinct=enumerate_distinct,
            enumerate_at_optimum=enumerate_at_optimum
        )
    except SolveCancelled:
        raise   # not an error — must reach solve()'s handler, not become a 500
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
        # These lead with the consequence, not the cause. The dashboard collapses
        # long messages to their first sentence, and more to the point a reader
        # skimming a warning must not have to reach sentence three to learn that
        # the map in front of them ignores the choices they just made.
        #
        # Reaching here now means Z3 found NOTHING — an incumbent would have been
        # salvaged and returned as a partial sat result — so the message no longer
        # has to hedge about what the route does or does not reflect.
        principle = _principle_name(optimize_prox, optimize_prior, optimize_util,
                                    util_noise_mode, station_transit_weights is not None)
        # The returned paths are PHASE 1's, so they are result["T"] long, not
        # T_for_phase2. Quoting the phase-2 horizon named a number that the route in
        # the reply does not have.
        T_returned = result["T"]
        if principle is None:
            lead = ("Your noise limit is still enforced, but arrival times were not "
                    "optimized. No fairness objective was active — this rule is the hard "
                    "D/U cap, which phase 1 applied — so the routing below is valid. ")
        else:
            lead = (f"This routing does NOT apply {principle}. Phase-2 optimization failed, "
                    f"so the map shows a plain feasible route that ignores it. ")
        if opt_result["reason"] == "timeout":
            detail = lead + (
                f"It ran out of time after {_timeout_ms() // 1000}s at T={T_for_phase2} "
                f"without reaching any solution at all; the route shown is phase 1's at "
                f"T={T_returned}. Raise the time limit in Admin, or tighten D/U, lower "
                f"T_max, reduce the station weight, or reduce N/aircraft multipliers."
            )
        else:
            detail = lead + (
                f"It unexpectedly found no solution at T={T_for_phase2} despite phase 1 "
                f"confirming feasibility at T={T_returned}."
            )
        # Machine-readable, so a caller never has to parse the sentence above.
        result["warning"]           = detail
        result["objectiveMode"]      = OBJECTIVE_MODE
        result["optimality"]         = "none"
        # Nothing was optimized, so this is False even though an objective was
        # configured; principleImposed just below is what says whether the routing
        # still honours what was asked for.
        result["principleOptimized"] = False
        result["phase2Failed"]       = True
        result["phase2FailReason"]   = opt_result["reason"]
        result["principleImposed"]   = principle is None
        return jsonify(result)

    opt_result["T_min"] = result["T"]
    # Set on every phase-2 success too, so a caller reads flags rather than probing
    # for a missing key. principleImposed answers "does this routing honour what was
    # asked for?" — yes here, including for Equal/Sufficientarian, whose rule is the
    # hard cap rather than an objective. That is a different question from
    # principleOptimized, which asks whether an objective term existed at all.
    opt_result["phase2Failed"]     = False
    opt_result["principleImposed"] = True
    if opt_result.get("optimality") == "partial":
        # Deliberately a notice and not a warning: the objective WAS applied, Z3 just
        # could not prove the answer best before the clock ran out. The map on screen
        # does reflect the choices made, so alarming language would be wrong here.
        subject = _principle_name(optimize_prox, optimize_prior, optimize_util,
                                  util_noise_mode, station_transit_weights is not None)
        if subject is None:
            subject = "the arrival-time tie-break"
        opt_result["notice"] = (
            f"This routing DOES apply {subject}, but it is the best found within "
            f"{_timeout_ms() // 1000}s rather than a proven best. A longer time limit in "
            f"Admin may turn up a slightly better one; the noise limits are exact either way."
        )
    if derived_proximity and opt_result.get("status") == "sat":
        # Only for the server-derived path: with a client-supplied vector the caller
        # already knows the weights, but here it otherwise cannot see what was priced.
        opt_result["proximityWeights"] = proximity_weights
        opt_result["proximityLayers"]  = proximity_layers
    return jsonify(opt_result)


if __name__ == "__main__":
    # threaded=True so GET /progress can be served while a POST /solve is in
    # flight. This is safe: /progress never touches Z3 or _solve_lock, only
    # the separate lightweight _progress_lock.
    app.run(port=5051, debug=True, threaded=True)
