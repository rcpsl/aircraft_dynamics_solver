"""Prioritarian for the 45 dB collection -- priority to the worst-off.

The objective minimises SUMMED ADDED dB over `protectedStations`, a set chosen
by a *lens* over community attributes. There is no selection rule here that
could be got wrong the way equal allocation's "largest value below the target"
was: the solver minimises the fairness quantity directly.

LENSES ARE IMPORTED, NEVER TRANSCRIBED. lens_definitions parses the workbook and
applies a column selector. The hand-written lists in the older collection were
taken with `SWAP = {6: 8, 8: 6}` in force and are wrong by one station.

D = 18 IS DELIBERATELY NON-BINDING. At 45 dB per craft the maximum added dB
anywhere is 17.56, so D=18 cannot bind. This domain's constraint IS its
objective. D is not a cap to be tuned here, and a run whose noise sits well
under 18 has not "satisfied" anything.

BOTH MODES RUN THE FULL FLEET AT 100% DEMAND.

  community : prioritarian alone.        N=14, real multipliers, T_max=5.
  people    : prioritarian + utilitarian. N=14, real multipliers, T_max=4,
              stationTransitWeights = PEOPLE_WEIGHTS.

`stationTransitWeights` is only read when optimize_util is true (see the
`if optimize_util:` guard around eff_w_util in optimize_objectives -- with it
false, eff_w_util is 0 and the weighted transit term never enters the
objective). That is the whole reason people mode carries a utilitarian term:
without it the population weighting would be silently dropped and the mode would
be identical to community mode.

WHY people MODE USES T_max=4 AND community USES 5.

people mode previously ran N=7 with unit multipliers -- 12.5% of base traffic --
because the combined prioritarian+utilitarian objective blew the phase-2 budget
at N=14. That was a solver limit wearing a "demandFulfilledPct" label, which
reads as a service cut caused by the fairness policy. It was not one: every
aircraft in that scenario flew and arrived. Measured alternatives, all at
combo s2-65_s6-55, lens low_income:

  N=14 FULL_MULT T_max=5, 240 s budget   -> phase2_failed at  268 s
  N=14 FULL_MULT T_max=5, 1500 s budget  -> phase2_failed at 1521 s  (6x is not enough)
  N=14 mult=1    T_max=5,  600 s budget  -> phase2_failed at  606 s  (not the multipliers)
  N=14 FULL_MULT T_max=4                 -> SAT in 19 s

So T is the only lever that works, and lowering it is nearly free HERE for a
reason specific to this map: T_min is 4, and at T=4 there is exactly ONE 1->16
path (`1-6-11-16`), so the routing is forced. At T=5 sixteen 4-hop paths open
up -- and the solver still puts every aircraft on that same diagonal and parks
it (see any community/*.csv routing block). The freedom exists and goes unused,
so T=4 yields the identical spatial routing and the identical PEAK added dB.

What does change: `avg` added dB is averaged over T, so the T=4 figure uses a
÷4 denominator against community's ÷5 and reads higher (2.8982 vs 2.3185) for
the same physical routing. Compare the two modes on PEAK, not AVG.

What is lost: at T=4 you may no longer say the objective *chose* this routing --
it was the only one available. The T=5 community files are what establish that
the objective picks the diagonal when it does have alternatives.

DEGENERACY. Every aircraft starts or ends at station 1 or 16, so those carry
traffic at every timestep by construction, and station 11 sits on the unique
shortest path 1-6-11-16. A protected set containing none of {1, 11, 16} can be
driven to exactly zero, at which point every zero-achieving routing ties and Z3
picks one arbitrarily -- the lens then carries no fairness signal even though
the output file differs from its neighbours. `protectedNoise` is therefore
written into EVERY preamble: it is the direct evidence of whether the lens did
anything, and 0.0 means it did not.

Usage:
    python run_prioritarian.py <combo> [--mode community|people|both]
    python run_prioritarian.py all
"""
import sys
import time
from pathlib import Path

import z3

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths45 import ROUTES
from _helpers45 import (
    COMBOS, FULL_MULT, PEOPLE_WEIGHTS, baseline_for, subsample_fleet,
    demand_pct, solve_scenario, metric_maxima, write_full_csv, travel_stats,
)
from lens_definitions import LENSES, SELECTORS

D_FIXED = 18.0      # non-binding by construction: ceiling at 45 dB/craft is 17.56
U_FIXED = 50.0      # non-binding: no disparity cap in this domain
W_TIME = 0.1
W_PRIOR = 1.0
T_FLOOR = 4         # phase-1 T_min at full fleet -- identical in all four combos

# Same rescue policy as equal allocation: a phase-2 timeout is a solver budget
# limit, not infeasibility, and is never answered by cutting the fleet.
RETRY_SEEDS = [1, 7, 42]

# Both modes run the full 14-aircraft real-multiplier fleet: 56/56 traffic
# units, 100% demand. They differ in objective and in T_max only -- see the
# module docstring for the measurements behind people mode's T_max=4.
MODES = {
    "community": dict(n=14, mult=list(FULL_MULT), t_max=5, flags=dict(
        optimize_prior=True, w_prior=W_PRIOR,
        optimize_util=False, station_transit_weights=None)),
    "people": dict(n=14, mult=list(FULL_MULT), t_max=4, flags=dict(
        optimize_prior=True, w_prior=W_PRIOR,
        optimize_util=True, w_util=1.0,
        station_transit_weights=PEOPLE_WEIGHTS, util_noise_mode=False)),
}


def run_one(combo, mode, lens, out_dir, log):
    path = out_dir / f"{lens}.csv"
    if path.exists():
        print(f"  skip {path.name} (exists)", flush=True)
        return

    spec = MODES[mode]
    n, mult, t_max, flags = spec["n"], spec["mult"], spec["t_max"], spec["flags"]
    start, end = subsample_fleet(n)
    baseline = baseline_for(combo)
    protected = LENSES[lens]

    t0 = time.time()
    r = solve_scenario(n, D_FIXED, U_FIXED, t_max, baseline, mult, start, end,
                       protected_stations=protected, w_time=W_TIME, **flags)
    dt = time.time() - t0
    status = r.get("status")
    log.append(f"{mode},{lens},\"{protected}\",{n},{demand_pct(mult)},{status},"
               f"{r.get('reason','')},{r.get('protectedNoise','')},{dt:.1f}")

    # phase_2 timeout != infeasible. Phase 1 already proved a feasible routing
    # exists at this fleet; only the optimizer ran out of its 240 s budget.
    # Reseed and retry -- Z3's search is not deterministic run-to-run. If it
    # still fails, leave the file unwritten. Cutting the fleet here would report
    # a solver limitation as a service cut, which is false.
    if status == "phase2_failed":
        for seed in RETRY_SEEDS:
            z3.set_param("smt.random_seed", seed)
            z3.set_param("sat.random_seed", seed)
            t1 = time.time()
            r = solve_scenario(n, D_FIXED, U_FIXED, t_max, baseline, mult, start,
                               end, protected_stations=protected, w_time=W_TIME,
                               **flags)
            dt1 = time.time() - t1
            log.append(f"{mode},{lens},\"{protected}\",{n},{demand_pct(mult)},"
                       f"{r.get('status')},seed{seed}:{r.get('reason','')},"
                       f"{r.get('protectedNoise','')},{dt1:.1f}")
            print(f"  {lens:<16} phase2 retry seed={seed} -> {r.get('status')} "
                  f"({dt1:.0f}s)", flush=True)
            if r.get("status") == "sat":
                break
        z3.set_param("smt.random_seed", 0)
        z3.set_param("sat.random_seed", 0)
        status = r.get("status")
        if status != "sat":
            print(f"  {lens:<16} PHASE-2 UNRESOLVED at {demand_pct(mult)}% demand "
                  f"-- feasible but not optimizable in budget; file NOT written, "
                  f"demand NOT cut", flush=True)
            return

    if status != "sat":
        print(f"  {lens:<16} {status}/{r.get('reason','')} ({dt:.0f}s) -- genuine "
              f"infeasibility, file NOT written", flush=True)
        return

    pn = r.get("protectedNoise")
    mx_avg, mx_peak = metric_maxima(r, baseline)
    avg_tt, _, _ = travel_stats(r["paths"], mult, start, end, r["T"])
    meta = {
        "domain": "prioritarian", "combo": combo, "mode": mode, "lens": lens,
        "protectedStations": protected,
        "lensSelector": SELECTORS[lens][0].replace(",", ";"),
        # The solver's own objective readout. 0.0 == the protected set was driven
        # to zero, every zero-achieving routing tied, and Z3's pick among them is
        # arbitrary -- this file's routing then carries NO fairness signal.
        "protectedNoise": pn,
        "protectedNoiseDegenerate": (pn == 0.0),
        "D": D_FIXED, "Dbinding": False,
        "Drole": "non-binding by construction (max added dB at 45 dB/craft is 17.56)",
        "U": U_FIXED, "Ubinding": False,
        "hardT": False, "T_max": t_max, "T_floor": T_FLOOR,
        # At T == the phase-1 floor there is exactly one 1->16 path (1-6-11-16),
        # so the routing is forced and no objective could have altered it. Above
        # the floor the solver had 16 four-hop alternatives and still chose the
        # diagonal -- freedom present but unused. Either way the reader needs to
        # know which regime this file is in before crediting the objective.
        "routingForcedByT": r["T"] <= T_FLOOR,
        "weightTime": W_TIME,
        "optimizePrioritarian": True, "weightPrioritarian": W_PRIOR,
        "optimizeUtilitarian": flags.get("optimize_util", False),
        "maxAvgAddedDb": round(mx_avg, 4),
        "maxPeakAddedDb": round(mx_peak, 4),
        # write_full_csv stamps demandFulfilledPct = sum(mult)/56. Both modes now
        # run the full fleet, so it is 100.0 -- but the name invites reading any
        # value below 100 as demand the fairness policy refused to serve, which
        # it never is. Every aircraft in a solved scenario flies and arrives; the
        # figure is model scope, not unmet demand.
        "demandRole": "share of the 56-unit base fleet modelled; not unserved demand",
        # avg added dB is averaged over T, so it is denominator-sensitive: the
        # T=4 and T=5 modes are NOT directly comparable on avg. Peak is.
        "avgAddedDbComparability": f"averaged over T={r['T']}; compare modes on peak, not avg",
    }
    # People mode passes both of these to the solver, so both must be in the
    # file. The 55 dB collection omitted them and its people-mode files could
    # therefore not be reproduced from themselves.
    if flags.get("optimize_util"):
        meta["weightUtilitarian"] = flags["w_util"]
        meta["stationTransitWeights"] = flags["station_transit_weights"]

    write_full_csv(path, meta, r["paths"], mult, start, end,
                   r["countMatrix"], r["noiseMatrix"], baseline, r["T"])
    degen = "  [DEGENERATE: protectedNoise=0]" if pn == 0.0 else ""
    print(f"  {lens:<16} protectedNoise={pn:<8} avg={mx_avg:6.3f} "
          f"peak={mx_peak:6.3f} T={r['T']} demand={demand_pct(mult)}% "
          f"travel={avg_tt} ({dt:.0f}s){degen}", flush=True)


def run(combo, mode):
    out_dir = ROUTES / combo / "prioritarian" / mode
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n=== {combo} / {mode} (N={MODES[mode]['n']}, "
          f"demand={demand_pct(MODES[mode]['mult'])}%) ===", flush=True)
    log = []
    t0 = time.time()
    for lens in LENSES:
        run_one(combo, mode, lens, out_dir, log)
    log_dir = out_dir / "_search_log"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "attempts.csv").write_text(
        "mode,lens,protectedStations,N,demandPct,status,reason,protectedNoise,"
        "elapsed_s\n" + "\n".join(log) + "\n", encoding="utf-8")
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
