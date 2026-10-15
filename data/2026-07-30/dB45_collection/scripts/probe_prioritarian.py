"""Probe B -- prioritarian lens degeneracy + fleet tractability, at 45 dB.

Two questions that must be answered BEFORE spending solver time on all 32
prioritarian files.

1. DEGENERACY. The objective minimises summed added dB over `protectedStations`.
   Every aircraft starts or ends at station 1 or 16, so those are occupied at
   every timestep by construction; station 11 sits on the unique shortest path
   1-6-11-16. A protected set containing none of {1, 11, 16} can potentially be
   driven to exactly zero -- at which point every routing achieving zero ties,
   Z3 picks arbitrarily, and the lens carries no fairness signal even though the
   output files differ. Of the four workbook-derived lenses only `low_income`
   contains an unavoidable station (16). The flatter 45 dB surface makes zero
   EASIER to reach, so this is expected to be worse here than at 55 dB.

   Read: the solver's own `protectedNoise`. 0.0 == degenerate.

2. TRACTABILITY. `people` mode ran N=7 (12.5% demand) only because the combined
   prioritarian+utilitarian objective exceeded the 240 s budget at N=14 at
   55 dB. If N=14 now solves, `people` becomes a real weighting variant of
   `community` instead of a different scenario -- which removes the biggest
   interpretive hazard in the domain.

`D` is deliberately non-binding here (D=18 cannot bind at 45 dB: the ceiling
anywhere is 17.56 dB). Both questions are about the objective, not the cap, so
this isolates them from the ladder choice made in probe A.

Writes data/probes/prioritarian.csv. Reads nothing from the 55 dB collection.

Usage: python probe_prioritarian.py [combo]
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths45 import PROBES
from _helpers45 import (
    FULL_MULT, FULL_START, FULL_END, PEOPLE_WEIGHTS,
    baseline_for, subsample_fleet, solve_scenario, metric_maxima, demand_pct,
)
from lens_definitions import LENSES

D, U, T_MAX, W_TIME, W_PRIOR = 18.0, 50.0, 5, 0.1, 1.0

# (label, N, multipliers, station weights, also-optimise-utilitarian)
FLEETS = [
    ("community_N14",  14, list(FULL_MULT), None,           False),
    ("people_N7",       7, [1] * 7,         PEOPLE_WEIGHTS,  True),
    ("people_N14",     14, list(FULL_MULT), PEOPLE_WEIGHTS,  True),  # the retest
]


def main():
    combo = sys.argv[1] if len(sys.argv) > 1 else "s2-65_s6-55"
    baseline = baseline_for(combo)
    PROBES.mkdir(parents=True, exist_ok=True)
    out = PROBES / "prioritarian.csv"
    out.write_text("combo,fleet,lens,protectedStations,N,demandPct,status,"
                   "protectedNoise,degenerate,maxAvgAdded,maxPeakAdded,T,elapsed_s\n",
                   encoding="utf-8")

    print(f"=== prioritarian probe, combo {combo}, D={D} (non-binding), "
          f"T_max={T_MAX} ===\n")
    for fleet, N, mult, stw, opt_util in FLEETS:
        start, end = subsample_fleet(N)
        for lens, protected in LENSES.items():
            t0 = time.time()
            r = solve_scenario(
                N, D, U, T_MAX, baseline, mult, start, end,
                optimize_prior=True, protected_stations=protected,
                optimize_util=opt_util, w_prior=W_PRIOR, w_util=1.0,
                w_time=W_TIME, station_transit_weights=stw,
            )
            dt = time.time() - t0
            status = r.get("status")
            if status == "sat":
                pn = r.get("protectedNoise")
                mx_avg, mx_peak = metric_maxima(r, baseline)
                degen = "YES" if pn == 0.0 else "no"
                row = (f"{combo},{fleet},{lens},\"{protected}\",{N},"
                       f"{demand_pct(mult)},sat,{pn},{degen},"
                       f"{mx_avg:.4f},{mx_peak:.4f},{r['T']},{dt:.1f}")
                print(f"  {fleet:<14} {lens:<16} protectedNoise={pn:<8} "
                      f"degenerate={degen:<4} peak={mx_peak:.3f}  ({dt:.0f}s)",
                      flush=True)
            else:
                row = (f"{combo},{fleet},{lens},\"{protected}\",{N},"
                       f"{demand_pct(mult)},{status}/{r.get('reason')},,,,,,{dt:.1f}")
                print(f"  {fleet:<14} {lens:<16} FAILED {status}/{r.get('reason')} "
                      f"({dt:.0f}s)", flush=True)
            with out.open("a", encoding="utf-8") as f:
                f.write(row + "\n")

    print(f"\n=== -> {out} ===")


if __name__ == "__main__":
    main()
