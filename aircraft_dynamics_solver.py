from z3 import *

# Problem parameters
N = 2   # number of aircraft
T = 7   # time horizon  (times 0..T-1)
M = 5   # number of stations (labels 1..M)
D = 1   # max noise level allowed at any station at any time
U = 2   # max noise difference between adjacent stations

# Adjacency matrix (0-indexed): adj[a][b] = 1 means station a+1 -> b+1 is OK
adjacency = [
    [1, 1, 0, 0, 0],
    [0, 1, 1, 0, 0],
    [0, 0, 1, 1, 0],
    [0, 0, 0, 1, 1],
    [0, 0, 0, 0, 1],
]

# Predefined start and end positions (1-indexed, length = N)
start_positions = [1, 3]   # aircraft 0 starts at 1, aircraft 1 starts at 3
end_positions   = [4, 5]   # aircraft 0 ends   at 5, aircraft 1 ends   at 5


def valid_next_locations(src_1indexed):
    src = src_1indexed - 1
    return [dst + 1 for dst in range(M) if adjacency[src][dst] == 1]

# Decision variables
# L[i][t] = location (1..M) of aircraft i at time t
L = [[Int("L_%d_%d" % (i, t)) for t in range(T)] for i in range(N)]

s = Solver()


# Constraint 1: bounds
s.add([And(1 <= L[i][t], L[i][t] <= M)
       for i in range(N) for t in range(T)])

# Constraint 2: start and end positions 

s.add([L[i][0]    == start_positions[i] for i in range(N)])
s.add([L[i][T-1]  == end_positions[i]   for i in range(N)])

# Constraint 3: valid movement along graph edges
for i in range(N):
    for t in range(T - 1):
        for src in range(1, M + 1):
            dsts = valid_next_locations(src)
            s.add(Implies(
                L[i][t] == src,
                Or([L[i][t+1] == dst for dst in dsts])
            ))

# Build symbolic noise matrix C (size M x T) 
# C[m][t] = sum of noise contributions from all aircraft at station m+1 at time t
# Each aircraft contributes noise_level=1 when it is at that station (via Z3 If)
noise_level = 1

C = [
    [
        Sum([If(L[i][t] == m + 1, noise_level, 0) for i in range(N)])
        for t in range(T)
    ]
    for m in range(M)
]

# Constraint 4: noise cap — C[m][t] <= D for all stations and times
s.add([C[m][t] <= D for m in range(M) for t in range(T)])

# Constraint 5: adjacent station noise difference <= 2
# Collect unique undirected adjacent pairs (m1, m2) with m1 < m2
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

# Solve and print results
if s.check() == sat:
    m_sol = s.model()

    # Extract paths
    paths = [[m_sol[L[i][t]].as_long() for t in range(T)] for i in range(N)]

    print("Aircraft schedules:")
    for i in range(N):
        print(f"  Aircraft {i}: {paths[i]}")

    # Evaluate C numerically for printing
    C_vals = [[m_sol.evaluate(C[m][t]).as_long() for t in range(T)] for m in range(M)]

    print("\nNoise matrix C (rows = stations 1..M, cols = time 0..T-1):")
    print("           " + "   ".join(f"t={t}" for t in range(T)))
    for loc in range(M):
        row_str = "  ".join(f"{C_vals[loc][t]:4d}" for t in range(T))
        print(f"  stn {loc+1}: {row_str}")

else:
    print("No valid schedule exists (unsat).")