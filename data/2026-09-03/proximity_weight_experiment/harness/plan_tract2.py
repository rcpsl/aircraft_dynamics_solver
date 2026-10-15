"""Second tractability block: payload-only levers on the objective's cost.

Block A showed the ~40x is the dB If-chains themselves -- ref:65 returns count's
exact routing and still times out where count takes 36 s. So the levers worth
timing are the ones that shorten or remove work, not the ones that change the
weights:

  weightTime=0   drops the soft-T penalty term entirely. At slack 0 that term is
                 the same 44 for every routing (the sum of the 16 shortest-path
                 hop counts, its floor), so it discriminates between nothing and
                 only costs search. Proximity still penalizes long active
                 windows, so aircraft have no incentive to dawdle.
  hardT=true     fixes phase 2 at phase 1's minimum T and drops both the penalty
                 and the sticky-arrival implications. Cuts terms but ENLARGES the
                 search space (aircraft may wander after arriving, which costs no
                 noise), so the sign of this one is genuinely unknown.
  D=7            shortens the If-chains on 45 dB tiles from 16 branches to 4.

Run against ref:55 and alpha:0.6, the two finalists, on the default ranking.
count is included under each lever as the floor.
"""
import json

ORDER = ["income", "ambient", "distance", "population"]
jobs = []
for s in ["ref:55", "alpha:0.6"]:
    for label, extra in [("wtime0", {"req": {"weightTime": 0.0}}),
                         ("hardT", {"req": {"hardT": True}}),
                         ("D7", {"D": 7.0}),
                         ("D7+wtime0", {"D": 7.0, "req": {"weightTime": 0.0}})]:
        j = {"scheme": s, "order": ORDER, "pop": True, "T_max": 5,
             "timeout_ms": 1800000, "wall_kill": 2000}
        j.update(extra)
        jobs.append(j)
json.dump({"out": "tract2.jsonl", "par": 8, "jobs": jobs}, open("plan_tract2.json", "w"))
print(len(jobs), "jobs")
