from z3 import *

# Problem parameters
N = 2   # number of aircraft
T = 7   # time horizon  (times 0..T-1)
M = 5   # number of stations (labels 1..M)

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
end_positions   = [5, 5]   # aircraft 0 ends   at 5, aircraft 1 ends   at 5


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

# ── Constraint 2: start and end positions ────────────────────────────────────
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

# Solve and display 
if s.check() == sat:
    m = s.model()
    print("Solution found!\n")
    for i in range(N):
        path = [m[L[i][t]].as_long() for t in range(T)]
        print(f"  Aircraft {i}: {path}")
else:
    print("No valid schedule exists (unsat).")