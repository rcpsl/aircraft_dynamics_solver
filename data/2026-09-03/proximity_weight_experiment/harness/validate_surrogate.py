"""Does the local search reproduce Z3's answers?

Count mode, all 30 rankings, against the routings sweep.jsonl already holds from
the Flask solver. Count mode is the right test set: it is the only pricing for
which a full 30-ranking set of Z3 optima exists, and the search knows nothing
about which pricing it is running.

Three outcomes worth distinguishing:
  MATCH   same occupancy vector
  TIE     different vector, but the surrogate's cost is <= Z3's cost on the
          surrogate's own objective -- both are optima and Z3 broke the tie the
          other way. Not an error.
  WORSE   the surrogate's cost is higher: the local search genuinely missed.
"""
import json, sys
import surrogate as su

SWEEP = r"d:/Documents/EECS_199_Shoukry/proximity_noise_experiment/harness/sweep.jsonl"


def main(restarts):
    rows = [json.loads(l) for l in open(SWEEP)]
    n_match = n_tie = n_worse = 0
    for r in rows:
        c = r["count"]
        if not c.get("occ"):
            continue
        order = r["order"] if r["pop"] else r["order"] + ["population"]
        p = su.Problem("count", order, r["pop"])
        got = p.solve(restarts=restarts)
        if got["occ"] == c["occ"]:
            n_match += 1
            verdict = "MATCH"
        else:
            # score Z3's routing under the identical objective
            z = score_occ(p, c["occ"])
            if z is None:
                verdict = "UNREACHABLE(z3 route not in path space!)"
                n_worse += 1
            elif got["cost"] <= z + 1e-12:
                verdict = f"TIE (surrogate {got['cost']:.8f} <= z3 {z:.8f})"
                n_tie += 1
            else:
                verdict = f"WORSE (surrogate {got['cost']:.8f} > z3 {z:.8f})"
                n_worse += 1
        print(f"{r['key']:46} {verdict}")
    print(f"\n{n_match} match, {n_tie} tie, {n_worse} worse (restarts={restarts})")


def score_occ(prob, occ):
    """Objective value of ANY assignment whose occupancy vector is `occ`.

    The proximity term depends on per-timestep counts, not on the summed-over-
    time occupancy vector sweep.jsonl stores, so this reconstructs by local
    search under a hard match constraint. Returns None if nothing matches.
    """
    import random
    rng = random.Random(1)
    N = len(prob.paths)
    best = None
    for _ in range(60):
        ch = [rng.randrange(len(prob.paths[i])) for i in range(N)]
        for _sweep in range(40):
            moved = False
            for i in rng.sample(range(N), N):
                cand = None
                for k in range(len(prob.paths[i])):
                    old = ch[i]
                    ch[i] = k
                    d = sum(abs(a - b) for a, b in zip(prob.occ(ch), occ))
                    c = prob.cost(ch)
                    if cand is None or (d, c) < cand[0]:
                        cand = ((d, c), k)
                    ch[i] = old
                if cand[1] != ch[i]:
                    ch[i] = cand[1]
                    moved = True
            if not moved:
                break
        if prob.occ(ch) == occ:
            c = prob.cost(ch)
            if best is None or c < best:
                best = c
    return best


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
