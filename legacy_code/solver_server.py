from flask import Flask, request, jsonify
from flask_cors import CORS
from z3 import Int, And, Or, Implies, Sum, If, Solver, sat

app = Flask(__name__)
CORS(app)


def run_solver(N, T, M, D, U, adjacency, start_positions, end_positions):
    def valid_next_locations(src_1indexed):
        src = src_1indexed - 1
        return [dst + 1 for dst in range(M) if adjacency[src][dst] == 1]

    L = [[Int("L_%d_%d" % (i, t)) for t in range(T)] for i in range(N)]

    s = Solver()

    # Constraint 1: bounds
    s.add([And(1 <= L[i][t], L[i][t] <= M)
           for i in range(N) for t in range(T)])

    # Constraint 2: start and end positions
    s.add([L[i][0]   == start_positions[i] for i in range(N)])
    s.add([L[i][T-1] == end_positions[i]   for i in range(N)])

    # Constraint 3: valid movement along graph edges
    for i in range(N):
        for t in range(T - 1):
            for src in range(1, M + 1):
                dsts = valid_next_locations(src)
                s.add(Implies(
                    L[i][t] == src,
                    Or([L[i][t+1] == dst for dst in dsts])
                ))

    # Symbolic noise matrix C[m][t]
    noise_level = 1
    C = [
        [Sum([If(L[i][t] == m + 1, noise_level, 0) for i in range(N)])
         for t in range(T)]
        for m in range(M)
    ]

    # Constraint 4: noise cap
    s.add([C[m][t] <= D for m in range(M) for t in range(T)])

    # Constraint 5: adjacent noise difference
    adjacent_pairs = set()
    for m1 in range(M):
        for m2 in range(M):
            if m1 != m2 and adjacency[m1][m2] == 1:
                adjacent_pairs.add((min(m1, m2), max(m1, m2)))

    s.add([
        And(C[m1][t] - C[m2][t] <= U,
            C[m2][t] - C[m1][t] <= U)
        for (m1, m2) in adjacent_pairs
        for t in range(T)
    ])

    if s.check() == sat:
        model = s.model()
        paths = [[model[L[i][t]].as_long() for t in range(T)] for i in range(N)]
        noise_matrix = [[model.evaluate(C[m][t]).as_long() for t in range(T)] for m in range(M)]
        return {"status": "sat", "paths": paths, "noiseMatrix": noise_matrix}
    else:
        return {"status": "unsat"}


@app.route("/solve", methods=["POST"])
def solve():
    data = request.get_json(force=True)
    try:
        N             = int(data["N"])
        T             = int(data["T"])
        M             = int(data["M"])
        D             = int(data["D"])
        U             = int(data["U"])
        adjacency     = data["adjacency"]
        start_positions = data["startPositions"]
        end_positions   = data["endPositions"]
    except (KeyError, TypeError, ValueError) as e:
        return jsonify({"error": f"Bad input: {e}"}), 400

    result = run_solver(N, T, M, D, U, adjacency, start_positions, end_positions)
    return jsonify(result)


if __name__ == "__main__":
    app.run(port=5050, debug=True)
