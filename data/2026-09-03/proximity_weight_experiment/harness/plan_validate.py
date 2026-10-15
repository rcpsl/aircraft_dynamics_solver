"""Do the direct find_min_T + optimize_objectives calls reproduce the Flask path?

Re-runs three count-mode rankings that sweep.jsonl already has and compares the
occupancy vectors. Count mode because it is ~38s a run, and because the two
paths share every line of code that could differ -- nothing in the comparison is
specific to the pricing mode.
"""
import json
jobs = [{"scheme": "count", "order": o, "pop": True, "T_max": 5,
         "timeout_ms": 600000, "wall_kill": 900}
        for o in (["income", "ambient", "distance", "population"],
                  ["distance", "income", "ambient", "population"],
                  ["population", "distance", "income", "ambient"])]
json.dump({"out": "validate.jsonl", "par": 3, "jobs": jobs}, open("plan_validate.json", "w"))
