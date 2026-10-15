"""The same sweep at the dashboard's REAL horizon.

sweep.jsonl and everything above run at slack 0 (T=5), which the fork chose for
speed. The dashboard sends slack 1 (T=6, chebyshev+1). That matters here for a
specific reason: at slack 0 the soft-T penalty is pinned at its floor of 44 for
every routing and cannot discriminate, so proximity is the only live term. At
slack 1 aircraft can arrive late, the penalty varies, and it outvotes proximity
11-14:1 -- so a scheme that restores the ranking at slack 0 could still be
overridden at the horizon the workshop actually uses.

Same validated surrogate, T=6.
"""
import itertools, json, sys
from concurrent.futures import ProcessPoolExecutor

F = ["income", "ambient", "distance", "population"]
RANKINGS = ([(list(p), True) for p in itertools.permutations(F)] +
            [(list(p) + ["population"], False)
             for p in itertools.permutations([f for f in F if f != "population"])])
SCHEMES = ["count", "base", "ref:45", "ref:55", "ref:60", "ref:65",
           "alpha:0.5", "alpha:0.6", "alpha:0.7", "alpha:1.0"]


def one(args):
    scheme, order, pop, restarts = args
    import surrogate as su
    import schemes as sc
    p = su.Problem(scheme, order, pop, T=6)
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
    return {"scheme": scheme, "order": order, "pop": pop, "w_prox": 1.0, "T": 6,
            "cost": r["cost"], "occ": occ, "tier": tier, "quiet": tier["45"],
            "peak": round(peak, 3), "dose": round(dose, 2), "w0dose": round(w0dose, 1),
            "tarr": sum(p.paths[i][c][1] for i, c in enumerate(r["choice"]))}


def main(out, restarts):
    jobs = [(s, o, p, restarts) for s in SCHEMES for o, p in RANKINGS]
    print(f"{len(jobs)} configurations at T=6", flush=True)
    done = 0
    with open(out, "w") as f, ProcessPoolExecutor(max_workers=5) as ex:
        for rec in ex.map(one, jobs, chunksize=2):
            f.write(json.dumps(rec) + "\n")
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(jobs)}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "surr_t6.jsonl",
         int(sys.argv[2]) if len(sys.argv) > 2 else 30)
