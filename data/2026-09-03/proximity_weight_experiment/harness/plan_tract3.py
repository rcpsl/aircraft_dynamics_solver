"""Third tractability block: the split-stream Admin toggle.

Individual mode sends N=16 free aircraft. Split mode carries each direction with
two streams at 1/3 and 2/3 of the count, so demand [4,2,2] becomes N=12 with
multipliers 1,3 / 1,1 / 1,1 -- fewer location variables for the optimizer to
search, same total traffic. It is an existing Admin toggle
(ADMIN.streamMode='split'), so it is payload-only like the other levers here.

Built by mirroring buildStreams() in the dashboard exactly:
lo = max(1, round(C/3)), hi = max(1, C - lo).

Caveat worth carrying: the multiplier-3 stream lands 3 aircraft on one tile at
once, which is what made D=5 unsat at a 45 dB destination
([[heavy-stream-destination-trap]]). At D=30 that is not in play, but split mode
is a coarser physical model, not just a faster encoding -- it cannot diverge
from individual mode only in runtime.
"""
import json

ORDER = ["income", "ambient", "distance", "population"]
DEM = [4, 2, 2]
AIR, DTN, COM = 11, 18, 5          # 1-indexed stations
PAIRS = [(DTN, AIR), (COM, DTN), (COM, AIR)]

starts, ends, mult = [], [], []
for (a, b), C in zip(PAIRS, DEM):
    for s, e in ((a, b), (b, a)):
        lo = max(1, round(C / 3))
        hi = max(1, C - lo)
        for m in (lo, hi):
            starts.append(s)
            ends.append(e)
            mult.append(m)

override = {"N": len(starts), "startPositions": starts,
            "endPositions": ends, "aircraftMultipliers": mult}
print(f"split mode: N={len(starts)} multipliers={mult} total={sum(mult)}")

jobs = []
for s in ["count", "ref:55", "alpha:0.6", "base"]:
    jobs.append({"scheme": s, "order": ORDER, "pop": True, "T_max": 5,
                 "timeout_ms": 1800000, "wall_kill": 2000,
                 "req": dict(override, split=True)})
json.dump({"out": "tract3.jsonl", "par": 4, "jobs": jobs}, open("plan_tract3.json", "w"))
print(len(jobs), "jobs")
