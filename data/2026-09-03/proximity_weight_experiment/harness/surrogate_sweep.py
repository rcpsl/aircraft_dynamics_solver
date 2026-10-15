"""Large sweep over weight schemes x rankings, using the validated surrogate.

Every result here is a SCREEN. The surrogate models the objective exactly but
searches it heuristically, and it says nothing at all about Z3's runtime --
which is half the decision. Finalists go back through Z3 (runner.py) before any
of it is recommended.

usage: python surrogate_sweep.py <out.jsonl> [restarts]
"""
import itertools, json, os, sys
from concurrent.futures import ProcessPoolExecutor

F = ["income", "ambient", "distance", "population"]
RANKINGS = ([(list(p), True) for p in itertools.permutations(F)] +
            [(list(p) + ["population"], False)
             for p in itertools.permutations([f for f in F if f != "population"])])

SCHEMES = (["count", "base"]
           + [f"alpha:{a/10:.1f}" for a in range(0, 15)]
           + [f"ref:{r}" for r in (45, 50, 55, 60, 65)]
           + [f"alphak:{k}" for k in (2, 3, 4)]
           + [f"gamma:{g}" for g in (0.25, 0.5, 0.75)])
W_PROX = [1.0, 3.0, 10.0, 30.0]


def one(args):
    scheme, order, pop, wp, restarts = args
    import surrogate as su
    import schemes as sc
    p = su.Problem(scheme, order, pop, w_prox=wp)
    r = p.solve(restarts=restarts)
    occ = r["occ"]
    tier = {str(b): sum(occ[m] for m in range(25) if su.BASE[m] == b) for b in (45, 55, 65)}
    # peak and dose are per-TIMESTEP quantities: dB is concave, so they cannot be
    # recovered from occupancy summed over time. Computed from the winning choice.
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
    return {"scheme": scheme, "order": order, "pop": pop, "w_prox": wp,
            "cost": r["cost"], "occ": occ, "tier": tier, "quiet": tier["45"],
            "peak": round(peak, 3), "dose": round(dose, 2), "w0dose": round(w0dose, 1),
            "tarr": sum(p.paths[i][c][1] for i, c in enumerate(r["choice"]))}


def main(out, restarts):
    jobs = [(s, o, p, wp, restarts)
            for wp in W_PROX for s in SCHEMES for o, p in RANKINGS]
    print(f"{len(jobs)} configurations", flush=True)
    done = 0
    # 5 workers, not 14: the Z3 sweep owns the rest of the cores.
    with open(out, "w") as f, ProcessPoolExecutor(max_workers=5) as ex:
        for rec in ex.map(one, jobs, chunksize=4):
            f.write(json.dumps(rec) + "\n")
            done += 1
            if done % 200 == 0:
                print(f"  {done}/{len(jobs)}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "surr.jsonl",
         int(sys.argv[2]) if len(sys.argv) > 2 else 30)
