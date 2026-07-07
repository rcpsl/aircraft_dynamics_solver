# dB-based variant of solver_server.py — runs on port 5051
import math
from math import ceil
from collections import deque, Counter
from flask import Flask, request, jsonify
from flask_cors import CORS
from z3 import Int, And, Or, Not, Implies, Sum, If, Solver, Optimize, Bool, sat

app = Flask(__name__)
CORS(app)

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


def make_dB_expr(count_expr, m, scaled_table, N):
    """
    Returns a Z3 ArithRef: the scaled dB increase at station m given count_expr aircraft.
    Uses an If-chain over all possible counts 0..N.
    count_expr is a Z3 ArithRef (integer aircraft count at station m at some timestep).
    """
    expr = scaled_table[m][0]   # n=0 → 0 increase
    for n in range(1, N + 1):
        expr = If(count_expr == n, scaled_table[m][n], expr)
    return expr


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


def find_min_T(N, M, D, U, adjacency, start_positions, end_positions, baseline, aircraft_dB):
    scaled_table = build_scaled_table(M, N, baseline, aircraft_dB)
    D_scaled = round(D * SCALE)
    U_scaled = round(U * SCALE)

    # ── Algebraic pre-checks (exact or O(M²), no Z3 needed) ─────────────────

    # all_pairs needed below for U checks
    all_pairs = [(m1, m2) for m1 in range(M) for m2 in range(m1 + 1, M)]

    # Pigeonhole: at every timestep some station must hold ≥⌈N/M⌉ aircraft.
    # The best-case station for the D constraint is the one with the highest
    # baseline (lowest dB increase per aircraft). If even that station exceeds D
    # with ⌈N/M⌉ aircraft, no distribution can satisfy D.
    min_forced_count = ceil(N / M)
    best_m = min(range(M), key=lambda m: scaled_table[m][min_forced_count])
    if scaled_table[best_m][min_forced_count] > D_scaled:
        return {
            "status": "unsat", "reason": "noise_cap",
            "detail": (
                f"Even distributing {N} aircraft across {M} stations forces ≥{min_forced_count} "
                f"at some station; even the most tolerant station "
                f"(baseline {baseline[best_m]:.1f} dBA) would exceed D={D} dBA"
            )
        }

    # Start-position D + U check: t=0 positions are fixed, so dB profile is exact.
    start_counts = Counter(start_positions)
    start_dB = [scaled_table[m][start_counts.get(m + 1, 0)] for m in range(M)]
    for m, inc_scaled in enumerate(start_dB):
        if inc_scaled > D_scaled:
            station = m + 1
            return {
                "status": "unsat", "reason": "start_conflict",
                "detail": (
                    f"Station {station} has {start_counts[station]} aircraft at t=0, "
                    f"causing a dB increase of {inc_scaled / SCALE:.1f} dBA "
                    f"which exceeds D={D} dBA"
                )
            }
    for (m1, m2) in all_pairs:
        diff = abs(start_dB[m1] - start_dB[m2])
        if diff > U_scaled:
            return {
                "status": "unsat", "reason": "start_disparity",
                "detail": (
                    f"At t=0, stations {m1+1} and {m2+1} differ by {diff / SCALE:.1f} dBA "
                    f"({start_dB[m1]/SCALE:.1f} vs {start_dB[m2]/SCALE:.1f}), "
                    f"exceeding U={U} dBA"
                )
            }

    # End-position D + U check: final-timestep positions are also fixed.
    end_counts = Counter(end_positions)
    end_dB = [scaled_table[m][end_counts.get(m + 1, 0)] for m in range(M)]
    for m, inc_scaled in enumerate(end_dB):
        if inc_scaled > D_scaled:
            station = m + 1
            return {
                "status": "unsat", "reason": "end_conflict",
                "detail": (
                    f"Station {station} has {end_counts[station]} aircraft at their final position, "
                    f"causing a dB increase of {inc_scaled / SCALE:.1f} dBA "
                    f"which exceeds D={D} dBA"
                )
            }
    for (m1, m2) in all_pairs:
        diff = abs(end_dB[m1] - end_dB[m2])
        if diff > U_scaled:
            return {
                "status": "unsat", "reason": "end_disparity",
                "detail": (
                    f"At the final timestep, stations {m1+1} and {m2+1} differ by {diff / SCALE:.1f} dBA "
                    f"({end_dB[m1]/SCALE:.1f} vs {end_dB[m2]/SCALE:.1f}), "
                    f"exceeding U={U} dBA"
                )
            }

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

    # Build permanent base state up to T_lower (Suggestion 3: encode once)
    L = [[Int(f"L_{i}_{t}") for t in range(T_lower)] for i in range(N)]
    s = Solver()

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

    # Noise cap + global disparity for t = 0 … T_lower-1
    # C_by_t[t][m] = symbolic aircraft count at station m at time t
    C_by_t = []
    dB_by_t = []
    for t in range(T_lower):
        C_t = [Sum([If(L[i][t] == m + 1, 1, 0) for i in range(N)]) for m in range(M)]
        C_by_t.append(C_t)
        dB_exprs_t = [make_dB_expr(C_t[m], m, scaled_table, N) for m in range(M)]
        dB_by_t.append(dB_exprs_t)
        s.add([dB_exprs_t[m] <= D_scaled for m in range(M)])
        for (m1, m2) in all_pairs:
            s.add(And(
                dB_exprs_t[m1] - dB_exprs_t[m2] <= U_scaled,
                dB_exprs_t[m2] - dB_exprs_t[m1] <= U_scaled
            ))

    T_current = T_lower

    for _ in range(T_lower, 51):
        # Assumption booleans — same names reused safely because the Implies
        # constraints referencing them are pushed/popped each iteration.
        end_asms = [Bool(f"end_{i}") for i in range(N)]

        s.push()
        for i in range(N):
            s.add(Implies(end_asms[i], L[i][T_current - 1] == end_positions[i]))

        result = s.check(*end_asms)

        if result == sat:
            model = s.model()
            paths = [
                [model[L[i][t]].as_long() for t in range(T_current)]
                for i in range(N)
            ]
            noise_matrix_dB = [
                [model.evaluate(dB_by_t[t][m]).as_long() / SCALE for t in range(T_current)]
                for m in range(M)
            ]
            s.pop()
            return {"status": "sat", "T": T_current, "paths": paths, "noiseMatrix": noise_matrix_dB}

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

        if T_current >= 50:
            break

        # ── Suggestion 3: extend base by exactly one timestep ───────────────
        new_t = T_current  # 0-indexed new final timestep

        for i in range(N):
            L[i].append(Int(f"L_{i}_{new_t}"))

        s.add([And(1 <= L[i][new_t], L[i][new_t] <= M) for i in range(N)])

        for i in range(N):
            for src in range(1, M + 1):
                dsts = valid_next(src)
                s.add(Implies(L[i][new_t - 1] == src, Or([L[i][new_t] == dst for dst in dsts])))

        C_new = [Sum([If(L[i][new_t] == m + 1, 1, 0) for i in range(N)]) for m in range(M)]
        C_by_t.append(C_new)
        dB_exprs_new = [make_dB_expr(C_new[m], m, scaled_table, N) for m in range(M)]
        dB_by_t.append(dB_exprs_new)
        s.add([dB_exprs_new[m] <= D_scaled for m in range(M)])
        for (m1, m2) in all_pairs:
            s.add(And(
                dB_exprs_new[m1] - dB_exprs_new[m2] <= U_scaled,
                dB_exprs_new[m2] - dB_exprs_new[m1] <= U_scaled
            ))

        T_current += 1

    return {"status": "unsat", "reason": "timeout", "detail": "No solution found within T=50"}


def optimize_objectives(N, T, M, D, U, adjacency, start_positions, end_positions,
                        optimize_util, optimize_prior, optimize_prop,
                        protected_stations, proportional_stations,
                        w_util, w_prior, w_prop,
                        soft_T, w_time,
                        baseline, aircraft_dB):
    """Phase-2 optimizer: rebuild all constraints in a fresh Optimize instance and
    minimize a weighted combination of transit time and protected-station noise (dB).

    NOTE: z3.Optimize is slower than z3.Solver. For large N, T, or M this phase
    may take several seconds. T is fixed to the value found in phase 1.
    """
    scaled_table = build_scaled_table(M, N, baseline, aircraft_dB)
    D_scaled = round(D * SCALE)
    U_scaled = round(U * SCALE)

    # ── Metric normalization ──────────────────────────────────────────────────
    # All metrics are divided by their theoretical maximums so that weights
    # operate on a comparable scale regardless of N, T, M, D.
    #
    # Transit and T-penalty: count-based, unchanged from the count-based solver.
    # Prioritarian and proportional: dB-based; bounded by all-N-aircraft case
    # at the loudest station.
    max_transit   = N * (T - 1)
    max_T_penalty = N * (T - 1)

    # Use scaled (integer) units for dB normalization bounds so all objective
    # terms live in the same numeric range as the Z3 dB expressions (×SCALE).
    # Mixing unscaled dB bounds with scaled Z3 expressions would make the dB
    # objectives SCALE× heavier than the count-based utilitarian term.
    max_dB_scaled_per_station = max(scaled_table[m][N] for m in range(M))
    max_protected_dB    = len(protected_stations)    * T * max_dB_scaled_per_station
    max_proportional_dB = len(proportional_stations) * T * max_dB_scaled_per_station

    # After normalization, all coefficients are dimensionless and comparable,
    # so w_util = w_prior = w_prop = w_time = 1.0 gives genuinely equal weighting.
    eff_w_util  = (w_util  / max_transit)         if (optimize_util  and max_transit         > 0) else 0.0
    eff_w_prior = (w_prior / max_protected_dB)    if (optimize_prior and max_protected_dB    > 0) else 0.0
    eff_w_prop  = (w_prop  / max_proportional_dB) if (optimize_prop  and max_proportional_dB > 0) else 0.0
    eff_w_time  = (w_time  / max_T_penalty)       if (soft_T         and max_T_penalty        > 0) else 0.0

    def valid_next(src_1indexed):
        s0 = src_1indexed - 1
        return [dst + 1 for dst in range(M) if adjacency[s0][dst] == 1]

    # Global disparity: all station pairs, not just adjacent ones
    all_pairs = [(m1, m2) for m1 in range(M) for m2 in range(m1 + 1, M)]

    opt = Optimize()

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

    # Noise cap and global disparity
    C_by_t = []
    dB_by_t = []
    for t in range(T):
        C_t = [Sum([If(L[i][t] == m + 1, 1, 0) for i in range(N)]) for m in range(M)]
        C_by_t.append(C_t)
        dB_exprs_t = [make_dB_expr(C_t[m], m, scaled_table, N) for m in range(M)]
        dB_by_t.append(dB_exprs_t)
        opt.add([dB_exprs_t[m] <= D_scaled for m in range(M)])
        for (m1, m2) in all_pairs:
            opt.add(And(
                dB_exprs_t[m1] - dB_exprs_t[m2] <= U_scaled,
                dB_exprs_t[m2] - dB_exprs_t[m1] <= U_scaled
            ))

    # ── Build objective terms ─────────────────────────────────────────────────
    objective_terms = []

    # Declare result variables in outer scope so the result block can read them
    transit = None
    total_transit = None
    protected_noise_dB = None
    proportional_noise_dB = None

    # Build ha whenever utilitarian or soft-T needs it
    ha = None
    if eff_w_util > 0 or soft_T:
        ha = [[Bool(f"o_ha_{i}_{t}") for t in range(T)] for i in range(N)]
        for i in range(N):
            opt.add(ha[i][0] == (L[i][0] == end_positions[i]))
            for t in range(1, T):
                opt.add(ha[i][t] == Or(ha[i][t - 1], L[i][t] == end_positions[i]))

    # Sticky arrival: once an aircraft reaches its destination it must stay there.
    # Without this, in soft mode aircraft can drift away between arrival and T-1.
    if soft_T:
        for i in range(N):
            for t in range(T - 1):
                opt.add(Implies(ha[i][t], L[i][t + 1] == end_positions[i]))

    if eff_w_util > 0:
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

        transit       = [Sum([If(it[i][t], 1, 0) for t in range(T)]) for i in range(N)]
        total_transit = Sum(transit)
        objective_terms.append(eff_w_util * total_transit)

    if eff_w_prior > 0:
        protected_noise_dB = Sum([
            dB_by_t[t][p - 1]
            for p in protected_stations
            for t in range(T)
        ])
        objective_terms.append(eff_w_prior * protected_noise_dB)

    if eff_w_prop > 0:
        proportional_noise_dB = Sum([
            dB_by_t[t][b - 1]
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

    opt.minimize(Sum(objective_terms))

    if opt.check() != sat:
        return None  # should not happen: phase-1 already confirmed sat at this T

    model = opt.model()
    paths = [
        [model[L[i][t]].as_long() for t in range(T)]
        for i in range(N)
    ]
    noise_matrix_dB = [
        [model.evaluate(dB_by_t[t][m]).as_long() / SCALE for t in range(T)]
        for m in range(M)
    ]

    result = {"status": "sat", "T": T, "paths": paths, "noiseMatrix": noise_matrix_dB}
    result["T_used"] = T

    if eff_w_util > 0:
        result["transitTimes"] = [model.evaluate(transit[i]).as_long() for i in range(N)]
        result["totalTransit"] = model.evaluate(total_transit).as_long()

    if eff_w_prior > 0:
        result["protectedNoise"]    = model.evaluate(protected_noise_dB).as_long() / SCALE
        result["protectedStations"] = protected_stations

    if eff_w_prop > 0:
        result["proportionalNoise"]    = model.evaluate(proportional_noise_dB).as_long() / SCALE
        result["proportionalStations"] = proportional_stations

    return result


@app.route("/solve", methods=["POST"])
def solve():
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

    result = find_min_T(N, M, D, U, adjacency, start_positions, end_positions, baseline, aircraft_dB)

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

    should_optimize = optimize_util or optimize_prior or optimize_prop or soft_T
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

    opt_result = optimize_objectives(
        N, T_for_phase2, M, D, U, adjacency, start_positions, end_positions,
        optimize_util, optimize_prior, optimize_prop,
        protected_stations, proportional_stations,
        w_util, w_prior, w_prop,
        soft_T, w_time,
        baseline, aircraft_dB
    )
    if opt_result is None:
        # Phase-2 unexpectedly returned unsat — fall back to phase-1 result
        if overlap_warning:
            result["warning"] = overlap_warning
        return jsonify(result)
    opt_result["T_min"] = result["T"]
    if overlap_warning:
        opt_result["warning"] = overlap_warning
    return jsonify(opt_result)


if __name__ == "__main__":
    app.run(port=5051, debug=True)
