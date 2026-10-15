"""Z3 timing for the widened-spread schemes.

Two reasons this block matters more than the others:

  1. `powa:10_0.7` reaches 4 routings at full noise quality while KEEPING per-tile
     dB pricing -- which contradicts the "3 is the ceiling for per-tile" claim made
     from the geo results, so its cost needs to be known before it is recommended.
  2. Coefficient SPREAD is what lets Z3 prune, and every fix so far destroyed spread
     to restore the ranking. These schemes ADD spread. They are the first candidates
     that could plausibly be faster than base rather than slower.

Full demand with and without split streams, plus half demand.
"""
import json, sys
sys.path.insert(0, r"d:/Documents/EECS_199_Shoukry/proximity_noise_experiment/harness")
import mkreq as mk

ORDER = ["income", "ambient", "distance", "population"]
ALT = ["income", "population", "distance", "ambient"]

DEM, AIR, DTN, COM = [4, 2, 2], 11, 18, 5
PAIRS = [(DTN, AIR), (COM, DTN), (COM, AIR)]
S_, E_, M_ = [], [], []
for (a, b), C in zip(PAIRS, DEM):
    for s, e in ((a, b), (b, a)):
        lo = max(1, round(C / 3))
        for m in (lo, max(1, C - lo)):
            S_.append(s); E_.append(e); M_.append(m)
SPLIT = {"N": len(S_), "startPositions": S_, "endPositions": E_,
         "aircraftMultipliers": M_, "split": True}
s8, e8, m8 = mk.streams(0.5)
HALF = {"N": len(s8), "startPositions": s8, "endPositions": e8,
        "aircraftMultipliers": m8, "demandFactor": 0.5}


def job(scheme, order, req=None):
    j = {"scheme": scheme, "order": order, "pop": True, "T_max": 5,
         "timeout_ms": 900000, "wall_kill": 1000}
    if req:
        j["req"] = dict(req)
    return j


jobs = []
for sch in ("powa:10_0.7", "pow:125", "pow:25"):
    jobs.append(job(sch, ORDER))                 # full demand, individual streams
for sch in ("powa:10_0.7", "pow:125"):
    jobs.append(job(sch, ORDER, SPLIT))          # full demand, split
    jobs.append(job(sch, ORDER, HALF))           # half demand
    jobs.append(job(sch, ALT, HALF))             # half demand, a second ranking
json.dump({"out": "pow.jsonl", "par": 6, "jobs": jobs}, open("plan_pow.json", "w"))
print(len(jobs), "jobs")
