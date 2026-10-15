"""No ambient in the ranking, and only the MAGNITUDE of the remaining weights varied.

Participants rank income / distance / population at 0.45 / 0.35 / 0.20 -- ambient
is gone from the ballot entirely. The solver keeps per-tile dB pricing exactly as
today (no proximityNoiseRef, no alpha correction). The single thing changed is the
base the weights are raised to.

The idea being tested: the dB curve applies a fixed ~70x ambient gradient. Make the
three remaining factors span far more than 70x and they should out-vote it.

Base is capped near 215: three factors each scoring at most 3 with rank weights
summing to 1 give a maximum exponent of 3.0, so the largest weight is B**3 and the
solver rejects anything above 1e7.

Watch the quality columns, not just the routing count. Without ambient on the
ballot nothing in the participants' weights protects quiet neighbourhoods -- the
only thing doing that is the gradient this sweep is trying to overpower.
"""
import itertools, json, sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"d:/Documents/EECS_199_Shoukry/proximity_noise_experiment/harness")
import mkreq as mk

RANKINGS = [(list(p), True) for p in itertools.permutations(["income", "distance", "population"])]
BASES = [5, 7, 10, 15, 20, 25, 35, 50, 75, 100, 150, 200]
SCHEMES = [f"pow:{b}" for b in BASES] + ["count"]


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
        for rec in ex.map(one, jobs, chunksize=2):
            fh.write(json.dumps(rec) + "\n")
    print("done", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "surr_noamb_pow.jsonl",
         int(sys.argv[2]) if len(sys.argv) > 2 else 60)
