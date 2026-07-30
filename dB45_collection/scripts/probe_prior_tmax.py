"""Can people mode run at 100% demand if T_max comes down?

people mode was cut to N=7 with unit multipliers (12.5% of base traffic) purely
because the combined prioritarian+utilitarian objective exceeded phase 2's 240 s
budget at N=14. That cut is a solver limitation wearing a service-cut label, and
it also breaks the mode comparison: community-vs-people stops isolating
population weighting once the two modes differ in fleet size too.

T is the other lever on phase-2 cost. The search is over N*T location variables
plus per-timestep noise terms, so shrinking T shrinks the problem without
touching demand. solve_scenario uses T_use = max(T_min_from_phase1, T_max), so
T_max can only ever RAISE T above the phase-1 floor -- lowering it past T_min
does nothing and is silently ignored.

What lowering T costs: soft-T slack is what lets aircraft stagger their
departures and spread noise across time. At T == T_min there is no slack left,
every aircraft must move every step, and the w_time penalty term goes inert.
That is a real modelling change, not a free win, so it gets measured here
rather than assumed.

Reports, per combo: the phase-1 T floor at full fleet, and whether people mode
(N=14, FULL_MULT, PEOPLE_WEIGHTS, prior+util) completes phase 2 at each
candidate T_max, walking down from the current 5.

Usage: python probe_prior_tmax.py <combo> [--lens low_income]
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths45 import PROBES
from _helpers45 import (
    FULL_MULT, PEOPLE_WEIGHTS, baseline_for, subsample_fleet,
    phase1_feasible, solve_scenario, metric_maxima, demand_pct,
)
from lens_definitions import LENSES

D, U, W_TIME, W_PRIOR, W_UTIL = 18.0, 50.0, 0.1, 1.0, 1.0
N = 14


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    combo = args[0] if args else "s2-65_s6-55"
    lens = (sys.argv[sys.argv.index("--lens") + 1]
            if "--lens" in sys.argv else "low_income")

    baseline = baseline_for(combo)
    mult = list(FULL_MULT)
    start, end = subsample_fleet(N)
    protected = LENSES[lens]

    print(f"=== T_max probe: {combo}, lens={lens}, N={N}, "
          f"demand={demand_pct(mult)}% ===", flush=True)

    ok, t_min, dt, status = phase1_feasible(D, U, N, mult, start, end, baseline)
    print(f"phase-1 floor: status={status} T_min={t_min} ({dt:.1f}s)", flush=True)
    if not ok:
        print("phase 1 infeasible -- nothing to probe")
        return

    PROBES.mkdir(parents=True, exist_ok=True)
    out = PROBES / f"prior_tmax_{combo}.csv"
    rows = ["combo,lens,N,demandPct,T_max,T_used,status,protectedNoise,"
            "maxAvgAdded,maxPeakAdded,elapsed_s"]

    # Walk down from the current setting to the phase-1 floor. Below T_min the
    # request is a no-op (max() clamps it), so stop there.
    for t_max in range(5, t_min - 1, -1):
        t0 = time.time()
        r = solve_scenario(
            N, D, U, t_max, baseline, mult, start, end,
            optimize_prior=True, protected_stations=protected, w_prior=W_PRIOR,
            optimize_util=True, w_util=W_UTIL,
            station_transit_weights=PEOPLE_WEIGHTS, util_noise_mode=False,
            w_time=W_TIME,
        )
        dt = time.time() - t0
        st = r.get("status")
        if st == "sat":
            pn = r.get("protectedNoise")
            mx_a, mx_p = metric_maxima(r, baseline)
            print(f"  T_max={t_max} -> T={r['T']} SAT  protectedNoise={pn} "
                  f"avg={mx_a:.4f} peak={mx_p:.4f} ({dt:.0f}s)", flush=True)
            rows.append(f"{combo},{lens},{N},{demand_pct(mult)},{t_max},"
                        f"{r['T']},sat,{pn},{mx_a:.4f},{mx_p:.4f},{dt:.1f}")
        else:
            print(f"  T_max={t_max} -> {st}/{r.get('reason')} ({dt:.0f}s)",
                  flush=True)
            rows.append(f"{combo},{lens},{N},{demand_pct(mult)},{t_max},,"
                        f"{st}/{r.get('reason')},,,,{dt:.1f}")

    out.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"=== -> {out} ===", flush=True)


if __name__ == "__main__":
    main()
