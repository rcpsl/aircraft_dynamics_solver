"""Stage 1b: the five schemes still worth Z3 time, interleaved.

Dropped from stage 1a: ref:45 (timed out on all 9 rankings at 1500s) and ref:55
(timed out on the 5 that ran). Those results are already in stage1.jsonl and are
a finding in their own right -- a uniform strongly-concave price curve is the
most expensive thing you can hand this optimizer.

Round-robin over schemes rather than scheme-major, so the first wave covers all
five instead of one.
"""
import json

RANKINGS = [
    "income|ambient|distance|population",
    "ambient|income|population|distance",
    "income|ambient|population|distance",
    "income|distance|ambient|population",
    "income|distance|population|ambient",
    "income|population|distance|ambient",
    "distance|population|income|ambient",
    "population|ambient|distance|income",
    "distance|ambient|income|NOPOP",
]
SCHEMES = ["alpha:1.0", "ref:65", "alpha:0.75", "alpha:0.5", "gamma:0.5"]

jobs = []
for k in RANKINGS:                      # ranking-major == scheme round-robin per wave
    for s in SCHEMES:
        pop = not k.endswith("|NOPOP")
        order = [f for f in k.split("|") if f != "NOPOP"]
        if not pop:
            order = order + ["population"]
        jobs.append({"scheme": s, "order": order, "pop": pop, "T_max": 5,
                     "timeout_ms": 1500000, "wall_kill": 1700})
json.dump({"out": "stage1.jsonl", "par": 14, "jobs": jobs}, open("plan_stage1b.json", "w"))
print(len(jobs), "jobs")
