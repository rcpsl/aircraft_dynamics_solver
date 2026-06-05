from math import ceil
from collections import deque, Counter
from flask import Flask, request, jsonify
from flask_cors import CORS
from z3 import Int, And, Or, Implies, Sum, If, Solver, Bool, sat

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

    result = find_min_T(N, M, D, U, adjacency, start_positions, end_positions)
    return jsonify(result)


if __name__ == "__main__":
    app.run(port=5050, debug=True)
