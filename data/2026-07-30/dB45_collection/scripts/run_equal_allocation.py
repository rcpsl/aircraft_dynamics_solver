"""Equal allocation for the 45 dB collection -- U as a real constraint.

WHAT CHANGED FROM THE 55 dB DESIGN, AND WHY

The previous collection swept `U` across many values, read the resulting max
added dB off each run, and then selected "the largest achievable value strictly
below the target" for targets 3 / 8 / 18 dB. Two things were wrong with that:

  1. The rule *maximises* noise subject to the target -- it deliberately picks
     the loudest option that still clears the bar. For a domain whose entire
     point is spreading noise evenly, that inverts the objective.
  2. `D` was pinned at 50 and never bound, so the "3dB / 8dB / 18dB" filenames
     were post-hoc selection tags, not constraints -- but they read to any
     viewer as "we capped noise at 8 dB", which was never true.

Here 3 / 8 / 18 are the `U` values themselves: the hard cap on the disparity
between any two stations' added dB. That makes the label honest (a U3 file
really was solved under a 3 dB disparity cap), removes the selection rule
entirely, and removes the search -- there is nothing left to choose, so nothing
can be chosen badly.

`avg` and `peak` are no longer separate files. They are two readings of one
solution, and both appear in every zone table.

FLEET POLICY. The full 14-aircraft real-multiplier fleet (100% demand) is used
wherever it is feasible. Where a U is infeasible at full demand -- probe A found
U=3 infeasible at 100% demand in both s6-45 combos, whose floor is U>=5 -- the
run steps down through the fleet variants and records what the constraint cost
in service. That demand cut is a finding, not a footnote, so it is written into
the preamble as `fullFleetFeasible` and `demandFulfilledPct`.

MODES
  community_equal : no objective, no station weights. Every community counts once.
  people_equal    : optimizeUtilitarian at w_util=2.0 with stationTransitWeights
                    = PEOPLE_WEIGHTS (population-weighted routing cost).
                    "Count people, not communities."

Usage:
    python run_equal_allocation.py <combo> [--mode community_equal|people_equal|both]
    python run_equal_allocation.py all [--mode both]
"""
import sys
import time
from pathlib import Path

import z3

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths45 import ROUTES
from _helpers45 import (
    COMBOS, PEOPLE_WEIGHTS, baseline_for, variant_to_fleet, demand_pct,
    solve_scenario, metric_maxima, write_full_csv, travel_stats,
)

D_FIXED = 50.0      # deliberately non-binding: this domain constrains via U only
T_MAX = 7
W_TIME = 0.1
U_VALUES = [3.0, 8.0, 18.0]

# Tried in descending demand order -- the first feasible one wins, so the run
# serves as much demand as the constraint allows.
FLEET_ORDER = ["baseline_mult", "N14_mult1", "N7_mult1", "N4_mult1"]

# Z3's search is not deterministic run-to-run, and phase-2 timeouts have been
# observed to clear on a reseeded retry. Used only to rescue phase2_failed --
# never to change a genuine unsat.
RETRY_SEEDS = [1, 7, 42]

MODES = {
    "community_equal": dict(optimize_util=False),
    "people_equal": dict(optimize_util=True, w_util=2.0,
                         station_transit_weights=PEOPLE_WEIGHTS,
                         util_noise_mode=False),
}


def run_one(combo, mode, U, out_dir, log):
    """Solve one (combo, mode, U) at the largest feasible fleet and emit it."""
    baseline = baseline_for(combo)
    flags = MODES[mode]
    path = out_dir / f"U{int(U)}.csv"
    if path.exists():
        print(f"  skip {path.name} (exists)", flush=True)
        return

    for attempt, variant in enumerate(FLEET_ORDER):
        n, mult, start, end = variant_to_fleet(variant)
        t0 = time.time()
        r = solve_scenario(n, D_FIXED, U, T_MAX, baseline, mult, start, end,
                           w_time=W_TIME, **flags)
        dt = time.time() - t0
        status = r.get("status")
        log.append(f"{mode},{U},{variant},{n},{sum(mult)},{demand_pct(mult)},"
                   f"{status},{r.get('reason','')},{dt:.1f}")

        # A phase-2 timeout is NOT infeasibility. Phase 1 already proved a
        # feasible routing exists at this fleet size -- only the optimizer ran
        # out of budget. Stepping the fleet down here would report a solver
        # limitation as though the fairness constraint had forced a service
        # cut, which is false and is exactly the kind of artifact that ends up
        # misread as a finding. Retry with different Z3 seeds instead (its
        # search is not deterministic run-to-run), and if that fails, leave the
        # cell unwritten rather than fabricating a demand cut.
        if status == "phase2_failed":
            for seed in RETRY_SEEDS:
                z3.set_param("smt.random_seed", seed)
                z3.set_param("sat.random_seed", seed)
                t1 = time.time()
                r = solve_scenario(n, D_FIXED, U, T_MAX, baseline, mult, start,
                                   end, w_time=W_TIME, **flags)
                dt1 = time.time() - t1
                log.append(f"{mode},{U},{variant},{n},{sum(mult)},"
                           f"{demand_pct(mult)},{r.get('status')},"
                           f"seed{seed}:{r.get('reason','')},{dt1:.1f}")
                print(f"  U={U:<5} {variant:<14} phase2 retry seed={seed} -> "
                      f"{r.get('status')} ({dt1:.0f}s)", flush=True)
                if r.get("status") == "sat":
                    break
            z3.set_param("smt.random_seed", 0)
            z3.set_param("sat.random_seed", 0)
            status = r.get("status")
            if status != "sat":
                print(f"  U={U:<5} {variant:<14} PHASE-2 UNRESOLVED at "
                      f"{demand_pct(mult)}% demand -- feasible but not "
                      f"optimizable in budget; NOT cutting demand", flush=True)
                return

        if status != "sat":
            print(f"  U={U:<5} {variant:<14} {status}/{r.get('reason','')} "
                  f"({dt:.0f}s) -> stepping down (genuine infeasibility)",
                  flush=True)
            continue

        mx_avg, mx_peak = metric_maxima(r, baseline)
        avg_tt, min_tt, max_tt = travel_stats(r["paths"], mult, start, end, r["T"])
        meta = {
            "domain": "equal_allocation", "combo": combo, "mode": mode,
            "U": U, "Urole": "hard disparity cap (a real constraint, not a label)",
            "D": D_FIXED, "Dbinding": False,
            "variant": variant, "fullFleetFeasible": attempt == 0,
            "hardT": False, "T_max": T_MAX, "weightTime": W_TIME,
            "optimizeUtilitarian": flags.get("optimize_util", False),
            "weightUtilitarian": flags.get("w_util", ""),
            "stationTransitWeights": flags.get("station_transit_weights", ""),
            "maxAvgAddedDb": round(mx_avg, 4),
            "maxPeakAddedDb": round(mx_peak, 4),
        }
        write_full_csv(path, meta, r["paths"], mult, start, end,
                       r["countMatrix"], r["noiseMatrix"], baseline, r["T"])
        flag = "" if attempt == 0 else "  [DEMAND CUT]"
        print(f"  U={U:<5} {variant:<14} avg={mx_avg:6.3f} peak={mx_peak:6.3f} "
              f"T={r['T']} demand={demand_pct(mult)}% travel={avg_tt} "
              f"({dt:.0f}s){flag}", flush=True)
        return

    print(f"  U={U:<5} INFEASIBLE at every fleet variant", flush=True)


def run(combo, mode):
    out_dir = ROUTES / combo / "equal_allocation" / mode
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n=== {combo} / {mode} ===", flush=True)
    log = []
    t0 = time.time()
    for U in U_VALUES:
        run_one(combo, mode, U, out_dir, log)
    log_dir = out_dir / "_search_log"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "attempts.csv").write_text(
        "mode,U,variant,N,totalTraffic,demandPct,status,reason,elapsed_s\n"
        + "\n".join(log) + "\n", encoding="utf-8")
    print(f"=== {combo}/{mode} done in {time.time() - t0:.0f}s ===", flush=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mode = "both"
    if "--mode" in sys.argv:
        mode = sys.argv[sys.argv.index("--mode") + 1]
    modes = list(MODES) if mode == "both" else [mode]
    combos = COMBOS if (not args or args[0] == "all") else [args[0]]
    for combo in combos:
        for m in modes:
            run(combo, m)


if __name__ == "__main__":
    main()
