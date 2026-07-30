"""Probe A -- phase-1 feasibility grid for the 45 dB collection.

Every dB constant inherited from the 55 dB collection (D=18, D=12, D=8,
Dmin=3.02, and the 3/8/18 equal_allocation ladder) was tuned against 55 dB
ceilings and goes inert or unreachable at 45 dB. This re-derives the feasible
range from scratch using find_min_T ONLY -- phase 1 settles feasibility and is
far cheaper than the full two-phase solve.

WHY A GRID, NOT A BISECTION. A bisection to 0.01 precision spends most of its
probes on infeasible D values, and infeasible probes are the expensive ones:
`_compute_d_counts` shrinks `max_d_count` to ~1 at tiny D, which RAISES
find_min_T's internal T cap to T_lower+40 (solver_server_dB.py:290-304), so each
such probe grinds through ~40 growing Z3 solves. A coarse scan over the handful
of D values that are actually candidate ladder rungs answers the design
question directly -- "which rungs are feasible at which fleet" -- at a fraction
of the cost, and the demand column falls out of the same table.

Writes data/probes/floors.csv. Reads nothing from the 55 dB collection.

Usage: python probe_floors.py [--quick]
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths45 import PROBES
from _helpers45 import (
    COMBOS, baseline_for, variant_to_fleet, demand_pct, phase1_feasible,
    AIRCRAFT_DB,
)

# Candidate rungs. The informative band at 45 dB per craft is roughly 0.5-8 dB:
# one weighted flight at a 45 dB station already adds 3.01 dB, while the ceiling
# at a 65 dB station is 1.93 dB even with all 56 flights stacked on it.
D_GRID = [0.5, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0]
U_GRID = [1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0]

# baseline_mult is the headline case (full fleet, 100% demand). The reduced
# fleets exist to show what a cap costs in service when it is infeasible at full
# demand -- the sufficientarian "how much service survives each floor" axis.
VARIANTS = ["baseline_mult", "N14_mult1", "N7_mult1", "N4_mult1"]


def main():
    quick = "--quick" in sys.argv
    variants = ["baseline_mult"] if quick else VARIANTS
    combos = COMBOS[:1] if quick else COMBOS

    PROBES.mkdir(parents=True, exist_ok=True)
    out = PROBES / "floors.csv"
    out.write_text("combo,variant,N,totalTraffic,demandPct,knob,value,"
                   "feasible,T_min,elapsed_s,status\n", encoding="utf-8")

    t_all = time.time()
    for combo in combos:
        baseline = baseline_for(combo)
        for variant in variants:
            n, mult, start, end = variant_to_fleet(variant)
            dpct = demand_pct(mult)
            print(f"\n--- {combo} / {variant}  N={n} demand={dpct}% ---", flush=True)

            # D sweep at U=999 (disparity off): isolates the absolute cap.
            d_ok = []
            for D in D_GRID:
                ok, T, dt, status = phase1_feasible(D, 999.0, n, mult, start, end, baseline)
                with out.open("a", encoding="utf-8") as f:
                    f.write(f"{combo},{variant},{n},{sum(mult)},{dpct},D,{D},"
                            f"{ok},{T},{dt:.1f},{status}\n")
                if ok:
                    d_ok.append(D)
                print(f"    D={D:>5}  U=999  -> {status:>5}  T={T}  ({dt:.1f}s)", flush=True)

            # U sweep at D=50 (cap off): isolates the disparity constraint,
            # which is what equal_allocation actually drives.
            u_ok = []
            for U in U_GRID:
                ok, T, dt, status = phase1_feasible(50.0, U, n, mult, start, end, baseline)
                with out.open("a", encoding="utf-8") as f:
                    f.write(f"{combo},{variant},{n},{sum(mult)},{dpct},U,{U},"
                            f"{ok},{T},{dt:.1f},{status}\n")
                if ok:
                    u_ok.append(U)
                print(f"    D=50   U={U:>5}  -> {status:>5}  T={T}  ({dt:.1f}s)", flush=True)

            print(f"  => feasible D: {d_ok or 'NONE'}", flush=True)
            print(f"  => feasible U: {u_ok or 'NONE'}", flush=True)

    print(f"\n=== done in {time.time() - t_all:.0f}s -> {out} "
          f"(dbPerCraft={AIRCRAFT_DB}) ===")


if __name__ == "__main__":
    main()
