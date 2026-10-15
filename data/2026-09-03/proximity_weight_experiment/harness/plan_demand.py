"""Last tractability lever: demand.

Everything cheaper about the objective has been tried and failed (weightTime=0,
hardT, D=7, and those combined). What is left is making the problem smaller.
The fork's own README already measured this for `base`: N=16 -> 960s,
N=8 -> 569s, N=6 -> 378s. This asks whether it is enough to bring a
gradient-corrected scheme under the budget, which is the only version of the
question that matters now.

Demand factor 0.5 gives demand [2,1,1] -> N=8; 0.25 gives [1,1,1] -> N=6.
Policy-relevant, not just an encoding trick: fewer aircraft is a different
scenario, and the workshop would have to accept modelling less traffic.
"""
import json
import sys
sys.path.insert(0, r"d:/Documents/EECS_199_Shoukry/proximity_noise_experiment/harness")
import mkreq as mk

ORDER = ["income", "ambient", "distance", "population"]
jobs = []
for f in (0.5, 0.25):
    s, e, m = mk.streams(f)
    ov = {"N": len(s), "startPositions": s, "endPositions": e,
          "aircraftMultipliers": m, "demandFactor": f}
    tmax = mk.cheb(s, e)          # slack 0, same convention as everywhere else
    for scheme in ("ref:55", "alpha:0.6", "base"):
        jobs.append({"scheme": scheme, "order": ORDER, "pop": True, "T_max": tmax,
                     "timeout_ms": 900000, "wall_kill": 1000, "req": dict(ov)})
    print(f"demand x{f}: N={len(s)} T_max={tmax}")
json.dump({"out": "demand.jsonl", "par": 6, "jobs": jobs}, open("plan_demand.json", "w"))
print(len(jobs), "jobs")
