"""Probe C -- can benefit TIERS be expressed without touching the solver?

GOAL. Proportional allocation says burden should follow benefit. The current
rule produces four tiers (3 vertiport / 2 medium / 1 low / 0 none) but the
solver's `proportionalStations` is a FLAT list: every station in it gets the
same coefficient, so a medium-benefit tile and a low-benefit tile are treated
identically. We want medium-benefit tiles to carry MORE noise than low-benefit
tiles.

THE NO-SOLVER-CHANGE IDEA. The objective is

    proportional_noise_dB = Sum([wdB_by_t[t][b-1]
                                 for b in proportional_stations
                                 for t in range(T)])

It iterates the list and never de-duplicates; `_solve_impl` validates only that
entries are ints in [1, M]. So listing a station k times multiplies its
coefficient by k -- multiplicity IS a per-station weight. The normalizer
`max_proportional_dB = len(proportional_stations) * T * max_dB_scaled` scales
with list length, so the objective stays normalized.

    tiered list = [1,1,1, 16,16,16, 5,5, 2, 6]   (weight == benefit tier)

THE REASON THIS MAY NOT WORK. The objective maximizes DECIBELS, and dB yield
depends on the station's own baseline: added dB is
10*log10(1 + n*10^((45-baseline)/10)), so a QUIET station gains far more dB from
the same traffic than a loud one. Ceilings with the full 56-flight fleet:

    baseline 45 -> 17.56 dB      baseline 55 -> 8.20 dB      baseline 65 -> 1.93 dB

Station 5 (medium benefit) sits at 55. Station 6 (low benefit) is the CYO slot,
which drops to 45 in two of the four combos. So:

    station 5 at weight 2  ->  up to 2 * 8.20  = 16.4
    station 6 at weight 1  ->  up to 1 * 17.56 = 17.6

The LOW-benefit tile can outbid the MEDIUM-benefit one despite half the weight.
Weighting by tier does not guarantee ordering by tier, because the weights
multiply a quantity whose scale is itself station-dependent.

WHAT THIS SCRIPT DECIDES. Run flat vs tiered on one s6-55 combo and one s6-45
combo, and read the per-station added dB. If tiered gives
dB(station 5) > dB(stations 2, 6) in BOTH, multiplicity is sufficient and no
solver change is needed. If it fails -- especially in the s6-45 combo, where the
baseline works against us -- a solver change is required, and section
"IF THIS FAILS" below states the minimal one.

IF THIS FAILS, the minimal solver change is a per-station coefficient on the
proportional term: accept `proportionalWeights` (list of M floats) alongside
`proportionalStations`, and build
    Sum([w[b-1] * wdB_by_t[t][b-1] ...])
That still would not GUARANTEE ordering (same scale problem). A true guarantee
needs a hard ordering constraint --
    opt.add(wdB_by_t[t][med-1] >= wdB_by_t[t][low-1])
for each timestep and each (medium, low) pair -- which is the same shape as the
existing `prop_alloc` violation penalty, but keyed on benefit tier rather than
on the active/adjacent/none geometry it currently uses.

Usage: python probe_proportional_tiers.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths45 import PROBES
from _helpers45 import (
    ADJ, M, baseline_for, solve_scenario, zone_stats, subsample_fleet,
    demand_pct,
)
from benefit45 import sets_for

D, U, T_MAX, W_TIME, W_PROP = 18.0, 50.0, 5, 0.1, 1.0
COMBOS = ["s2-65_s6-55", "s2-65_s6-45"]   # one quiet-6, one loud-6

# N=14 at full multipliers does NOT solve for this objective -- an initial run of
# this probe hit phase2_failed/timeout at ~262s for BOTH the flat and tiered
# schemes, i.e. the failure is the objective's cost, not the tiering. That
# reproduces the 55 dB collection's own measurement (all_benefited timed out at
# N=14, ~253s) which is why it cut to N=7. Use the same tractable fleet here so
# the probe actually tests the tiering question.
N_PROBE = 7
MULT_PROBE = [1] * N_PROBE


def tiered_list(benefit):
    """Multiplicity == benefit tier. Sorted so the emitted list is readable."""
    out = []
    for st in sorted(benefit, key=lambda s: (-benefit[s], s)):
        out.extend([st] * benefit[st])
    return out


def main():
    PROBES.mkdir(parents=True, exist_ok=True)
    out = PROBES / "proportional_tiers.csv"
    out.write_text("combo,scheme,proportionalStations,proportionalNoise,status,"
                   "station,benefitTier,baseline,avgAdded,peakAdded,elapsed_s\n",
                   encoding="utf-8")

    income, benefit, high, allb = sets_for({}, ADJ, M)
    tiered = tiered_list(benefit)
    print(f"benefit map: {{st: tier}} = "
          f"{ {s: b for s, b in benefit.items() if b} }")
    print(f"flat all_benefited = {allb}")
    print(f"tiered (multiplicity = tier) = {tiered}\n")

    for combo in COMBOS:
        baseline = baseline_for(combo)
        for scheme, stations in (("flat", allb), ("tiered", tiered)):
            start, end = subsample_fleet(N_PROBE)
            t0 = time.time()
            r = solve_scenario(N_PROBE, D, U, T_MAX, baseline, MULT_PROBE,
                               start, end,
                               optimize_prop=True,
                               proportional_stations=stations,
                               w_prop=W_PROP, w_time=W_TIME)
            dt = time.time() - t0
            status = r.get("status")
            if status != "sat":
                print(f"{combo:<13} {scheme:<7} FAILED {status}/"
                      f"{r.get('reason','')} ({dt:.0f}s)", flush=True)
                with out.open("a", encoding="utf-8") as f:
                    f.write(f"{combo},{scheme},\"{stations}\",,{status},,,,,,{dt:.1f}\n")
                continue

            pn = r.get("proportionalNoise")
            zs = {z["zone"]: z for z in
                  zone_stats(r["countMatrix"], r["noiseMatrix"], baseline, r["T"])}
            print(f"{combo:<13} {scheme:<7} proportionalNoise={pn} ({dt:.0f}s)",
                  flush=True)
            for st in sorted(s for s in benefit if benefit[s]):
                z = zs[st]
                print(f"    station {st:<3} tier={benefit[st]} "
                      f"baseline={baseline[st-1]}  avgAdded={z['avg_added']:6.3f}  "
                      f"peakAdded={z['peak_added']:6.3f}", flush=True)
                with out.open("a", encoding="utf-8") as f:
                    f.write(f"{combo},{scheme},\"{stations}\",{pn},sat,{st},"
                            f"{benefit[st]},{baseline[st-1]},"
                            f"{z['avg_added']:.4f},{z['peak_added']:.4f},{dt:.1f}\n")

            # The decision: does medium (tier 2) outrank low (tier 1)?
            med = [s for s in benefit if benefit[s] == 2]
            low = [s for s in benefit if benefit[s] == 1]
            if med and low:
                mn = min(zs[s]["avg_added"] for s in med)
                mx = max(zs[s]["avg_added"] for s in low)
                verdict = "ORDERING HOLDS" if mn > mx else "ORDERING VIOLATED"
                print(f"    -> min(medium)={mn:.3f} vs max(low)={mx:.3f}  "
                      f"{verdict}\n", flush=True)

    print(f"-> {out}")


if __name__ == "__main__":
    main()
