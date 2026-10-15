"""Replicate the split-stream result, and time the best-on-paper combination.

350 s for alpha:0.6 + split is ONE sample, and Z3's run-to-run variance at this
size is ~2x -- so on its own it does not establish that the scheme fits a 600 s
budget. Two more rankings each for the two finalists is the minimum that makes
the claim mean anything.

Also times ref:45 + split at weightProximity=30, which the surrogate says is the
best combination anywhere in the sweep (5 of 6 routings, dose 16.8 against
count's 22.4) but whose Z3 cost is completely untested.
"""
import json

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

RANKINGS = [
    ["income", "population", "distance", "ambient"],   # count -> the loud routing
    ["ambient", "income", "population", "distance"],   # count -> the quiet routing
]
jobs = []
for order in RANKINGS:
    for s in ("alpha:0.6", "ref:55"):
        jobs.append({"scheme": s, "order": order, "pop": True, "T_max": 5,
                     "timeout_ms": 900000, "wall_kill": 1000, "req": dict(SPLIT)})
jobs.append({"scheme": "ref:45", "order": ["income", "ambient", "distance", "population"],
             "pop": True, "T_max": 5, "w_prox": 30.0,
             "timeout_ms": 900000, "wall_kill": 1000, "req": dict(SPLIT)})
json.dump({"out": "final.jsonl", "par": 5, "jobs": jobs}, open("plan_final.json", "w"))
print(len(jobs), "jobs")
