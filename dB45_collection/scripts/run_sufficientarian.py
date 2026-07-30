"""Sufficientarian domain for the 45 dB collection -- D as a real floor of
acceptable conditions, with the objective minimising NOISE rather than transit.

WHAT THIS DOMAIN IS

Sufficientarianism sets a floor of acceptable conditions: no station may exceed
`D` added dB at any timestep. `U = 999` switches the disparity constraint off
entirely, so the absolute cap is the only fairness constraint in force. Within
that cap, the optimiser is free -- and what it optimises is the whole design
question.

THE OBJECTIVE: COUNT-BASED, NOT dB-SUM

    optimize_util   = True
    util_noise_mode = False    # count-based transit term, NOT the summed-dB term
    w_util          = 1.0

This is the `else` branch of `if util_noise_mode:` in optimize_objectives
(solver_server_dB.py) -- the term the solver's own comments call "the
count-based utilitarian term". It minimises

    sum over aircraft i, timestep t of:  multiplier[i] * weight(station of i)
    for every timestep at which i is in transit

i.e. weighted aircraft-timesteps in transit. No solver change was made or is
required; only kwargs differ.

HISTORY OF THIS DECISION. The domain was first specified with
`util_noise_mode=True`, minimising summed added dB directly. That was built and
run, and it did not survive contact with the solver: the summed-dB objective
builds a nonlinear dB table lookup for all 16 stations at every timestep, and
at D=3 (which forces T up to 6-7) phase 2 exhausted its 240 s budget on the
initial attempt and on all reseeded retries, in all four combos. It was
switched to the count-based term, which is linear in booleans and cheap.

*** WHAT THIS CHANGES ABOUT THE DOMAIN'S POLITICS -- READ THIS ***

The count objective is BASELINE-BLIND. It never sees which stations are loud;
no baseline and no dB table appears anywhere in it. Two consequences:

  1. The regressive pull of the summed-dB objective is GONE. Minimising summed
     dB would have pushed traffic onto the already-loudest stations, because
     added noise is 10*log10(1 + n*10^((45-baseline)/10)) -- a 65 dB station
     gains only 1.93 dB with the full 56-flight fleet on it, where a 45 dB
     station gains 17.56 dB, so loud stations are where noise is cheapest to
     add. The count objective has no such preference and does not concentrate
     burden on already-noisy communities by construction.

  2. But the PHYSICS is unchanged, and it still decides who suffers. Where the
     count objective happens to put traffic still determines the dB outcome,
     and the masking asymmetry above still holds. So the traffic distribution
     in these files must still be read against the baselines, not assumed
     neutral. The D cap is now the ONLY part of this setup that references
     baselines at all.

MODES
  unweighted : station_transit_weights = None -- every station weighted
               equally, so this reduces to minimising total aircraft transit
               time. Note this points the same direction as the soft-T w_time
               term already does; expect it to be close to plain efficiency.
  weighted   : station_transit_weights = PEOPLE_WEIGHTS -- aircraft-presence is
               charged at the station's population weight, so traffic is pushed
               AWAY from high-population stations. "Keep aircraft away from
               where people are." Watch station 15: population Low (weight 1)
               makes it the cheapest sink in the grid, and it is also a 65 dB
               station -- so weighted mode can reproduce loud-station
               concentration for an entirely different reason than the
               summed-dB objective would have.

PEOPLE_WEIGHTS is used exactly as imported: station 6 is a Create-Your-Own slot
(neutral 5) and station 8 is Dove Springs (High population, 10). The 55 dB
collection had these transposed; that is not corrected back here.

CAPS. D = 3, 8, 18 are real constraints, not selection labels. Two of them
cannot bind at 45 dB per craft: the maximum added dB anywhere in this model is
17.56 (all 56 weighted flights on a 45 dB station), so D=18 is unreachable
outright, and D=8 is unreachable at the 55 dB stations (ceiling 8.20) and the
65 dB stations (ceiling 1.93) -- it binds only at the 45 dB stations. Both are
run anyway; if D=8 and D=18 come out identical that is a real result about the
cap ladder at this aircraft level, not a bug.

FLEET POLICY. The full 14-aircraft real-multiplier fleet (100% demand) is used
wherever the cap permits. Only on a genuine `unsat` does the run step down
through FLEET_ORDER and take the first feasible variant -- the highest demand
achievable under that cap. Never further than necessary, and never a smaller
fleet merely because it is quieter. Where a cap forces a cut, that cut IS the
finding -- "how much service survives this floor" -- so it is written into the
preamble as `fullFleetFeasible` and `demandFulfilledPct`.

Usage:
    python run_sufficientarian.py <combo> [--mode unweighted|weighted|both]
    python run_sufficientarian.py all [--mode both]
"""
import math
import sys
import time
from pathlib import Path

import z3

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths45 import ROUTES
from _helpers45 import (
    COMBOS, PEOPLE_WEIGHTS, AIRCRAFT_DB, MAX_TRAFFIC, baseline_for,
    variant_to_fleet, demand_pct, solve_scenario, metric_maxima,
    write_full_csv, travel_stats,
)
# _helpers45 has already put the repo root on sys.path and imported this, so
# this is the same module object the solve path uses.
import solver_server_dB as S

DEFAULT_PHASE2_TIMEOUT_MS = S.SOLVE_TIMEOUT_MS  # 240000; captured before any override

U_FIXED = 999.0     # disparity deliberately off: only the absolute cap matters
T_MAX = 7
W_TIME = 0.1
W_UTIL = 1.0
D_VALUES = [3.0, 8.0, 18.0]

# Tried in descending demand order -- the first feasible one wins, so the run
# serves as much demand as the cap allows.
FLEET_ORDER = ["baseline_mult", "N14_mult1", "N7_mult1", "N4_mult1"]

# Z3's search is not deterministic run-to-run and phase-2 timeouts have been
# observed to clear on a reseeded retry. Used only to rescue phase2_failed --
# never to change a genuine unsat.
RETRY_SEEDS = [1, 7, 42]

MODES = {
    "unweighted": dict(station_transit_weights=None),
    "weighted": dict(station_transit_weights=PEOPLE_WEIGHTS),
}

# The objective is baseline-blind, so it carries no built-in preference for
# loud stations -- but the dB physics that decides who actually suffers is
# unchanged. This travels with every file so the distinction is not lost.
OBJECTIVE_NOTE = (
    "count-based: minimises weighted aircraft-timesteps in transit. "
    "BASELINE-BLIND -- the objective never sees which stations are loud, "
    "so it does not concentrate burden on already-noisy stations by "
    "construction (as a summed-dB objective would). But added dB still "
    "depends on baseline (65 dB station gains 1.93 dB at full fleet vs "
    "17.56 dB at 45 dB), so read the traffic distribution against the "
    "baselines rather than assuming it is neutral"
)

# The single most important caveat for anyone reading these numbers. D is a
# CAP, not a target: it forbids exceeding, and gives the solver no reason at
# all to go below. Since the count objective does not contain noise, the dB
# values in this file are not minimised -- they are simply whatever transit
# minimisation happened to produce within the cap. Measured consequence: in
# both s6-45 combos, relaxing D from 8 to 18 let the optimiser buy one
# timestep of travel time (4.089 -> 3.000) by raising peak added dB from
# 7.782 to 14.771. A looser cap did not leave the answer unchanged; it
# licensed a louder one.
CAP_BEHAVIOUR_WARNING = (
    "D is a CAP, not a target -- it forbids exceeding and gives no incentive "
    "to go below, and the objective does not contain noise. The dB values "
    "here are NOT minimised; they are whatever transit minimisation produced "
    "within the cap, and they can sit right against it. Relaxing the cap "
    "licenses louder outcomes rather than leaving them unchanged (measured: "
    "s6-45 combos, D=8 -> D=18 raised peak added dB 7.782 -> 14.771 to save "
    "one timestep of travel). Do not read these values as optimised-for-quiet"
)


def added_db_ceiling(baseline_m, weighted_count):
    """Added dB at a station of this baseline with `weighted_count` craft on it."""
    return 10 * math.log10(1 + weighted_count * 10 ** ((AIRCRAFT_DB - baseline_m) / 10))


def d_can_bind(D, baseline, total_traffic):
    """True if this cap excludes any routing that is physically reachable.

    The most added dB any station can take is the whole weighted fleet parked on
    the quietest station. If D sits above that ceiling, no routing could ever
    have violated it and the cap is inert -- which is the case for D=18 at
    45 dB per craft (ceiling 17.56).
    """
    ceiling = max(added_db_ceiling(b, total_traffic) for b in baseline)
    return D < ceiling


def run_one(combo, mode, D, out_dir, log):
    """Solve one (combo, mode, D) at the largest feasible fleet and emit it."""
    baseline = baseline_for(combo)
    stw = MODES[mode]["station_transit_weights"]
    path = out_dir / f"D{int(D)}.csv"
    if path.exists():
        print(f"  skip {path.name} (exists)", flush=True)
        return

    flags = dict(optimize_util=True, optimize_prior=False, optimize_prop=False,
                 w_util=W_UTIL, util_noise_mode=False,
                 station_transit_weights=stw)

    for attempt, variant in enumerate(FLEET_ORDER):
        n, mult, start, end = variant_to_fleet(variant)
        t0 = time.time()
        r = solve_scenario(n, D, U_FIXED, T_MAX, baseline, mult, start, end,
                           w_time=W_TIME, **flags)
        dt = time.time() - t0
        status = r.get("status")
        log.append(f"{mode},{D},{variant},{n},{sum(mult)},{demand_pct(mult)},"
                   f"{status},{r.get('reason','')},{dt:.1f}")

        # A phase-2 timeout is NOT infeasibility. Phase 1 already proved a
        # feasible routing exists at this fleet size -- only the optimiser ran
        # out of its budget. Cutting the fleet here would report a solver
        # limitation as though the cap had forced a service cut, which is false.
        # Retry with different Z3 seeds, and if that fails leave the cell
        # unwritten rather than fabricating a demand cut.
        if status == "phase2_failed":
            for seed in RETRY_SEEDS:
                z3.set_param("smt.random_seed", seed)
                z3.set_param("sat.random_seed", seed)
                t1 = time.time()
                r = solve_scenario(n, D, U_FIXED, T_MAX, baseline, mult, start,
                                   end, w_time=W_TIME, **flags)
                dt1 = time.time() - t1
                log.append(f"{mode},{D},{variant},{n},{sum(mult)},"
                           f"{demand_pct(mult)},{r.get('status')},"
                           f"seed{seed}:{r.get('reason','')},{dt1:.1f}")
                print(f"  D={D:<5} {variant:<14} phase2 retry seed={seed} -> "
                      f"{r.get('status')} ({dt1:.0f}s)", flush=True)
                if r.get("status") == "sat":
                    break
            z3.set_param("smt.random_seed", 0)
            z3.set_param("sat.random_seed", 0)
            status = r.get("status")
            if status != "sat":
                print(f"  D={D:<5} {variant:<14} PHASE-2 UNRESOLVED at "
                      f"{demand_pct(mult)}% demand -- feasible but not "
                      f"optimizable in budget; NOT cutting demand", flush=True)
                return

        if status != "sat":
            print(f"  D={D:<5} {variant:<14} {status}/{r.get('reason','')} "
                  f"({dt:.0f}s) -> stepping down (genuine infeasibility)",
                  flush=True)
            continue

        mx_avg, mx_peak = metric_maxima(r, baseline)
        avg_tt, min_tt, max_tt = travel_stats(r["paths"], mult, start, end, r["T"])
        meta = {
            "domain": "sufficientarian", "combo": combo, "mode": mode,
            "D": D, "Drole": "hard floor of acceptable conditions "
                             "(no station may exceed D added dB at any timestep)",
            "Dbinding": d_can_bind(D, baseline, sum(mult)),
            "U": U_FIXED, "Urole": "disparity deliberately off",
            "hardT": False, "T_max": T_MAX, "weightTime": W_TIME,
            "optimizeUtilitarian": True, "utilNoiseMode": False,
            "weightUtilitarian": W_UTIL,
            "objective": "minimise weighted aircraft-timesteps in transit "
                         "(count-based term, NOT the summed-dB term)",
            "objectiveNote": OBJECTIVE_NOTE,
            "capBehaviourWarning": CAP_BEHAVIOUR_WARNING,
            "variant": variant, "fullFleetFeasible": attempt == 0,
            "phase2TimeoutMs": S.SOLVE_TIMEOUT_MS,
            "maxAvgAddedDb": round(mx_avg, 4),
            "maxPeakAddedDb": round(mx_peak, 4),
        }
        if stw is not None:
            meta["stationTransitWeights"] = stw
        # The solver's own objective readout -- direct evidence the objective
        # was actually in force. Count mode reports totalTransit, not
        # totalUtilNoise; keep whichever is present rather than assuming.
        for key in ("totalTransit", "totalUtilNoise"):
            if key in r:
                meta[key] = r[key]

        write_full_csv(path, meta, r["paths"], mult, start, end,
                       r["countMatrix"], r["noiseMatrix"], baseline, r["T"])
        flag = "" if attempt == 0 else "  [DEMAND CUT]"
        print(f"  D={D:<5} {variant:<14} avg={mx_avg:6.3f} peak={mx_peak:6.3f} "
              f"T={r['T']} demand={demand_pct(mult)}% travel={avg_tt} "
              f"({dt:.0f}s){flag}", flush=True)
        return

    print(f"  D={D:<5} INFEASIBLE at every fleet variant", flush=True)


def run(combo, mode):
    out_dir = ROUTES / combo / "sufficientarian" / mode
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n=== {combo} / {mode} ===", flush=True)
    log = []
    t0 = time.time()
    for D in D_VALUES:
        run_one(combo, mode, D, out_dir, log)
    log_dir = out_dir / "_search_log"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "attempts.csv").write_text(
        "mode,D,variant,N,totalTraffic,demandPct,status,reason,elapsed_s\n"
        + "\n".join(log) + "\n", encoding="utf-8")
    print(f"=== {combo}/{mode} done in {time.time() - t0:.0f}s ===", flush=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mode = "both"
    if "--mode" in sys.argv:
        mode = sys.argv[sys.argv.index("--mode") + 1]
    # Phase-2 budget override. Set on the imported solver module, NOT by editing
    # solver_server_dB.py -- optimize_objectives reads the global at call time
    # (`opt.set("timeout", SOLVE_TIMEOUT_MS)`), so assigning here is sufficient
    # and leaves the solver file untouched. The value in force is recorded in
    # every preamble as `phase2TimeoutMs`, because a cell that only solved under
    # a raised budget is not the same evidence as one that solved under the
    # default and the file has to say which it was.
    if "--timeout-ms" in sys.argv:
        S.SOLVE_TIMEOUT_MS = int(sys.argv[sys.argv.index("--timeout-ms") + 1])
        print(f"phase-2 timeout overridden: {DEFAULT_PHASE2_TIMEOUT_MS} -> "
              f"{S.SOLVE_TIMEOUT_MS} ms", flush=True)
    modes = list(MODES) if mode == "both" else [mode]
    combos = COMBOS if (not args or args[0] == "all") else [args[0]]
    for combo in combos:
        for m in modes:
            run(combo, m)


if __name__ == "__main__":
    main()
