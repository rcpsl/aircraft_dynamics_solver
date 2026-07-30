"""s2-65_s6-55/equal_allocation/people_equal/3dB_avg.csv fails at PHASE 1
(find_min_T -- pure feasibility, before the weighted objective is ever
involved), and resolves fast (~10s) either way rather than grinding a full
timeout budget. That makes it cheap to try many random seeds in quick
succession instead of committing a long timeout to one attempt.

Usage: python retry_multiseed.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import REPO, ROUTES
sys.path.insert(0, str(REPO))
from _solve_helpers import run_and_write, baseline_for, PEOPLE_WEIGHTS, FULL_MULT, FULL_START, FULL_END
import solver_server_dB as S
import z3

S.SOLVE_TIMEOUT_MS = 300000  # 300s per-attempt safety net; expected to resolve much faster

combo = "s2-65_s6-55"
baseline = baseline_for(combo)
meta = {
    "domain": "equal_allocation", "combo": combo, "mode": "people_equal",
    "target_dB": "3", "metric": "avg", "variant": "N14_mult1",
    "D": 50, "U": 6.0, "hardT": False, "T_max": 7, "weightTime": 0.1,
    "solver_optimize_util": True, "solver_w_util": 2.0,
    "solver_station_transit_weights": PEOPLE_WEIGHTS, "solver_util_noise_mode": False,
}
out_path = ROUTES / combo / "equal_allocation" / "people_equal" / "3dB_avg.csv"

# BUG FIX: variant is N14_mult1 -- unit multipliers ([1]*14, sum=14), NOT
# FULL_MULT (sum=56). Confirmed against the historical file's own
# "Total Traffic,14" / T=6 -- the earlier attempts were solving the wrong,
# much harder (56-traffic) problem entirely, not hitting real solver hardness.
mult = [1] * 14

for seed in [None, 7, 99]:
    if out_path.exists():
        print(f"  already solved, stopping (seed {seed} not needed)")
        break
    if seed is not None:
        z3.set_param("smt.random_seed", seed)
        z3.set_param("sat.random_seed", seed)
    t0 = time.time()
    ok = run_and_write(out_path, meta, 14, 50, 6.0, 7, baseline, mult,
                       list(FULL_START), list(FULL_END),
                       w_time=0.1, expect_value=2.8873,
                       optimize_util=True, w_util=2.0,
                       station_transit_weights=PEOPLE_WEIGHTS, util_noise_mode=False)
    print(f"  seed {seed}: {'SUCCESS' if ok else 'failed'} ({time.time()-t0:.1f}s)")

print("done" if out_path.exists() else "all seeds exhausted, still missing")
