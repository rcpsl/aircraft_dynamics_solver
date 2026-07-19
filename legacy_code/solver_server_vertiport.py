# vertiport placement solver — port 5052
# Brute-force enumeration over all C(Z,K) subsets; no Z3 needed.
from collections import deque
from itertools import combinations
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


def bfs_shortest_path(adjacency, src, dst, Z):
    """BFS shortest path from src to dst (0-indexed). Returns zone list or None."""
    if src == dst:
        return [src]
    parent = [-1] * Z
    parent[src] = src
    queue = deque([src])
    while queue:
        node = queue.popleft()
        for nb in range(Z):
            if adjacency[node][nb] and parent[nb] == -1:
                parent[nb] = node
                if nb == dst:
                    path, cur = [], dst
                    while cur != src:
                        path.append(cur)
                        cur = parent[cur]
                    path.append(src)
                    return list(reversed(path))
                queue.append(nb)
    return None


def precompute_paths(adjacency, Z):
    """paths[i][j] = shortest directed path from i to j, or None. i==j → None."""
    return [
        [bfs_shortest_path(adjacency, i, j, Z) if i != j else None for j in range(Z)]
        for i in range(Z)
    ]


def score_placement(subset, paths, pop_level, jobs_level, w_pop, w_jobs, w_noise):
    """Weighted objective for a given subset of zone indices.
    Noise cost per route = sum of pop_level[z] for each zone z on the path,
    so routes flying over high-population zones are penalised more."""
    total = 0.0
    for i in subset:
        for j in subset:
            if i != j and paths[i][j] is not None:
                noise_cost = sum(pop_level[z] for z in paths[i][j])
                total += w_pop * pop_level[i] + w_jobs * jobs_level[j] - w_noise * noise_cost
    return total


@app.route("/solve", methods=["POST"])
def solve():
    data = request.get_json(force=True)
    try:
        Z          = int(data["Z"])
        K          = int(data["K"])
        adjacency  = data["adjacency"]
        pop_level  = [int(v) for v in data["popLevel"]]
        jobs_level = [int(v) for v in data["jobsLevel"]]
    except (KeyError, TypeError, ValueError) as e:
        return jsonify({"error": f"Bad input: {e}"}), 400

    if Z < 1:
        return jsonify({"error": "Z must be >= 1"}), 400
    if K < 1 or K > Z:
        return jsonify({"error": f"K must be between 1 and Z={Z}"}), 400
    if not isinstance(adjacency, list) or len(adjacency) != Z or \
            any(not isinstance(r, list) or len(r) != Z for r in adjacency):
        return jsonify({"error": f"adjacency must be a {Z}×{Z} matrix"}), 400
    if len(pop_level) != Z or len(jobs_level) != Z:
        return jsonify({"error": f"popLevel and jobsLevel must each have length Z={Z}"}), 400
    if any(v not in (1, 2, 3) for v in pop_level):
        return jsonify({"error": "popLevel values must be 1, 2, or 3"}), 400
    if any(v not in (1, 2, 3) for v in jobs_level):
        return jsonify({"error": "jobsLevel values must be 1, 2, or 3"}), 400

    try:
        w_pop   = max(0.0, float(data.get("weightPop",   1.0)))
        w_jobs  = max(0.0, float(data.get("weightJobs",  1.0)))
        w_noise = max(0.0, float(data.get("weightNoise", 1.0)))
    except (TypeError, ValueError):
        w_pop = w_jobs = w_noise = 1.0

    paths = precompute_paths(adjacency, Z)

    # Enumerate all C(Z, K) subsets — for Z=16 worst case is C(16,8)=12,870, fast in Python.
    best_score = float("-inf")
    best_subset = None
    for subset in combinations(range(Z), K):
        s = score_placement(subset, paths, pop_level, jobs_level, w_pop, w_jobs, w_noise)
        if s > best_score:
            best_score = s
            best_subset = subset

    vertiports = list(best_subset)

    # ── Output metrics ────────────────────────────────────────────────────────
    routes = [
        {"from": i, "to": j, "path": paths[i][j]}
        for i in vertiports for j in vertiports
        if paths[i][j] is not None
    ]
    pop_benefit = sum(
        pop_level[i]
        for i in vertiports for j in vertiports
        if paths[i][j] is not None
    )
    jobs_benefit = sum(
        jobs_level[j]
        for i in vertiports for j in vertiports
        if paths[i][j] is not None
    )
    # Noise per zone: route-leg count multiplied by pop_level[z] — high-pop zones
    # suffer more from the same number of overflights.
    noise_per_zone = [
        pop_level[z] * sum(
            1 for i in vertiports for j in vertiports
            if paths[i][j] is not None and z in paths[i][j]
        )
        for z in range(Z)
    ]
    total_noise = sum(noise_per_zone)

    # ── Option B: routing pipeline parameters ─────────────────────────────────
    # K×K adjacency sub-matrix over the chosen vertiports, ready to pass to the
    # dB aircraft routing solver (port 5051). Vertiport vertiports[a] becomes
    # station a+1 (1-indexed) in the routing solver.
    station_adjacency = [
        [adjacency[vertiports[a]][vertiports[b]] for b in range(K)]
        for a in range(K)
    ]

    return jsonify({
        "status": "sat",
        "vertiports": vertiports,
        "routes": routes,
        "popBenefit": pop_benefit,
        "jobsBenefit": jobs_benefit,
        "noisePerZone": noise_per_zone,
        "totalNoise": total_noise,
        "objective": best_score,
        "stationAdjacency": station_adjacency,
    })


if __name__ == "__main__":
    app.run(port=5052, debug=True)
