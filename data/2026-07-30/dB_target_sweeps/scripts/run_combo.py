"""Full-route regeneration for ONE baseline combo, across all 4 fairness
domains (30 files total: 12 equal_allocation + 6 sufficientarian +
4 utilitarian + 8 prioritarian). Run once per combo (4 parallel processes
total) as independent OS processes -- see _solve_helpers.py docstring.

Usage: python run_combo.py <combo>
  where combo in {s2-65_s6-55, s2-65_s6-45, s2-55_s6-55, s2-55_s6-45}
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _solve_helpers import (
    run_and_write, read_meta_preamble, read_picks_summary, variant_to_fleet,
    baseline_for, subsample_fleet, PEOPLE_WEIGHTS, FULL_MULT, FULL_START, FULL_END,
)

combo = sys.argv[1]
from _paths import AGG as SRC, ROUTES
OUT = ROUTES / combo
baseline = baseline_for(combo)
t_combo0 = time.time()
n_done = 0

print(f"=== combo {combo} ===")

# ---------------------------------------------------------------- equal_allocation
for mode, mode_flags in [
    ("community_equal", dict(optimize_util=False)),
    ("people_equal", dict(optimize_util=True, w_util=2.0,
                          station_transit_weights=PEOPLE_WEIGHTS, util_noise_mode=False)),
]:
    picks_path = SRC / "equal_allocation" / combo / mode / "picks_summary.csv"
    for row in read_picks_summary(picks_path):
        target, metric, variant, U = row["target_dB"], row["metric"], row["config"], float(row["U"])
        expect = float(row["value"])
        n, mult, start, end = variant_to_fleet(variant)
        meta = {
            "domain": "equal_allocation", "combo": combo, "mode": mode,
            "target_dB": target, "metric": metric, "variant": variant,
            "D": 50, "U": U, "hardT": False, "T_max": 7, "weightTime": 0.1,
            **{f"solver_{k}": v for k, v in mode_flags.items()},
        }
        out_path = OUT / "equal_allocation" / mode / f"{target}dB_{metric}.csv"
        run_and_write(out_path, meta, n, 50, U, 7, baseline, mult, start, end,
                     w_time=0.1, expect_value=expect, **mode_flags)
        n_done += 1

# ---------------------------------------------------------------- sufficientarian
for mode in ("unweighted", "weighted"):
    for cap_file in ("D8", "D18", "Dmin_3.02"):
        src_path = SRC / "sufficientarian" / combo / mode / f"{cap_file}.csv"
        pre = read_meta_preamble(src_path)
        N = int(pre["N"])
        mult = json.loads(pre["aircraftMultipliers"])
        start = json.loads(pre["startPositions"])
        end = json.loads(pre["endPositions"])
        D = float(pre["D"])
        U = float(pre["U"])
        weighted = pre["weighted"] == "True"
        meta = {
            "domain": "sufficientarian", "combo": combo, "mode": mode,
            "cap": cap_file, "variant": pre.get("variant", ""),
            "D": D, "U": U, "hardT": False, "T_max": 7, "weightTime": 0.1,
            "optimizeUtilitarian": True,
        }
        out_path = OUT / "sufficientarian" / mode / f"{cap_file}.csv"
        run_and_write(out_path, meta, N, D, U, 7, baseline, mult, start, end,
                     optimize_util=True, w_util=1.0, w_time=0.1,
                     station_transit_weights=PEOPLE_WEIGHTS if weighted else None,
                     util_noise_mode=False)
        n_done += 1

# ---------------------------------------------------------------- utilitarian
d_min = {}
for line in (SRC / "utilitarian" / "utilitarian_peak" / combo / "d_min.txt").read_text().splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        d_min[k.strip()] = v.strip()

for domain_folder, D in [("utilitarian", 12.0),
                        ("utilitarian_peak", float(d_min["D_used_for_final_csvs"]))]:
    for weight_mode, fname in [("no_weight", "no_weight.csv"), ("weighted", "weighted.csv")]:
        meta = {
            "domain": f"utilitarian/{domain_folder}", "combo": combo, "mode": weight_mode,
            "D": D, "U": 50, "hardT": False, "T_max": 7, "weightTime": 0.1,
            "optimizeUtilitarian": True,
        }
        out_path = OUT / domain_folder / weight_mode / "result.csv"
        run_and_write(out_path, meta, 14, D, 50, 7, baseline, list(FULL_MULT),
                     list(FULL_START), list(FULL_END),
                     optimize_util=True, w_util=1.0, w_time=0.1,
                     station_transit_weights=PEOPLE_WEIGHTS if weight_mode == "weighted" else None,
                     util_noise_mode=False)
        n_done += 1

# ---------------------------------------------------------------- prioritarian
for mode in ("community", "people"):
    for lens in ("low_income", "transit_desert", "few_jobs", "mostly_renters"):
        src_path = SRC / "prioritarian" / "step3_baseline_sweep" / combo / mode / f"{lens}.csv"
        pre = read_meta_preamble(src_path)
        N = int(pre["N"])
        D = float(pre["D"])
        U = float(pre["U"])
        T_max = int(pre["T_max"])
        w_prior = float(pre["weightPrioritarian"])
        w_time = float(pre["weightTime"])
        protected = json.loads(pre["protectedStations"])
        if mode == "people":
            mult = json.loads(pre["aircraftMultipliers"])
            start, end = subsample_fleet(N)
            w_util = float(pre["weightUtilitarian"])
            stw = json.loads(pre["stationTransitWeights"])
        else:
            mult = list(FULL_MULT)
            start, end = list(FULL_START), list(FULL_END)
            w_util = 1.0
            stw = None
        meta = {
            "domain": "prioritarian", "combo": combo, "mode": mode, "lens": lens,
            "protectedStations": protected, "D": D, "U": U, "hardT": False,
            "T_max": T_max, "weightTime": w_time, "weightPrioritarian": w_prior,
            "optimizePrioritarian": True,
            "optimizeUtilitarian": mode == "people",
        }
        out_path = OUT / "prioritarian" / mode / f"{lens}.csv"
        run_and_write(out_path, meta, N, D, U, T_max, baseline, mult, start, end,
                     optimize_util=(mode == "people"), optimize_prior=True,
                     protected_stations=protected, w_util=w_util, w_prior=w_prior,
                     w_time=w_time, station_transit_weights=stw, util_noise_mode=False)
        n_done += 1

print(f"=== combo {combo}: {n_done} files done in {time.time()-t_combo0:.1f}s ===")
