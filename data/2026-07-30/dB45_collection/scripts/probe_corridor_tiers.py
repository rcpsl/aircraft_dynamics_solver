"""Probe D -- does the corridor benefit rule make medium > low achievable?

BACKGROUND. Probe C showed the tier ordering could not be enforced by any
weighting: the medium-benefit station (5) received EXACTLY 0.000 added dB in
every scheme, because it is vertiport-adjacent but sits off the route the
traffic actually takes. Benefit and burden were assigned over incommensurable
sets, so no objective coefficient could reconcile them.

THE CORRIDOR RULE (benefit45.compute_benefit(corridor_only=True)) fixes the
benefit side rather than forcing the solver: a station earns benefit only if it
lies on a viable route between the vertiports. Under the default CYO picks that
leaves {1:3, 6:1, 16:3} -- correct, but with no tier-2 station left, so
medium-vs-low is not observable.

Under CYO slot C = Suburban Tech Campus it leaves {1:3, 6:1, 11:2, 16:3}:
station 11 is MEDIUM benefit and station 6 is LOW benefit, and BOTH sit on the
unique shortest path 1-6-11-16, so both are guaranteed traffic. That is the
configuration where the ordering question is decidable.

PREDICTION WORTH RECORDING BEFORE THE RUN. Added dB is
10*log10(1 + n*10^((45-baseline)/10)), so a quieter station converts the same
traffic into more decibels. Station 11 is baseline 55 (ceiling 8.20 with the
full fleet). Station 6 is the CYO slot: 55 in the s6-55 combos, 45 in the s6-45
combos (ceiling 17.56).

  s6-55: both at 55 -> weights 2 vs 1 should cleanly favour station 11.
  s6-45: station 6 at 45 yields far more dB per aircraft. Weight 2 on station 11
         caps at 2*8.20 = 16.4 while weight 1 on station 6 reaches 17.56, so the
         LOW-benefit station may still outrank the MEDIUM one.

If that split appears, the corridor rule works but is not sufficient on its own,
and the residual failure is caused by the CYO baseline choice rather than by the
benefit rule.

Usage: python probe_corridor_tiers.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths45 import PROBES
from _helpers45 import (
    ADJ, M, baseline_for, solve_scenario, zone_stats, subsample_fleet,
)
from benefit45 import sets_for, tiered_list, corridor_stations

D, U, T_MAX, W_TIME, W_PROP = 18.0, 50.0, 5, 0.1, 1.0
COMBOS = ["s2-65_s6-55", "s2-65_s6-45"]
N_PROBE = 7                      # N=14 times out for this objective (probe C)
MULT_PROBE = [1] * N_PROBE
CYO = {11: 1}                    # slot C = Suburban Tech Campus


def main():
    PROBES.mkdir(parents=True, exist_ok=True)
    out = PROBES / "corridor_tiers.csv"
    out.write_text("combo,cyo,corridorOnly,scheme,proportionalStations,"
                   "proportionalNoise,station,tier,baseline,avgAdded,peakAdded,"
                   "orderingHolds,elapsed_s\n", encoding="utf-8")

    # The corridor toggle was removed from the production rule; this probe
    # applies the mask locally so its recorded result stays reproducible.
    income, benefit, high, allb = sets_for(CYO, ADJ, M)
    corridor = set(corridor_stations(ADJ, M))
    benefit = {s_: (b if s_ in corridor else 0) for s_, b in benefit.items()}
    allb = sorted(s_ for s_, b in benefit.items() if b > 0)
    tiered = tiered_list(benefit)
    tiers = {s: b for s, b in benefit.items() if b}
    print(f"corridor benefit tiers (cyo=c11-tech): {tiers}")
    print(f"flat   = {allb}")
    print(f"tiered = {tiered}\n")

    for combo in COMBOS:
        baseline = baseline_for(combo)
        for scheme, stations in (("flat", allb), ("tiered", tiered)):
            start, end = subsample_fleet(N_PROBE)
            t0 = time.time()
            r = solve_scenario(N_PROBE, D, U, T_MAX, baseline, MULT_PROBE,
                               start, end, optimize_prop=True,
                               proportional_stations=stations,
                               w_prop=W_PROP, w_time=W_TIME)
            dt = time.time() - t0
            if r.get("status") != "sat":
                print(f"{combo:<13} {scheme:<7} FAILED {r.get('status')}/"
                      f"{r.get('reason','')} ({dt:.0f}s)", flush=True)
                continue

            pn = r.get("proportionalNoise")
            zs = {z["zone"]: z for z in
                  zone_stats(r["countMatrix"], r["noiseMatrix"], baseline, r["T"])}
            med = [s for s in benefit if benefit[s] == 2]
            low = [s for s in benefit if benefit[s] == 1]
            holds = (min(zs[s]["avg_added"] for s in med)
                     > max(zs[s]["avg_added"] for s in low)) if med and low else None

            print(f"{combo:<13} {scheme:<7} proportionalNoise={pn} ({dt:.0f}s)",
                  flush=True)
            for st in sorted(tiers):
                z = zs[st]
                tag = {3: "vertiport", 2: "MEDIUM", 1: "low"}[benefit[st]]
                print(f"    station {st:<3} tier={benefit[st]} {tag:<9} "
                      f"baseline={baseline[st-1]}  avg={z['avg_added']:6.3f}  "
                      f"peak={z['peak_added']:6.3f}", flush=True)
                with out.open("a", encoding="utf-8") as f:
                    f.write(f"{combo},c11-tech,True,{scheme},\"{stations}\",{pn},"
                            f"{st},{benefit[st]},{baseline[st-1]},"
                            f"{z['avg_added']:.4f},{z['peak_added']:.4f},"
                            f"{holds},{dt:.1f}\n")
            print(f"    -> medium(st{med[0]})={zs[med[0]]['avg_added']:.3f} vs "
                  f"low(st{low[0]})={zs[low[0]]['avg_added']:.3f}  "
                  f"{'ORDERING HOLDS' if holds else 'ORDERING VIOLATED'}\n",
                  flush=True)

    print(f"-> {out}")


if __name__ == "__main__":
    main()
