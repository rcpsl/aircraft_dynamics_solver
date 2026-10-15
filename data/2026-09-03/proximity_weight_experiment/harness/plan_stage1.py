"""Stage 1: screen 7 weight schemes on 9 rankings chosen to span behaviour.

Ranking subset: two from each count-mode routing family plus the singleton and
both rankings whose noise run fell back entirely. If a scheme returns ONE
routing across these nine it cannot be responsive across thirty, so this is a
cheap kill test; a scheme that survives goes to the full 30 in stage 2.

T_max=5 (slack 0), matching sweep.jsonl so today's numbers are directly
comparable. Finalists get re-run at the dashboard's slack 1 in stage 3.
"""
import json

RANKINGS = [
    "income|ambient|distance|population",      # (4,28,12) family, the dashboard default
    "ambient|income|population|distance",      # (4,28,12) family
    "income|ambient|population|distance",      # (8,24,12)
    "income|distance|ambient|population",      # (7,25,12)
    "income|distance|population|ambient",      # (16,16,12) peak 9.54
    "income|population|distance|ambient",      # (16,16,12) peak 10.41
    "distance|population|income|ambient",      # (16,16,12) peak 10.41
    "population|ambient|distance|income",      # noise fell back
    "distance|ambient|income|NOPOP",           # noise fell back, population off
]
SCHEMES = ["ref:45", "ref:55", "ref:65", "alpha:0.5", "alpha:0.75", "alpha:1.0", "gamma:0.5"]

jobs = []
for s in SCHEMES:
    for k in RANKINGS:
        pop = not k.endswith("|NOPOP")
        order = [f for f in k.split("|") if f != "NOPOP"]
        if not pop:
            order = order + ["population"]      # mkreq.build wants all four; pop flag drops it
        jobs.append({"scheme": s, "order": order, "pop": pop, "T_max": 5,
                     "timeout_ms": 1500000, "wall_kill": 1700})
json.dump({"out": "stage1.jsonl", "par": 14, "jobs": jobs}, open("plan_stage1.json", "w"))
print(len(jobs), "jobs")
