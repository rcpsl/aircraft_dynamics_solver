"""Schemes that KEEP per-tile added-noise pricing. No shared reference curve.

Every scheme here runs proximityMode="noise" with each tile priced by its own
dB curve; only the weight vector changes. Two families:

  alpha:a   w0[m] / g[m]**a, where g[m] is the tile's own increase at ONE
            aircraft. Cancels the gradient exactly at n=1 and drifts elsewhere.
  geo:K     w0[m] / geomean(dB(baseline[m], n) for n in 1..K) -- the
            least-squares fit to a shared curve shape over occupancies 1..K.
            geo:1 IS alpha:1.0; larger K trades exactness at one aircraft for a
            better fit across the occupancies that actually occur.
  geoa:K_a  the geo:K correction applied only fractionally, so the fit has its
            own strength dial the way alpha does.

Run at full demand and at half demand, since the two families rank differently
under the two (alpha:0.6 loses a routing at N=8 where ref keeps all four).
"""
import itertools, json, sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"d:/Documents/EECS_199_Shoukry/proximity_noise_experiment/harness")
import mkreq as mk

F = ["income", "ambient", "distance", "population"]
RANKINGS = ([(list(p), True) for p in itertools.permutations(F)] +
            [(list(p) + ["population"], False)
             for p in itertools.permutations([f for f in F if f != "population"])])
SCHEMES = (["base", "count", "ref:55"]
           + [f"alpha:{a}" for a in ("0.6", "0.7", "0.75", "0.8")]
           + [f"geo:{k}" for k in (2, 3, 4, 6)]
           + [f"geoa:3_{a}" for a in ("0.7", "0.85")])


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
    main(sys.argv[1] if len(sys.argv) > 1 else "surr_keepdb.jsonl",
         int(sys.argv[2]) if len(sys.argv) > 2 else 50)
