"""Where exactly is the tractability cliff on the alpha dial?

alpha:0.6 + split solves in 350 s; ref (the alpha=1-equivalent flat endpoint)
+ split does not finish in 900 s. Both restore the ranking, so the useful
question for whoever tunes this is how much responsiveness can be bought before
the solve falls off. The dial is the 45 dB : 65 dB price ratio it leaves behind:

    base 160x  ->  a:0.5 19x  ->  a:0.6 13x  ->  a:0.7 8x  ->  a:0.75 6.6x
    ->  a:0.8 5x  ->  ref/a:1.0 2.3x

alpha:0.6 (13x) is inside the budget and ref (2.3x) is not, so the cliff is in
between. Split streams throughout, since that is the only configuration where
any of this fits.
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
ORDER = ["income", "ambient", "distance", "population"]

jobs = [{"scheme": f"alpha:{a}", "order": ORDER, "pop": True, "T_max": 5,
         "timeout_ms": 900000, "wall_kill": 1000, "req": dict(SPLIT)}
        for a in ("0.7", "0.8", "0.9", "1.0", "0.5")]
json.dump({"out": "cliff.jsonl", "par": 5, "jobs": jobs}, open("plan_cliff.json", "w"))
print(len(jobs), "jobs")
