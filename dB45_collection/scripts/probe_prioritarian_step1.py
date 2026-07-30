"""Step 1 -- prioritarian lens degeneracy + the N=14 people-mode retest, at 45 dB.

Same two questions as probe_prioritarian.py, re-run because that probe's stored
CSV predates the station-map correction: its lens lists were taken with the old
`SWAP = {6: 8, 8: 6}` in force, so every row reading "station 6" is really about
station 8. Its FLEET findings still hold; its lens columns do not.

Nothing is transcribed here either -- LENSES is imported from lens_definitions,
which parses the workbook.

Differences from probe_prioritarian.py, both about not wasting solver budget:

  * `--fleet` selects one row of the fleet table, so the three fleets can run as
    three parallel processes instead of ~25 minutes in series. Each writes its
    own CSV (the older probe rewrites one shared file, which parallel runs would
    clobber).
  * `--lenses` restricts the lens loop. The N=14 people-mode retest only needs
    ONE lens to answer "does the combined objective fit in the 240 s budget now"
    -- running all four costs 4x for the same bit of information.

Usage:
    python probe_prioritarian_step1.py [combo] --fleet community_N14
    python probe_prioritarian_step1.py [combo] --fleet people_N14 --lenses low_income
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths45 import PROBES
from _helpers45 import (
    FULL_MULT, PEOPLE_WEIGHTS,
    baseline_for, subsample_fleet, solve_scenario, metric_maxima, demand_pct,
)
from lens_definitions import LENSES, SELECTORS

D, U, T_MAX, W_TIME, W_PRIOR = 18.0, 50.0, 5, 0.1, 1.0

# label -> (N, multipliers, station weights, also-optimise-utilitarian)
FLEETS = {
    "community_N14": (14, list(FULL_MULT), None,          False),
    "people_N7":     (7,  [1] * 7,         PEOPLE_WEIGHTS, True),
    "people_N14":    (14, list(FULL_MULT), PEOPLE_WEIGHTS, True),  # the retest
}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    combo = args[0] if args else "s2-65_s6-55"
    fleet = sys.argv[sys.argv.index("--fleet") + 1]
    if "--lenses" in sys.argv:
        lenses = sys.argv[sys.argv.index("--lenses") + 1].split(",")
    else:
        lenses = list(LENSES)

    N, mult, stw, opt_util = FLEETS[fleet]
    baseline = baseline_for(combo)
    start, end = subsample_fleet(N)
    PROBES.mkdir(parents=True, exist_ok=True)
    out = PROBES / f"prioritarian_step1_{fleet}.csv"
    out.write_text("combo,fleet,lens,lensSelector,protectedStations,N,demandPct,"
                   "status,protectedNoise,degenerate,maxAvgAdded,maxPeakAdded,"
                   "T,elapsed_s\n", encoding="utf-8")

    print(f"=== step1 {fleet}: combo {combo}, N={N}, demand={demand_pct(mult)}%, "
          f"D={D} (non-binding), T_max={T_MAX} ===", flush=True)
    for lens in lenses:
        protected = LENSES[lens]
        t0 = time.time()
        r = solve_scenario(
            N, D, U, T_MAX, baseline, mult, start, end,
            optimize_prior=True, protected_stations=protected,
            optimize_util=opt_util, w_prior=W_PRIOR, w_util=1.0,
            w_time=W_TIME, station_transit_weights=stw,
        )
        dt = time.time() - t0
        status = r.get("status")
        sel = SELECTORS[lens][0].replace(",", ";")
        if status == "sat":
            pn = r.get("protectedNoise")
            mx_avg, mx_peak = metric_maxima(r, baseline)
            degen = "YES" if pn == 0.0 else "no"
            row = (f"{combo},{fleet},{lens},\"{sel}\",\"{protected}\",{N},"
                   f"{demand_pct(mult)},sat,{pn},{degen},{mx_avg:.4f},"
                   f"{mx_peak:.4f},{r['T']},{dt:.1f}")
            print(f"  {lens:<16} {str(protected):<22} protectedNoise={pn:<8} "
                  f"degenerate={degen:<4} peak={mx_peak:.3f} ({dt:.0f}s)", flush=True)
        else:
            row = (f"{combo},{fleet},{lens},\"{sel}\",\"{protected}\",{N},"
                   f"{demand_pct(mult)},{status}/{r.get('reason')},,,,,,{dt:.1f}")
            print(f"  {lens:<16} {str(protected):<22} FAILED "
                  f"{status}/{r.get('reason')} ({dt:.0f}s)", flush=True)
        with out.open("a", encoding="utf-8") as f:
            f.write(row + "\n")

    print(f"=== -> {out} ===", flush=True)


if __name__ == "__main__":
    main()
