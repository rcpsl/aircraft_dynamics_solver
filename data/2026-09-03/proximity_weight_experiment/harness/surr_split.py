"""Does the ranking still work under the split-stream toggle?

Split mode is what made a gradient-corrected scheme tractable (alpha:0.6 solved
in 350 s against >900 s in individual mode), so it is now part of the proposal
and not just an encoding curiosity. But it is a coarser physical model: each
direction is carried by two streams at 1/3 and 2/3 of the count, so the
multiplier-3 stream lands three aircraft on one tile at once and cannot spread
them. That could easily collapse the routing choices the ranking was moving.

Same validated surrogate, streams replaced. Compare the routing counts here
against the individual-mode ones in surr.jsonl.
"""
import itertools, json, sys
from concurrent.futures import ProcessPoolExecutor

F = ["income", "ambient", "distance", "population"]
RANKINGS = ([(list(p), True) for p in itertools.permutations(F)] +
            [(list(p) + ["population"], False)
             for p in itertools.permutations([f for f in F if f != "population"])])
SCHEMES = ["count", "base", "ref:45", "ref:55", "ref:60", "ref:65",
           "alpha:0.5", "alpha:0.6", "alpha:0.7", "alpha:1.0"]

DEM, AIR, DTN, COM = [4, 2, 2], 11, 18, 5
PAIRS = [(DTN, AIR), (COM, DTN), (COM, AIR)]
S_, E_, M_ = [], [], []
for (a, b), C in zip(PAIRS, DEM):
    for s, e in ((a, b), (b, a)):
        lo = max(1, round(C / 3))
        for m in (lo, max(1, C - lo)):
            S_.append(s); E_.append(e); M_.append(m)
STREAMS = (S_, E_, M_)


def one(args):
    scheme, order, pop, restarts = args
    import surrogate as su
    import schemes as sc
    p = su.Problem(scheme, order, pop, streams=STREAMS)
    r = p.solve(restarts=restarts)
    occ = r["occ"]
    tier = {str(b): sum(occ[m] for m in range(25) if su.BASE[m] == b) for b in (45, 55, 65)}
    cnt = p.counts(r["choice"])
    w0 = sc.weights_for(order, pop)
    peak = dose = w0dose = 0.0
    for t in range(p.T):
        for m in range(25):
            if cnt[t][m]:
                d = sc.dbinc(su.BASE[m], cnt[t][m])
                peak = max(peak, d)
                dose += d
                w0dose += d * w0[m]
    return {"scheme": scheme, "order": order, "pop": pop, "w_prox": 1.0, "split": True,
            "cost": r["cost"], "occ": occ, "tier": tier, "quiet": tier["45"],
            "peak": round(peak, 3), "dose": round(dose, 2), "w0dose": round(w0dose, 1)}


def main(out, restarts):
    jobs = [(s, o, p, restarts) for s in SCHEMES for o, p in RANKINGS]
    print(f"{len(jobs)} configurations, split streams (N=12)", flush=True)
    with open(out, "w") as f, ProcessPoolExecutor(max_workers=5) as ex:
        for rec in ex.map(one, jobs, chunksize=2):
            f.write(json.dumps(rec) + "\n")
    print("done", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "surr_split.jsonl",
         int(sys.argv[2]) if len(sys.argv) > 2 else 40)
