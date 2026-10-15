"""Tractability: the one question the surrogate cannot answer.

The surrogate settles which routing a scheme produces (58 of 58 Z3 routings
reproduced). It cannot model how long z3.Optimize takes to prove optimality, and
with a 600 s dashboard budget that is half the decision.

Block A isolates the cost of noise pricing itself. ref:65 is the control that
matters: its routing is identical to count's, so any time difference between
them is the dB If-chains in the objective and nothing else.

Block B tests the only payload-only lever on chain length. Proportional sends
D = 30 dB while the loudest reachable tile is +12.30 dB, so _compute_d_counts
returns 16 for every station and every chain runs all 16 branches. D = 7 cuts
45 dB tiles to 4 branches (dB(45,4)=6.99 <= 7 < 7.78=dB(45,5)); it cannot help
55 or 65 dB tiles, which hold all 16 aircraft under any plausible D, so this
measures how much of the cost lives on the quiet tiles.

par=10 not 14, so each process has headroom. Timings here are comparable across
schemes but not against sweep.jsonl's solo numbers.
"""
import json

RANKINGS = [
    "income|ambient|distance|population",   # dashboard default
    "income|population|distance|ambient",   # count gives the loud (16,16,12) routing
    "ambient|income|population|distance",   # count gives the quiet (4,28,12) routing
]
jobs = []
for k in RANKINGS:
    order = k.split("|")
    for s in ["count", "ref:65", "ref:60", "ref:50", "alpha:0.6", "base"]:
        jobs.append({"scheme": s, "order": order, "pop": True, "T_max": 5,
                     "timeout_ms": 1800000, "wall_kill": 2000})
    for s in ["ref:55", "count"]:
        jobs.append({"scheme": s, "order": order, "pop": True, "T_max": 5, "D": 7.0,
                     "timeout_ms": 1800000, "wall_kill": 2000})
json.dump({"out": "tract.jsonl", "par": 10, "jobs": jobs}, open("plan_tract.json", "w"))
print(len(jobs), "jobs")
