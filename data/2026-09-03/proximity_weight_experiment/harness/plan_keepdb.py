"""Z3 timing for the keep-per-tile-dB finalist at half demand.

alpha:0.7 is the best scheme that keeps genuine per-tile added-noise pricing:
3 of 6 routings with noise quality fully intact, at both full and half demand.
Its full-demand cost is known (452 s with split streams, marginal against the
600 s budget). Its half-demand cost is not, and alpha:0.6 came in at 48 s there,
so this should be the comfortable option -- worth confirming rather than
assuming.
"""
import json, sys
sys.path.insert(0, r"d:/Documents/EECS_199_Shoukry/proximity_noise_experiment/harness")
import mkreq as mk

ORDER = ["income", "ambient", "distance", "population"]
s, e, m = mk.streams(0.5)
ov = {"N": len(s), "startPositions": s, "endPositions": e,
      "aircraftMultipliers": m, "demandFactor": 0.5}
jobs = [{"scheme": sch, "order": o, "pop": True, "T_max": mk.cheb(s, e),
         "timeout_ms": 900000, "wall_kill": 1000, "req": dict(ov)}
        for sch in ("alpha:0.7", "alpha:0.8")
        for o in (ORDER, ["income", "population", "distance", "ambient"])]
json.dump({"out": "keepdb.jsonl", "par": 4, "jobs": jobs}, open("plan_keepdb.json", "w"))
print(len(jobs), "jobs")
