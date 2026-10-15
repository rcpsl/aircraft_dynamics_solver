"""Does the ranking still respond at reduced demand?

Halving demand makes every corrected scheme tractable (ref:55 62 s, alpha:0.6
48 s, against >900 s at full demand), which is by far the strongest tractability
result here. But it is not free: fewer aircraft is a different scenario, and it
could easily leave too little traffic for the ranking to move. Eight aircraft
have fewer ways to be routed than sixteen.

Same validated surrogate, streams from mkreq.streams(f).
"""
import itertools, json, sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"d:/Documents/EECS_199_Shoukry/proximity_noise_experiment/harness")
import mkreq as mk

F = ["income", "ambient", "distance", "population"]
RANKINGS = ([(list(p), True) for p in itertools.permutations(F)] +
            [(list(p) + ["population"], False)
             for p in itertools.permutations([f for f in F if f != "population"])])
SCHEMES = ["count", "base", "ref:45", "ref:55", "ref:60", "alpha:0.6", "alpha:1.0"]


def one(args):
    scheme, order, pop, factor, restarts = args
    import surrogate as su
    import schemes as sc
    s, e, m = mk.streams(factor)
    p = su.Problem(scheme, order, pop, streams=(s, e, m))
    r = p.solve(restarts=restarts)
    occ = r["occ"]
    tier = {str(b): sum(occ[m_] for m_ in range(25) if su.BASE[m_] == b) for b in (45, 55, 65)}
    cnt = p.counts(r["choice"])
    w0 = sc.weights_for(order, pop)
    peak = dose = 0.0
    for t in range(p.T):
        for m_ in range(25):
            if cnt[t][m_]:
                d = sc.dbinc(su.BASE[m_], cnt[t][m_])
                peak = max(peak, d)
                dose += d
    return {"scheme": scheme, "order": order, "pop": pop, "w_prox": 1.0,
            "demand": factor, "N": len(s), "cost": r["cost"], "occ": occ, "tier": tier,
            "quiet": tier["45"], "peak": round(peak, 3), "dose": round(dose, 2),
            "w0dose": 0.0}


def main(out, restarts):
    jobs = [(s, o, p, f, restarts)
            for f in (0.5, 0.25) for s in SCHEMES for o, p in RANKINGS]
    print(f"{len(jobs)} configurations at reduced demand", flush=True)
    with open(out, "w") as f_:
        with ProcessPoolExecutor(max_workers=6) as ex:
            for rec in ex.map(one, jobs, chunksize=4):
                f_.write(json.dumps(rec) + "\n")
    print("done", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "surr_demand.jsonl",
         int(sys.argv[2]) if len(sys.argv) > 2 else 40)
