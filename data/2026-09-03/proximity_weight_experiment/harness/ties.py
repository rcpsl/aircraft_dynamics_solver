"""How many routings are TIED at each scheme's optimum?

This matters for the workshop, not just for bookkeeping. The surrogate
canonicalizes ties (it keeps the lexicographically smallest occupancy vector
among equal-cost optima) so that "distinct routings" counts genuine ranking
response. Z3 does no such thing -- it returns whichever optimum its search
reaches first. So if a scheme's optimum is highly degenerate, the map a group
actually sees is arbitrary among many equally-optimal answers, and two runs of
the same ranking can differ for no reason the participants can be told about.

Reports, per scheme: how often the optimum is unique, and the worst degeneracy
found. Optima are collected across restarts, so counts are a LOWER bound on the
true multiplicity.
"""
import itertools, json, sys
from concurrent.futures import ProcessPoolExecutor

F = ["income", "ambient", "distance", "population"]
RANKINGS = ([(list(p), True) for p in itertools.permutations(F)] +
            [(list(p) + ["population"], False)
             for p in itertools.permutations([f for f in F if f != "population"])])


def one(args):
    scheme, order, pop, restarts = args
    import random
    import surrogate as su
    p = su.Problem(scheme, order, pop)
    rng = random.Random(7)
    N = len(p.paths)
    best, seen = None, {}
    for r in range(restarts):
        ch = ([0] * N if r == 0 else [rng.randrange(len(p.paths[i])) for i in range(N)])
        cur = p.cost(ch)
        improved = True
        while improved:
            improved = False
            for i in rng.sample(range(N), N):
                bi, bc = ch[i], cur
                for k in range(len(p.paths[i])):
                    if k == ch[i]:
                        continue
                    old = ch[i]
                    ch[i] = k
                    c = p.cost(ch)
                    if c < bc - 1e-15:
                        bi, bc = k, c
                    ch[i] = old
                if bi != ch[i]:
                    ch[i], cur, improved = bi, bc, True
        c = round(cur, 12)
        if best is None or c < best:
            best, seen = c, {}
        if c == best:
            seen[tuple(p.occ(ch))] = 1
    return {"scheme": scheme, "order": order, "pop": pop,
            "cost": best, "tied_routings": len(seen)}


def main(out, schemes, restarts):
    jobs = [(s, o, p, restarts) for s in schemes for o, p in RANKINGS]
    print(f"{len(jobs)} configurations", flush=True)
    with open(out, "w") as f, ProcessPoolExecutor(max_workers=4) as ex:
        for rec in ex.map(one, jobs, chunksize=2):
            f.write(json.dumps(rec) + "\n")
    print("done", flush=True)


if __name__ == "__main__":
    main("ties.jsonl", ["base", "count", "ref:55", "alpha:0.6"], 100)
