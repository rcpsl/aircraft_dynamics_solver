"""Generate the two proportional-benefit datasets by running the EXISTING Z3
solver (solver_server_dB) with its optimizeProportional objective — no new
solver, no code changes to solver_server_dB.

The benefit map (proportional_benefit.py) is deterministic and combo-independent
(income doesn't vary across combos — only baseline dB does). It yields two
station sets fed to the solver as `proportionalStations`:

  high_benefit  = benefit==3 tiles = {1,16}          (the vertiports)
  all_benefited = benefit>0  tiles = {1,2,5,6,16}     (+ downtown's adjacent tiles)

The solver's proportional term has a NEGATIVE coefficient (see solver_server_dB
optimize_objectives, "negative coefficient = maximize"): it MAXIMIZES noise at
those stations => burden follows benefit. Everything else mirrors the working
prioritarian community config (soft-T, T_max=5, D=18, full N=14 fleet — the
combo that reliably solves and leaves real route choice; see prioritarian
REPORT.md §5b).

Output: full_routes/<combo>/proportional/{high_benefit,all_benefited}.csv, same
format as the other full_routes files plus Benefit/Income/DemandServed columns.

Usage: python run_proportional.py            # all 4 combos, both datasets
       python run_proportional.py s2-55_s6-45
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _paths import REPO, ROUTES
sys.path.insert(0, str(REPO))  # for solver_server_dB
import solver_server_dB as S
from _solve_helpers import (
    ADJ, M, AIRCRAFT_DB, FULL_MULT, FULL_START, FULL_END, MAX_TRAFFIC,
    baseline_for, zone_stats, subsample_fleet,
)
from proportional_benefit import (
    build_station_income, compute_benefit, compute_demand_served,
    benefit_sets, tier_label,
)

COMBOS = ["s2-65_s6-55", "s2-65_s6-45", "s2-55_s6-55", "s2-55_s6-45"]
VERTIPORTS = [1, 16]
D, U, T_MAX, W_TIME, W_PROP = 18.0, 50.0, 5, 0.1, 1.0

# Per-mode fleet: high_benefit ({1,16}) is tractable at the full N=14 fleet;
# all_benefited reliably times out at N=14 (measured 253s, over the 240s Z3 budget)
# and needs the N=7 "every-other" fleet cut — same tractability fix and convention
# as prioritarian people-mode (REPORT.md §5d). N is held fixed across a mode's 4
# combos so combo-to-combo comparison stays clean.
MODE_N = {"high_benefit": 14, "all_benefited": 7}

# CYO user-choice scenarios. Only slot C (station 11, adjacent to vertiport 16)
# changes the benefit map: Low income (default) -> benefit 0; High income
# (Suburban Tech Campus) -> benefit 2, which adds st11 to the all_benefited set.
# Slots A/B are already the s2/s6 combo axes (Medium income either way); slot D
# isn't vertiport-adjacent. So the full CYO surface here is exactly these two
# scenarios, and only all_benefited differs between them (high_benefit's {1,16}
# set is CYO-invariant, so it's generated once under "default").
#   (label, cyo_choices, [(mode, filename_suffix)])
SCENARIOS = [
    ("default",  {},       [("high_benefit", ""), ("all_benefited", "")]),
    ("c11-tech", {11: 1},  [("all_benefited", "__c11-tech")]),
]


def build_overlay(cyo_choices):
    """(income, benefit, {mode->prop_station_set}) for a CYO choice."""
    income = build_station_income(cyo_choices)
    benefit = compute_benefit(VERTIPORTS, income, ADJ, M)
    high, allb = benefit_sets(benefit)
    return income, benefit, {"high_benefit": high, "all_benefited": allb}


def fleet(n):
    """(start, end, mult) for an n-aircraft fleet: full multipliers at N=14,
    else the every-other subsample with unit multipliers."""
    if n >= len(FULL_MULT):
        return list(FULL_START), list(FULL_END), list(FULL_MULT)
    start, end = subsample_fleet(n)
    return start, end, [1] * n


def solve_prop(baseline, prop_stations, start, end, mult):
    n = len(mult)
    p1 = S.find_min_T(n, M, D, U, ADJ, start, end, baseline, AIRCRAFT_DB, multipliers=mult)
    if p1["status"] != "sat":
        return p1
    T_use = max(p1["T"], T_MAX)
    return S.optimize_objectives(
        n, T_use, M, D, U, ADJ, start, end,
        optimize_util=False, optimize_prior=False, optimize_prop=True,
        protected_stations=[], proportional_stations=prop_stations,
        w_util=1.0, w_prior=1.0, w_prop=W_PROP,
        soft_T=True, w_time=W_TIME,
        prop_alloc=False, station_transit_weights=None, util_noise_mode=False,
        aircraft_multipliers=mult, baseline=baseline, aircraft_dB=AIRCRAFT_DB,
    )


def write_csv(path, meta, r, baseline, start, end, mult, demand, benefit, income):
    T = r["T"]
    n = len(mult)
    traffic = sum(mult)
    lines = [f"# {k},{v}" for k, v in meta.items()]
    lines += [
        f"# N,{n}",
        f"# aircraftMultipliers,{list(mult)}",
        f"# totalTraffic,{traffic}",
        f"# maxTraffic,{MAX_TRAFFIC}",
        f"# demandFulfilledPct,{round(100 * traffic / MAX_TRAFFIC, 2)}",
        f"Time Steps (T),{T}",
        "",
        "Routing (station per aircraft per timestep):",
        ",".join(["Aircraft", "Multiplier", "Start", "End"] + [f"T{t}" for t in range(T)]),
    ]
    for i in range(n):
        lines.append(",".join([str(i + 1), str(mult[i]), str(start[i]), str(end[i])]
                              + [str(p) for p in r["paths"][i][:T]]))
    lines += [
        "",
        "Zone,Avg Added dB,Avg Total dB,Peak Added dB,Peak Total dB,Avg Aircraft,Peak Aircraft,"
        "Benefit,Tier,Income,Demand Served",
    ]
    for row in zone_stats(r["countMatrix"], r["noiseMatrix"], baseline, T):
        m = row["zone"]
        lines.append(
            f"Zone {m},{row['avg_added']:.2f},{row['avg_total']:.2f},"
            f"{row['peak_added']:.2f},{row['peak_total']:.2f},"
            f"{row['avg_aircraft']:.2f},{row['peak_aircraft']},"
            f"{benefit[m]},{tier_label(benefit[m])},{income[m]},{demand.get(m, 0)}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(combos):
    for label, cyo, jobs in SCENARIOS:
        income, benefit, sets = build_overlay(cyo)
        for combo in combos:
            baseline = baseline_for(combo)
            for mode, suffix in jobs:
                prop_stations, n = sets[mode], MODE_N[mode]
                out = ROUTES / combo / "proportional" / f"{mode}{suffix}.csv"
                if out.exists():
                    print(f"  skip {combo}/{mode}{suffix} (exists)")
                    continue
                start, end, mult = fleet(n)
                demand = compute_demand_served(VERTIPORTS, start, end, mult)
                t0 = time.time()
                r = solve_prop(baseline, prop_stations, start, end, mult)
                dt = time.time() - t0
                if r.get("status") != "sat":
                    print(f"  FAILED {combo}/{mode}{suffix}: {r.get('reason')} ({dt:.1f}s)")
                    continue
                meta = {
                    "domain": "proportional", "combo": combo, "mode": mode,
                    "cyoScenario": label, "cyoChoices": cyo or "{} (all slot defaults)",
                    "vertiports": VERTIPORTS, "proportionalStations": prop_stations,
                    "benefitRule": "vertiport=3; adjacent High=2 Med=1 Low=0; overlap=max",
                    "incomeSource": "Sample Communities.xlsx (6<->8 swap)",
                    "D": D, "U": U, "hardT": False, "T_max": T_MAX,
                    "weightTime": W_TIME, "weightProportional": W_PROP,
                    "optimizeProportional": True,
                    "proportionalNoise": round(r.get("proportionalNoise", 0), 4),
                }
                write_csv(out, meta, r, baseline, start, end, mult, demand, benefit, income)
                print(f"  wrote {combo}/{mode}{suffix} ({dt:.1f}s, T={r['T']}, N={n}, "
                      f"propNoise={r.get('proportionalNoise')})")


if __name__ == "__main__":
    main(sys.argv[1:] or COMBOS)
