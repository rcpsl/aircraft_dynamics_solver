from math import ceil
from collections import deque, Counter
from flask import Flask, request, jsonify
from flask_cors import CORS
from z3 import Int, And, Or, Not, Implies, Sum, If, Solver, Optimize, Bool, sat

app = Flask(__name__)
CORS(app)


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


def find_min_T(N, M, D, U, adjacency, start_positions, end_positions):
    # ── Suggestion 1: algebraic pre-checks (O(1), no Z3 needed) ─────────────

    # Pigeonhole: if N aircraft must spread across M stations, the minimum
    # occupancy per station is ⌈N/M⌉; if that exceeds D, no schedule exists.
    if ceil(N / M) > D:
        return {
            "status": "unsat", "reason": "noise_cap",
            "detail": f"⌈{N}/{M}⌉ = {ceil(N/M)} aircraft minimum per station exceeds D={D}"
        }

    # Start-position conflict: if any station hosts more aircraft at t=0
    # than D allows, the problem is immediately infeasible.
    start_counts = Counter(start_positions)
    worst_start = max(start_counts.values(), default=0)
    if worst_start > D:
        busiest = start_counts.most_common(1)[0][0]
        return {
            "status": "unsat", "reason": "start_conflict",
            "detail": f"Station {busiest} has {worst_start} aircraft at t=0, exceeding D={D}"
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

    # ── Suggestions 2 & 3: incremental solver + unsat-core early exit ────────

    def valid_next(src_1indexed):
        s0 = src_1indexed - 1
        return [dst + 1 for dst in range(M) if adjacency[s0][dst] == 1]

    adjacent_pairs = set()
    for m1 in range(M):
        for m2 in range(M):
            if m1 != m2 and adjacency[m1][m2] == 1:
                adjacent_pairs.add((min(m1, m2), max(m1, m2)))

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

    # Noise cap + adjacent disparity for t = 0 … T_lower-1
    # C_by_t[t][m] = symbolic aircraft count at station m at time t
    C_by_t = []
    for t in range(T_lower):
        C_t = [Sum([If(L[i][t] == m + 1, 1, 0) for i in range(N)]) for m in range(M)]
        C_by_t.append(C_t)
        s.add([C_t[m] <= D for m in range(M)])
        for (m1, m2) in adjacent_pairs:
            s.add(And(C_t[m1] - C_t[m2] <= U, C_t[m2] - C_t[m1] <= U))

    T_current = T_lower

    # Each iteration: try endpoint pins at t = T_current-1 via assumptions,
    # then extend the base by one timestep if needed.
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
            noise_matrix = [
                [model.evaluate(C_by_t[t][m]).as_long() for t in range(T_current)]
                for m in range(M)
            ]
            s.pop()
            return {"status": "sat", "T": T_current, "paths": paths, "noiseMatrix": noise_matrix}

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
        s.add([C_new[m] <= D for m in range(M)])
        for (m1, m2) in adjacent_pairs:
            s.add(And(C_new[m1] - C_new[m2] <= U, C_new[m2] - C_new[m1] <= U))

        T_current += 1

    return {"status": "unsat", "reason": "timeout", "detail": "No solution found within T=50"}


def optimize_objectives(N, T, M, D, U, adjacency, start_positions, end_positions,
                        optimize_util, optimize_prior,
                        protected_stations, w_util, w_prior):
    """Phase-2 optimizer: rebuild all constraints in a fresh Optimize instance and
    minimize a weighted combination of transit time and protected-station noise.

    NOTE: z3.Optimize is slower than z3.Solver. For large N, T, or M this phase
    may take several seconds. T is fixed to the value found in phase 1.
    """
    # ── Metric normalization ──────────────────────────────────────────────────
    # Both metrics are divided by their theoretical maximums so that w_util and
    # w_prior operate on a comparable [0,1] scale regardless of N, T, M, D.
    #
    # Scale note: max_transit = N*(T-1), max_protected = |protected|*T*D.
    # If either denominator is 0, that term is inactive regardless of the flag.
    max_transit   = N * (T - 1)
    max_protected = len(protected_stations) * T * D

    # After normalization, both coefficients are dimensionless and comparable,
    # so w_util = w_prior = 1.0 gives genuinely equal weighting.
    eff_w_util  = (w_util  / max_transit)   if (optimize_util  and max_transit   > 0) else 0.0
    eff_w_prior = (w_prior / max_protected) if (optimize_prior and max_protected > 0) else 0.0

    def valid_next(src_1indexed):
        s0 = src_1indexed - 1
        return [dst + 1 for dst in range(M) if adjacency[s0][dst] == 1]

    adjacent_pairs = set()
    for m1 in range(M):
        for m2 in range(M):
            if m1 != m2 and adjacency[m1][m2] == 1:
                adjacent_pairs.add((min(m1, m2), max(m1, m2)))

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

    # Noise cap and adjacent disparity
    C_by_t = []
    for t in range(T):
        C_t = [Sum([If(L[i][t] == m + 1, 1, 0) for i in range(N)]) for m in range(M)]
        C_by_t.append(C_t)
        opt.add([C_t[m] <= D for m in range(M)])
        for (m1, m2) in adjacent_pairs:
            opt.add(And(C_t[m1] - C_t[m2] <= U, C_t[m2] - C_t[m1] <= U))

    # ── Build objective terms ─────────────────────────────────────────────────
    objective_terms = []

    # Declare result variables in outer scope so the result block can read them
    transit = None
    total_transit = None
    protected_noise = None

    if eff_w_util > 0:
        # hm[i][t]: aircraft i has changed location at least once in t'=1..t
        # ha[i][t]: aircraft i has reached end_positions[i] at some t'=0..t
        # it[i][t]: aircraft i is currently accumulating transit cost at time t
        hm = [[Bool(f"o_hm_{i}_{t}") for t in range(T)] for i in range(N)]
        ha = [[Bool(f"o_ha_{i}_{t}") for t in range(T)] for i in range(N)]
        it = [[Bool(f"o_it_{i}_{t}") for t in range(T)] for i in range(N)]

        for i in range(N):
            opt.add(hm[i][0] == False)
            opt.add(ha[i][0] == (L[i][0] == end_positions[i]))
            opt.add(it[i][0] == False)
            for t in range(1, T):
                opt.add(hm[i][t] == Or(hm[i][t - 1], L[i][t] != L[i][t - 1]))
                opt.add(ha[i][t] == Or(ha[i][t - 1], L[i][t] == end_positions[i]))
                # Arrival timestep IS counted — gate on t-1 arrival, not t
                opt.add(it[i][t] == And(hm[i][t], Not(ha[i][t - 1])))

        transit       = [Sum([If(it[i][t], 1, 0) for t in range(T)]) for i in range(N)]
        total_transit = Sum(transit)
        objective_terms.append(eff_w_util * total_transit)

    if eff_w_prior > 0:
        protected_noise = Sum([
            C_by_t[t][p - 1]
            for p in protected_stations
            for t in range(T)
        ])
        objective_terms.append(eff_w_prior * protected_noise)

    opt.minimize(Sum(objective_terms))

    if opt.check() != sat:
        return None  # should not happen: phase-1 already confirmed sat at this T

    model = opt.model()
    paths = [
        [model[L[i][t]].as_long() for t in range(T)]
        for i in range(N)
    ]
    noise_matrix = [
        [model.evaluate(C_by_t[t][m]).as_long() for t in range(T)]
        for m in range(M)
    ]

    result = {"status": "sat", "T": T, "paths": paths, "noiseMatrix": noise_matrix}

    if eff_w_util > 0:
        result["transitTimes"] = [model.evaluate(transit[i]).as_long() for i in range(N)]
        result["totalTransit"] = model.evaluate(total_transit).as_long()

    if eff_w_prior > 0:
        result["protectedNoise"]    = model.evaluate(protected_noise).as_long()
        result["protectedStations"] = protected_stations

    return result


@app.route("/solve", methods=["POST"])
def solve():
    data = request.get_json(force=True)
    try:
        N               = int(data["N"])
        M               = int(data["M"])
        D               = int(data["D"])
        U               = int(data["U"])
        adjacency       = data["adjacency"]
        start_positions = data["startPositions"]
        end_positions   = data["endPositions"]
    except (KeyError, TypeError, ValueError) as e:
        return jsonify({"error": f"Bad input: {e}"}), 400

    optimize_util  = data.get("optimizeUtilitarian",  False)
    optimize_prior = data.get("optimizePrioritarian", False)
    if not isinstance(optimize_util,  bool): optimize_util  = False
    if not isinstance(optimize_prior, bool): optimize_prior = False

    try:
        w_util  = float(data.get("weightUtilitarian",  1.0))
        w_prior = float(data.get("weightPrioritarian", 1.0))
    except (TypeError, ValueError):
        w_util, w_prior = 1.0, 1.0
    if w_util  < 0: w_util  = 0.0
    if w_prior < 0: w_prior = 0.0

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

    result = find_min_T(N, M, D, U, adjacency, start_positions, end_positions)

    should_optimize = optimize_util or optimize_prior
    if result["status"] != "sat" or not should_optimize:
        return jsonify(result)

    opt_result = optimize_objectives(
        N, result["T"], M, D, U, adjacency, start_positions, end_positions,
        optimize_util, optimize_prior,
        protected_stations, w_util, w_prior
    )
    if opt_result is None:
        # Phase-2 unexpectedly returned unsat — fall back to phase-1 result
        return jsonify(result)
    return jsonify(opt_result)


if __name__ == "__main__":
    app.run(port=5050, debug=True)
