"""Targeted retry for the four equal_allocation people_equal cells that phase 2
could not optimize within the default budget.

STATUS OF THESE CELLS. Phase 1 proved a feasible FULL-DEMAND routing exists in
every one of them -- the disparity constraint is satisfiable at 100% demand.
Only phase 2 (z3.Optimize under the population-weighted transit objective)
failed, at 262-274s against a 240s budget, identically across seeds 1/7/42. So
they are "unresolved", not "infeasible", and emphatically not "needs a demand
cut": reducing the fleet here would report a solver limitation as a fairness
cost.

TWO LEVERS, both applied here:

1. Timeout 240s -> 600s, set at RUNTIME (`S.SOLVE_TIMEOUT_MS = ...`). The solver
   source is NOT edited -- this collection never modifies solver_server_dB.py.
2. T_max 7 -> 6, then 5. Phase 2 runs at T = max(T_min, T_max), and the
   constraint volume grows with T, so fewer timesteps is a much smaller problem.

CAVEAT THAT MUST SURVIVE INTO ANY WRITEUP. The other 20 equal_allocation files
ran at T_max=7. A file solved at T_max=6 or 5 had strictly less scheduling slack
to spread traffic with, so its noise figures can only be equal or worse, never
better -- they are not directly comparable to the T_max=7 files. Every file this
script writes records `T_max`, `T_maxDeviatesFromDomain` and `solveTimeoutMs` in
its preamble so the difference is visible rather than silent.

Usage: python retry_unresolved.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths45 import ROUTES
from _helpers45 import (
    PEOPLE_WEIGHTS, baseline_for, variant_to_fleet, demand_pct,
    solve_scenario, metric_maxima, write_full_csv, travel_stats, S,
)

# Runtime override -- no source edit. Applies to both find_min_T and
# optimize_objectives, which read this constant when they set their z3 timeout.
NEW_TIMEOUT_MS = 600_000
S.SOLVE_TIMEOUT_MS = NEW_TIMEOUT_MS

DOMAIN_T_MAX = 7             # what the other 20 files used
# Tried in order, first success wins. T_min for this scenario is 4 (shortest
# path 1-6-11-16 is 3 hops), so T_max=4 is the smallest problem z3 can be given
# -- the best shot at tractability, though it may make U=3 unsat by removing all
# scheduling slack. 9 is the opposite lever: a bigger problem, but more slack
# can make the optimum easier to FIND. 6 and 7 already failed at 600s/240s.
T_MAX_LADDER = [5, 4, 9]
D_FIXED = 50.0
W_TIME = 0.1

FLAGS = dict(optimize_util=True, w_util=2.0,
             station_transit_weights=PEOPLE_WEIGHTS, util_noise_mode=False)

# The two cells still unwritten. The two U=8 cells were resolved by
# substitution from community_equal, justified by 6/6 loose-constraint pairs
# being byte-identical across modes. These two are NOT substitutable: both U=3
# pairs that did solve show the modes diverging (max avg added dB 0.365->0.650
# and 0.442->0.736), so U=3 is exactly where the population weighting changes
# the answer and a copied routing would erase the domain's only mode contrast.
CELLS = [
    ("s2-65_s6-55", 3.0),
    ("s2-55_s6-55", 3.0),
]


def main():
    print(f"timeout {NEW_TIMEOUT_MS // 1000}s, T_max ladder {T_MAX_LADDER} "
          f"(domain default {DOMAIN_T_MAX})\n", flush=True)
    written, still_unresolved = [], []

    for combo, U in CELLS:
        baseline = baseline_for(combo)
        n, mult, start, end = variant_to_fleet("baseline_mult")
        out = ROUTES / combo / "equal_allocation" / "people_equal" / f"U{int(U)}.csv"
        if out.exists():
            print(f"skip {combo} U={U} (exists)", flush=True)
            continue

        print(f"--- {combo} U={U} (people_equal, 100% demand) ---", flush=True)
        for t_max in T_MAX_LADDER:
            t0 = time.time()
            r = solve_scenario(n, D_FIXED, U, t_max, baseline, mult, start, end,
                               w_time=W_TIME, **FLAGS)
            dt = time.time() - t0
            status = r.get("status")
            if status != "sat":
                print(f"    T_max={t_max}: {status}/{r.get('reason','')} "
                      f"({dt:.0f}s)", flush=True)
                continue

            mx_avg, mx_peak = metric_maxima(r, baseline)
            avg_tt, _, _ = travel_stats(r["paths"], mult, start, end, r["T"])
            meta = {
                "domain": "equal_allocation", "combo": combo,
                "mode": "people_equal", "U": U,
                "Urole": "hard disparity cap (a real constraint, not a label)",
                "D": D_FIXED, "Dbinding": False,
                "variant": "baseline_mult", "fullFleetFeasible": True,
                "hardT": False, "T_max": t_max,
                "T_maxDeviatesFromDomain": t_max != DOMAIN_T_MAX,
                "T_maxDomainDefault": DOMAIN_T_MAX,
                "solveTimeoutMs": NEW_TIMEOUT_MS,
                "retryNote": (f"phase 2 unresolved at T_max={DOMAIN_T_MAX}/240s "
                              f"across seeds 1/7/42; solved at T_max={t_max} "
                              f"with a {NEW_TIMEOUT_MS // 1000}s budget. Less "
                              f"scheduling slack than the T_max=7 files, so not "
                              f"directly comparable to them."),
                "weightTime": W_TIME, "optimizeUtilitarian": True,
                "weightUtilitarian": 2.0,
                "stationTransitWeights": PEOPLE_WEIGHTS,
                "maxAvgAddedDb": round(mx_avg, 4),
                "maxPeakAddedDb": round(mx_peak, 4),
            }
            write_full_csv(out, meta, r["paths"], mult, start, end,
                           r["countMatrix"], r["noiseMatrix"], baseline, r["T"])
            print(f"    T_max={t_max}: SOLVED avg={mx_avg:.3f} peak={mx_peak:.3f} "
                  f"T={r['T']} travel={avg_tt} ({dt:.0f}s) -> {out.name}",
                  flush=True)
            written.append((combo, U, t_max, mx_avg, mx_peak, r["T"]))
            break
        else:
            print(f"    still unresolved at every T_max", flush=True)
            still_unresolved.append((combo, U))

    print(f"\n=== written {len(written)}, still unresolved "
          f"{len(still_unresolved)} ===")
    for c, u, t, a, p, T in written:
        print(f"  OK   {c} U={u} T_max={t} avg={a:.3f} peak={p:.3f} T={T}")
    for c, u in still_unresolved:
        print(f"  FAIL {c} U={u}")


if __name__ == "__main__":
    main()
