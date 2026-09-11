"""Measure the disparity-encoding speedup instead of asserting it.

Sec. III-D claims the max/min encoding of the U constraint "is what brings problems of
this size into range at all", on the strength of an arithmetic constraint count
(10,200 pairwise against 51 max/min per timestep). The pairwise encoding was never built
and never timed, which made this the one engineering claim in the paper with no
experiment behind it -- and the cheapest positive result available.

This builds BOTH encodings on the identical phase-2 model and times them. Everything
except the U constraint is shared, so the difference is attributable to the encoding.

  max/min   two auxiliary integers per timestep:
              dbmax >= d_m, dbmin <= d_m for all m,  dbmax - dbmin <= U     (2M+1)
  pairwise  the direct statement, one implication per ORDERED pair per count value:
              c_a = i  and  c_b = j   =>   |db_a(i) - db_b(j)| <= U

Only the U encoding differs. Both are exact statements of the same constraint, so any
routing feasible under one is feasible under the other; the check below asserts the two
agree on the objective value, which is what makes the timing comparison meaningful.

usage: python pairwise_bench.py [N ...]     default: 6 8
"""
import importlib.util as iu
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import payload as P

SOLVER = r"d:/Documents/EECS_199_Shoukry/solver_server_dB.py"
spec = iu.spec_from_file_location("SOLVER_DB", SOLVER)
S = iu.module_from_spec(spec)
spec.loader.exec_module(S)
from z3 import And, Bool, If, Implies, Int, Not, Optimize, Or, Sum, sat


def build(req, T, pairwise, timeout_ms):
    """Phase-2 model with the U constraint in one of the two encodings.

    Mirrors optimize_objectives' structure for the Equal configuration (no
    principle objective, arrival tie-break only), which is the cheapest payload that
    still carries the full noise encoding -- so the U encoding is the dominant term
    rather than being lost behind an expensive objective.
    """
    N, M = req["N"], req["M"]
    D_s = round(req["D"] * S.SCALE)
    U_s = round(req["U"] * S.SCALE)
    mult = [max(1, round(m)) for m in req["aircraftMultipliers"]]
    maxw = sum(mult)
    tbl = S.build_scaled_table(M, maxw, req["baseline"], req["aircraftDB"])
    Dc = S._compute_d_counts(M, maxw, D_s, tbl)
    adj, sp, ep = req["adjacency"], req["startPositions"], req["endPositions"]

    opt = Optimize()
    opt.set("timeout", timeout_ms)
    L = [[Int(f"L_{i}_{t}") for t in range(T)] for i in range(N)]
    for i in range(N):
        for t in range(T):
            opt.add(And(1 <= L[i][t], L[i][t] <= M))
        opt.add(L[i][0] == sp[i])
        opt.add(L[i][T - 1] == ep[i])
        for t in range(T - 1):
            for src in range(1, M + 1):
                dsts = [d + 1 for d in range(M) if adj[src - 1][d] == 1]
                opt.add(Implies(L[i][t] == src, Or([L[i][t + 1] == d for d in dsts])))

    ha = [[Bool(f"ha_{i}_{t}") for t in range(T)] for i in range(N)]
    mv = [[Bool(f"mv_{i}_{t}") for t in range(T)] for i in range(N)]
    ac = [[Bool(f"ac_{i}_{t}") for t in range(T)] for i in range(N)]
    for i in range(N):
        opt.add(ha[i][0] == (L[i][0] == ep[i]))
        opt.add(mv[i][0] == False)
        opt.add(ac[i][0] == False)
        for t in range(1, T):
            opt.add(ha[i][t] == Or(ha[i][t - 1], L[i][t] == ep[i]))
            opt.add(mv[i][t] == Or(mv[i][t - 1], Not(L[i][t] == sp[i])))
            opt.add(ac[i][t] == And(mv[i][t], Not(ha[i][t - 1])))
        for t in range(T - 1):
            opt.add(Implies(ha[i][t], L[i][t + 1] == ep[i]))

    n_u = 0
    for t in range(T):
        cnt = [Int(f"c_{m}_{t}") for m in range(M)]
        for m in range(M):
            opt.add(cnt[m] == Sum([If(And(L[i][t] == m + 1, ac[i][t]), mult[i], 0)
                                   for i in range(N)]))
            opt.add(And(0 <= cnt[m], cnt[m] <= Dc[m]))
        db = [S.make_dB_expr(cnt[m], m, tbl, Dc[m]) for m in range(M)]
        if pairwise:
            # The conditional table Sec. III-D describes: for each ORDERED pair and each
            # reachable count of the first tile, pin the second tile's dB within U of the
            # first's. M(M-1)(kappa+1) implications, which is the 10,200 figure.
            #
            # Emitting only the violating combinations would be a cheaper variant, but it
            # is not what the paper claims to have replaced, and on this payload it emits
            # nothing at all: with U wide the constraint is vacuous. The comparison has to
            # use a configuration where U actually binds -- hence Equal, which sends
            # U = limit, rather than Sufficientarian, which sends U = 30.
            for a in range(M):
                for b in range(M):
                    if a == b:
                        continue
                    for i in range(Dc[a] + 1):
                        opt.add(Implies(cnt[a] == i,
                                        And(db[b] <= tbl[a][i] + U_s,
                                            db[b] >= tbl[a][i] - U_s)))
                        n_u += 1
        else:
            hi, lo = Int(f"hi_{t}"), Int(f"lo_{t}")
            for m in range(M):
                opt.add(hi >= db[m]); opt.add(lo <= db[m]); n_u += 2
            opt.add(hi - lo <= U_s); n_u += 1

    pen = Sum([If(Not(ha[i][t]), 1, 0) for i in range(N) for t in range(T)])
    opt.minimize(pen)
    return opt, pen, n_u


def run(N_target, timeout_s=1800):
    f = {6: 0.25, 8: 0.5, 14: 0.75, 16: 1.0}[N_target]
    req = P.build_request("equal", limit=10, demand_factor=f)
    T = req["T_max"]
    out = {"N": req["N"], "T": T, "D": req["D"], "U": req["U"]}
    for tag, pw in (("maxmin", False), ("pairwise", True)):
        t0 = time.monotonic()
        opt, pen, n_u = build(req, T, pw, timeout_s * 1000)
        t_build = time.monotonic() - t0
        t1 = time.monotonic()
        res = opt.check()
        t_solve = time.monotonic() - t1
        val = opt.model().evaluate(pen).as_long() if res == sat else None
        out[tag] = {"u_constraints": n_u, "build_s": round(t_build, 2),
                    "solve_s": round(t_solve, 2), "status": str(res), "arrival": val}
        print(f"  N={out['N']:>3} {tag:9s} U-constraints={n_u:>8} "
              f"build={t_build:7.2f}s solve={t_solve:8.2f}s {res} arrival={val}",
              flush=True)
    a, b = out["maxmin"], out["pairwise"]
    out["agree"] = (a["arrival"] == b["arrival"] and a["arrival"] is not None)
    if a["solve_s"] > 0:
        out["speedup_solve"] = round(b["solve_s"] / a["solve_s"], 2)
        out["speedup_total"] = round((b["solve_s"] + b["build_s"])
                                     / (a["solve_s"] + a["build_s"]), 2)
    return out


if __name__ == "__main__":
    targets = [int(x) for x in sys.argv[1:]] or [6, 8]
    rows = []
    for n in targets:
        print(f"=== N={n} ===", flush=True)
        rows.append(run(n))
        with io.open(os.path.join(HERE, "results", "pairwise.jsonl"), "a",
                     encoding="utf-8") as fh:
            fh.write(json.dumps(rows[-1]) + "\n")
    print()
    for r in rows:
        print(f"N={r['N']}: objectives agree={r.get('agree')}  "
              f"solve speedup={r.get('speedup_solve')}x  "
              f"total speedup={r.get('speedup_total')}x")
