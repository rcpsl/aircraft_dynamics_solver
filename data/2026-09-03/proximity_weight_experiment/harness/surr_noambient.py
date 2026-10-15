"""Sweep with `ambient` removed from the ranked factors entirely.

This is the open question the fork's README leaves standing: it exists to enable
the frontend half of the change, and nobody had run it. Participants rank only
income / distance / population, at the dashboard's own three-factor weights
0.45 / 0.35 / 0.20 -- exactly the table it already uses when Population is
switched off. Six orderings instead of thirty, so routing counts are out of 6.

What it does and does not do: it removes the participants' copy of the ambient
preference. It does NOT remove the solver's. The dB curve still applies its
implicit ~70x ambient gradient, unconditionally. So the double-count becomes a
single count that nobody in the room voted for -- which may read as worse rather
than better, and the routing numbers below are only half the question.

Landscape before solving: the 45:65 price ratio falls 143.8x -> 33.0x, and the
eight quiet tiles stop monopolising the top of the price order (15/24 rankings
-> 0/6). Notably the weight ratio inverts, 2.06x -> 0.47x: with ambient gone, the
loud tiles (Downtown, Airport, Underdeveloped, Industrial) are the ones the
remaining factors want protected, since they are low-income and high-population.
"""
import itertools, json, sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"d:/Documents/EECS_199_Shoukry/proximity_noise_experiment/harness")
import mkreq as mk

# Three ranked factors, ambient dropped. mkreq.weights gives any factor absent
# from the order a weight of 0 and applies RANKW_NOPOP to the rest, so this is
# the dashboard's existing three-factor behaviour with a different factor removed.
RANKINGS = [(list(p), True) for p in itertools.permutations(["income", "distance", "population"])]
# ...and with Population also off, leaving two factors at 0.45 / 0.35.
RANKINGS += [(list(p), True) for p in itertools.permutations(["income", "distance"])]

SCHEMES = ["base", "count", "ref:45", "ref:55", "ref:65",
           "alpha:0.5", "alpha:0.7", "alpha:1.0",
           "pow:25", "pow:125", "powa:25_0.7"]


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
            "nfactors": len(order), "cost": r["cost"], "occ": occ, "tier": tier,
            "quiet": tier["45"], "peak": round(peak, 3), "dose": round(dose, 2),
            "w0dose": 0.0}


def main(out, restarts):
    jobs = [(s, o, p, f, restarts)
            for f in (1.0, 0.5) for s in SCHEMES for o, p in RANKINGS]
    print(f"{len(jobs)} configurations (ambient not ranked)", flush=True)
    with open(out, "w") as fh, ProcessPoolExecutor(max_workers=12) as ex:
        for rec in ex.map(one, jobs, chunksize=2):
            fh.write(json.dumps(rec) + "\n")
    print("done", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "surr_noambient.jsonl",
         int(sys.argv[2]) if len(sys.argv) > 2 else 60)
