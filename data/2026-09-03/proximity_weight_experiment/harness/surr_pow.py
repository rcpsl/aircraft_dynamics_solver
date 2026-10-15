"""Does simply widening the ranking's own weight spread outrun the gradient?

The implicit ambient gradient is a fixed ~70x. Today's weights span 56x, so they
lose. Raising the dashboard's PROX_BASE from 5 to 10 spans 316x, to 25 spans
3125x -- in principle enough to overpower it.

The reason it might not: `ambient` is one of the four ranked factors, so the
weights ALREADY contain a term that agrees with the gradient. Stretching them
stretches that agreement too, and a group that ranked ambient highly could end up
further from being able to change anything, not closer.

Also tested combined with the shared curve (powref) and with a partial alpha
correction (powa), since spread and gradient-removal are independent knobs.
"""
import itertools, json, sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"d:/Documents/EECS_199_Shoukry/proximity_noise_experiment/harness")
import mkreq as mk

F = ["income", "ambient", "distance", "population"]
RANKINGS = ([(list(p), True) for p in itertools.permutations(F)] +
            [(list(p) + ["population"], False)
             for p in itertools.permutations([f for f in F if f != "population"])])
SCHEMES = ["base", "count", "ref:55", "alpha:0.7",
           "pow:10", "pow:25", "pow:125",
           "powref:10_55", "powref:25_55", "powref:125_55",
           "powa:10_0.7", "powa:25_0.7"]


def one(args):
    scheme, order, pop, factor, restarts = args
    import surrogate as su
    import schemes as sc
    st = mk.streams(factor) if factor != 1.0 else None
    p = su.Problem(scheme, order, pop, streams=st)
    r = p.solve(restarts=restarts)
    occ = r["occ"]
    tier = {str(b): sum(occ[m] for m in range(25) if su.BASE[m] == b) for b in (45, 55, 65)}
    cnt = p.counts(r["choice"])
    peak = dose = 0.0
    for t in range(p.T):
        for m in range(25):
            if cnt[t][m]:
                d = sc.dbinc(su.BASE[m], cnt[t][m])
                peak = max(peak, d)
                dose += d
    return {"scheme": scheme, "order": order, "pop": pop, "w_prox": 1.0, "demand": factor,
            "cost": r["cost"], "occ": occ, "tier": tier, "quiet": tier["45"],
            "peak": round(peak, 3), "dose": round(dose, 2), "w0dose": 0.0}


def main(out, restarts):
    jobs = [(s, o, p, f, restarts)
            for f in (1.0, 0.5) for s in SCHEMES for o, p in RANKINGS]
    print(f"{len(jobs)} configurations", flush=True)
    with open(out, "w") as fh, ProcessPoolExecutor(max_workers=12) as ex:
        for rec in ex.map(one, jobs, chunksize=3):
            fh.write(json.dumps(rec) + "\n")
    print("done", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "surr_pow.jsonl",
         int(sys.argv[2]) if len(sys.argv) > 2 else 50)
