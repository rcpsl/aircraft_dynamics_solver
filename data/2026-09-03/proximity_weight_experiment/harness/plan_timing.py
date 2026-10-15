"""One Z3 timing plan, run alone, capped at 900 s.

900 s, not 1800 s. The decision threshold is the dashboard's 600 s budget, so
anything slower than 900 s fails it with margin and the exact figure past that
point buys nothing. Capping at 900 s cuts the wall time of this block by half
and lets it run at a parallelism where the timings mean something.

Three groups:
  BASELINE   count and base, to anchor against sweep.jsonl's solo numbers
             (count 17-47 s, base median 1029 s) and measure this run's
             contention factor.
  SCHEMES    do the two finalists and the ref:65 control cost more than base?
             ref:65 is the informative one: its routing IS count's, so any gap
             between them is the dB If-chains and nothing else.
  LEVERS     the payload-only ways to make the objective cheaper.
"""
import json

ORDER = ["income", "ambient", "distance", "population"]
DEM, AIR, DTN, COM = [4, 2, 2], 11, 18, 5
PAIRS = [(DTN, AIR), (COM, DTN), (COM, AIR)]
starts, ends, mult = [], [], []
for (a, b), C in zip(PAIRS, DEM):
    for s, e in ((a, b), (b, a)):
        lo = max(1, round(C / 3))
        for m in (lo, max(1, C - lo)):
            starts.append(s); ends.append(e); mult.append(m)
SPLIT = {"N": len(starts), "startPositions": starts, "endPositions": ends,
         "aircraftMultipliers": mult, "split": True}


def job(scheme, **extra):
    j = {"scheme": scheme, "order": ORDER, "pop": True, "T_max": 5,
         "timeout_ms": 900000, "wall_kill": 1000}
    j.update(extra)
    return j


jobs = [
    job("count"), job("base"),                                   # baseline
    job("ref:65"), job("ref:55"), job("alpha:0.6"),              # schemes
    job("ref:55", req={"weightTime": 0.0}),                      # levers on ref:55
    job("ref:55", req={"hardT": True}),
    job("ref:55", D=7.0),
    job("ref:55", D=7.0, req={"weightTime": 0.0}),
    job("alpha:0.6", req={"weightTime": 0.0}),                   # levers on alpha:0.6
    job("alpha:0.6", req={"hardT": True}),
    job("alpha:0.6", D=7.0),
    job("ref:55", req=dict(SPLIT)),                              # split streams
    job("alpha:0.6", req=dict(SPLIT)),
    job("count", req=dict(SPLIT)),
]
json.dump({"out": "timing.jsonl", "par": 8, "jobs": jobs}, open("plan_timing.json", "w"))
print(len(jobs), "jobs, 900s cap, par=8")
