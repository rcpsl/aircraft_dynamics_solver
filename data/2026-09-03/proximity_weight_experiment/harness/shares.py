"""How loudly does each term actually speak, at the solution the solver returned?

optimize_objectives divides every term by a theoretical maximum and adds them
with the client's weights. If the proximity term only reaches a few percent of
its normalized range while the soft-T penalty reaches half of its own, the
routing is mostly "arrive early" and no weight vector can change it -- that is
the failure mode [[objective-binding-strength]] documented for the utilitarian
term, and it is worth ruling in or out for each scheme here rather than
assuming the gradient is the whole story.

Recomputed offline from the saved paths using the solver's own
_max_weighted_price and build_scaled_table, so the normalization matches what
Z3 actually divided by.
"""
import importlib.util as iu
import json, sys
import schemes as sc

spec = iu.spec_from_file_location(
    "S", r"d:/Documents/EECS_199_Shoukry/proximity_noise_experiment/solver_server_dB_noise.py")
S = iu.module_from_spec(spec)
spec.loader.exec_module(S)

REQ = sc.mk.build()
BASE, ADB, M = REQ["baseline"], REQ["aircraftDB"], 25


def shares(rec):
    paths = rec.get("paths")
    if not paths:
        return None
    T = len(paths[0])
    s0, e0, mult = REQ["startPositions"], REQ["endPositions"], REQ["aircraftMultipliers"]
    N = len(paths)
    mw = sum(mult)
    table = S.build_scaled_table(M, mw, BASE, ADB)
    D_count = S._compute_d_counts(M, mw, round(REQ["D"] * S.SCALE), table)

    pw, extra = sc.build(rec["scheme"], rec["order"], rec["pop"])
    int_pw = [round(w * 100) for w in pw]
    mode = extra.get("proximityMode", "noise")
    ref = extra.get("proximityNoiseRef")
    if mode == "count":
        price = None
    elif ref is None:
        price = table
    else:
        row = [round(S.dB_increase(ref, n, ADB) * S.SCALE) for n in range(mw + 1)]
        price = [row] * M

    cnt = [[0] * T for _ in range(M)]
    n_arr = 0
    for i, p in enumerate(paths):
        if s0[i] != e0[i]:
            t_fm = next((t for t in range(T) if p[t] != s0[i]), None)
            if t_fm is not None:
                t_arr = next((t for t in range(T) if p[t] == e0[i]), T - 1)
                for t in range(t_fm, t_arr + 1):
                    cnt[p[t] - 1][t] += mult[i]
        # T penalty counts timesteps before arrival, exactly as the objective does
        for t in range(T):
            if not any(p[u] == e0[i] for u in range(t + 1)):
                n_arr += 1

    if mode == "count":
        cost = sum(cnt[m][t] * int_pw[m] for m in range(M) for t in range(T))
        max_prox = mw * T * max(int_pw)
    else:
        cost = sum(price[m][cnt[m][t]] * int_pw[m] for m in range(M) for t in range(T))
        max_prox = S._max_weighted_price(price, int_pw, D_count, mw, M, T)
    max_tp = N * (T - 1)
    wp = float(rec.get("w_prox", 1.0))
    return {"prox_share": round(wp * cost / max_prox, 4) if max_prox else None,
            "time_share": round(n_arr / max_tp, 4) if max_tp else None,
            "prox_raw": cost, "prox_max": max_prox, "tp": n_arr, "tp_max": max_tp}


def main(path):
    recs = [json.loads(l) for l in open(path)]
    print(f"{'scheme':12}{'ranking':38}{'prox term':>11}{'time term':>11}{'ratio':>9}")
    for r in sorted(recs, key=lambda r: (r["scheme"], r["key"])):
        if r["status"] != "sat":
            continue
        s = shares(r)
        k = "-".join(r["order"]) + ("" if r["pop"] else "*")
        ratio = (s["time_share"] / s["prox_share"]) if s["prox_share"] else float("inf")
        print(f"{r['scheme']:12}{k[:37]:38}{s['prox_share']:>11.4f}{s['time_share']:>11.4f}"
              f"{ratio:>9.1f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "stage1.jsonl")
