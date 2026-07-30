"""Utilitarian domain for the 45 dB collection.

THE QUESTION THIS DOMAIN ASKS

"Route so the total burden is smallest" -- optimizeUtilitarian minimises the
summed transit cost, with no protected stations and no proportional stations.
There is no redistribution term at all; whatever spreading happens is a side
effect of the D cap and the soft-T schedule, not of the objective.

TWO SUB-DOMAINS, ONE PARAMETER APART

  utilitarian       D = 12.0 everywhere.
  utilitarian_peak  D = the phase-1 feasibility floor from data/probes/floors.csv
                    (2.0 for the two s6-55 combos, 4.0 for the two s6-45 combos).

At 45 dB per craft the *ceiling* on added noise is 8.20 dB at a 55 dB station
and 1.93 dB at a 65 dB station, so D = 12 is above the physical maximum
everywhere except the four 45 dB-baseline stations (4, 13, 14, and station 6 in
the s6-45 combos). The `utilitarian` sub-domain is therefore expected to be
nearly or entirely unconstrained; `utilitarian_peak` presses D right down onto
the floor where it must bind. If the two come back identical for a combo, that
is the finding -- it says D = 12 selected nothing that the objective and the
adjacency graph were not already going to pick.

TWO WEIGHT MODES

  no_weight  station_transit_weights = None. Every station's transit costs the
             same, so "total burden" counts vehicle-steps.
  weighted   station_transit_weights = PEOPLE_WEIGHTS. Transit through a
             high-population station costs more, so "total burden" counts
             people exposed. This is the expensive objective -- it has timed out
             at the 240 s phase-2 budget elsewhere in this collection.

Note that PEOPLE_WEIGHTS here puts weight 5 on station 6 (Create-Your-Own slot
B, neutral) and weight 10 on station 8 (Dove Springs, High population). The
55 dB collection had those two transposed; this is not a bug to be "fixed".

Usage:
    python run_utilitarian.py <combo> [--sub utilitarian|utilitarian_peak|both]
    python run_utilitarian.py all
"""
import sys
import time
from pathlib import Path

import z3

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _helpers45 as H
from _paths45 import ROUTES
from _helpers45 import (
    COMBOS, PEOPLE_WEIGHTS, FULL_MULT, FULL_START, FULL_END,
    baseline_for, solve_scenario, metric_maxima, write_full_csv, travel_stats,
)

# Phase-2 compute budget, in seconds. The solver's own default is 240 s
# (SOLVE_TIMEOUT_MS); `--phase2-budget` raises it for this process only, by
# rebinding the module attribute that optimize_objectives reads at call time.
# solver_server_dB.py itself is NOT edited -- this collection never edits it.
#
# This is a COMPUTE budget, not a design parameter: at the D floor the feasible
# region is a needle with huge aircraft-permutation symmetry, so z3.Optimize
# needs longer to *prove* no better routing exists (phase 1 already found one).
# A larger budget cannot change which routing is optimal; it can only let the
# same optimum be certified instead of timing out. Every file records the
# budget it was solved under so cells are never silently incomparable.
PHASE2_BUDGET_S = H.S.SOLVE_TIMEOUT_MS / 1000

N = 14
U_FIXED = 50.0
T_MAX = 7
W_TIME = 0.1

D_UTILITARIAN = 12.0

# Phase-1 D floors, read off data/probes/floors.csv (smallest probed D whose
# find_min_T is sat at baseline_mult / 100% demand). Not re-searched here.
D_FLOOR = {
    "s2-65_s6-55": 2.0,
    "s2-55_s6-55": 2.0,
    "s2-65_s6-45": 4.0,
    "s2-55_s6-45": 4.0,
}

# Same rescue policy as equal_allocation: reseeding only ever rescues a
# phase-2 timeout, and never converts a genuine unsat.
RETRY_SEEDS = [1, 7, 42]

MODES = {
    "no_weight": None,
    "weighted": PEOPLE_WEIGHTS,
}

SUBDOMAINS = ["utilitarian", "utilitarian_peak"]


def d_for(sub, combo):
    return D_UTILITARIAN if sub == "utilitarian" else D_FLOOR[combo]


def run_one(combo, sub, mode, log):
    """Solve and write one (combo, sub-domain, weight mode) cell."""
    out_dir = ROUTES / combo / sub / mode
    path = out_dir / "result.csv"
    if path.exists():
        print(f"  skip {sub}/{mode} (exists)", flush=True)
        return

    D = d_for(sub, combo)
    baseline = baseline_for(combo)
    weights = MODES[mode]
    mult, start, end = list(FULL_MULT), list(FULL_START), list(FULL_END)

    flags = dict(optimize_util=True, w_util=1.0, optimize_prior=False,
                 optimize_prop=False, station_transit_weights=weights,
                 util_noise_mode=False)

    t0 = time.time()
    r = solve_scenario(N, D, U_FIXED, T_MAX, baseline, mult, start, end,
                       w_time=W_TIME, **flags)
    dt = time.time() - t0
    status = r.get("status")
    log.append(f"{sub},{mode},{D},{status},{r.get('reason','')},{dt:.1f}")

    # phase-2 timeout is a solver budget limit, NOT infeasibility: phase 1
    # already proved a feasible routing exists at this D and this full fleet.
    # Reseed and retry; never cut the fleet, never rewrite it as unsat.
    if status == "phase2_failed":
        for seed in RETRY_SEEDS:
            z3.set_param("smt.random_seed", seed)
            z3.set_param("sat.random_seed", seed)
            t1 = time.time()
            r = solve_scenario(N, D, U_FIXED, T_MAX, baseline, mult, start, end,
                               w_time=W_TIME, **flags)
            dt1 = time.time() - t1
            log.append(f"{sub},{mode},{D},{r.get('status')},"
                       f"seed{seed}:{r.get('reason','')},{dt1:.1f}")
            print(f"  {sub}/{mode} phase2 retry seed={seed} -> "
                  f"{r.get('status')} ({dt1:.0f}s)", flush=True)
            if r.get("status") == "sat":
                break
        z3.set_param("smt.random_seed", 0)
        z3.set_param("sat.random_seed", 0)
        status = r.get("status")

    if status != "sat":
        kind = ("PHASE-2 UNRESOLVED (feasible, not optimizable in budget)"
                if status == "phase2_failed" else "INFEASIBLE")
        print(f"  {sub}/{mode} D={D} {kind}: {status}/{r.get('reason','')} "
              f"({dt:.0f}s) -- file NOT written", flush=True)
        return

    mx_avg, mx_peak = metric_maxima(r, baseline)
    avg_tt, min_tt, max_tt = travel_stats(r["paths"], mult, start, end, r["T"])
    meta = {
        "domain": sub, "combo": combo, "mode": mode,
        "D": D, "Drole": ("fixed 12.0 dB cap" if sub == "utilitarian"
                          else "phase-1 feasibility floor for this combo"),
        "U": U_FIXED,
        "hardT": False, "T_max": T_MAX, "weightTime": W_TIME,
        "optimizeUtilitarian": True, "weightUtilitarian": 1.0,
        "utilNoiseMode": False,
        "maxAvgAddedDb": round(mx_avg, 4),
        "maxPeakAddedDb": round(mx_peak, 4),
        "phase2BudgetSeconds": PHASE2_BUDGET_S,
    }
    if weights is not None:
        meta["stationTransitWeights"] = weights
    # The objective's own value, as run_and_write would stamp it. For THIS
    # domain it is the load-bearing readout: totalTransit is the utilitarian
    # objective, so it is the only direct evidence of whether re-weighting the
    # stations changed what was being minimised, as opposed to merely changing
    # which of several equally-costly routings Z3 happened to return.
    for key in ("totalTransit", "totalUtilNoise"):
        if key in r:
            meta[key] = r[key]
    write_full_csv(path, meta, r["paths"], mult, start, end,
                   r["countMatrix"], r["noiseMatrix"], baseline, r["T"])
    print(f"  {sub}/{mode} D={D:<5} avg={mx_avg:6.3f} peak={mx_peak:6.3f} "
          f"T={r['T']} travel={avg_tt} ({dt:.0f}s)", flush=True)


def run(combo, subs):
    print(f"\n=== {combo} : utilitarian ===", flush=True)
    log = []
    t0 = time.time()
    for sub in subs:
        for mode in MODES:
            run_one(combo, sub, mode, log)
    log_dir = ROUTES / combo / "utilitarian" / "_search_log"
    log_dir.mkdir(parents=True, exist_ok=True)
    # Budget-tagged so an extended-budget rerun cannot overwrite the record of
    # which cells failed at the solver's default 240 s. The failures are part of
    # the result, not scratch output.
    name = ("attempts.csv" if PHASE2_BUDGET_S == 240.0
            else f"attempts_budget{PHASE2_BUDGET_S:.0f}s.csv")
    (log_dir / name).write_text(
        "subdomain,mode,D,status,reason,elapsed_s\n" + "\n".join(log) + "\n",
        encoding="utf-8")
    print(f"=== {combo} done in {time.time() - t0:.0f}s ===", flush=True)


def main():
    global PHASE2_BUDGET_S, RETRY_SEEDS
    argv = sys.argv
    flag_vals = set()
    for f in ("--sub", "--phase2-budget"):
        if f in argv:
            flag_vals.add(argv[argv.index(f) + 1])
    args = [a for a in argv[1:] if not a.startswith("--") and a not in flag_vals]

    sub = argv[argv.index("--sub") + 1] if "--sub" in argv else "both"
    subs = SUBDOMAINS if sub == "both" else [sub]

    if "--phase2-budget" in argv:
        PHASE2_BUDGET_S = float(argv[argv.index("--phase2-budget") + 1])
        H.S.SOLVE_TIMEOUT_MS = int(PHASE2_BUDGET_S * 1000)
        print(f"phase-2 budget raised to {PHASE2_BUDGET_S:.0f}s "
              f"(solver default 240s; solver_server_dB.py unmodified)", flush=True)
    if "--no-reseed" in argv:
        # A longer budget subsumes what reseeding was for: both exist to escape
        # an unlucky search trajectory, and paying 3 extra long attempts per
        # cell is not worth it. Kept as a flag so the default path is unchanged.
        RETRY_SEEDS = []

    combos = COMBOS if (not args or args[0] == "all") else [args[0]]
    for combo in combos:
        run(combo, subs)


if __name__ == "__main__":
    main()
