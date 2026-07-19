"""Regenerates prioritarian/step3_baseline_sweep/<combo>/<lens>.csv with a
config that actually lets the prioritarian objective differentiate between
protected-station lenses.

Why this replaces the old step3 data: the original data (hardT=true) pins every
solve to T=T_min=4, and the base scenario's only feasible route at that length
is the unique shortest path 1->6->11->16 (confirmed by BFS/path enumeration in
REPORT.md). With zero timing slack, every aircraft is forced onto that one
route no matter which stations the objective says to protect, so all 24
original files (step1/step2/step3) came out byte-identical across lenses.

The fix (confirmed empirically, see REPORT.md's updated Sec. 5):
  - hardT=false, T_max=5 (not the originally-attempted T_max=7): T_max=5 opens
    the 12 alternate length-4 routes, which is enough for the prioritarian
    objective to actually have a choice, while keeping the per-timestep
    constraint volume small enough to solve in seconds instead of timing out.
  - D=18 (not the original 40/non-binding): tight enough to force real
    overflow at the station 6/11 bottleneck (so there's a genuine reason to
    reroute), matching the D value the sufficientarian domain already proved
    solves with the FULL N=14 fleet (no service-level sacrifice needed).
  - Everything else unchanged from the original prioritarian methodology:
    N=14, aircraftMultipliers = the original config's, weightPrioritarian=1.0,
    weightTime=0.1 (soft-T convention used elsewhere in this project).

step1_prioritarian_only/ and step2_prioritarian_utilitarian/ are left as-is —
they still correctly document the original hard-T finding (identical lenses)
at the default combo; only step3's 4-combo sweep is upgraded here, since
that's the one the dashboard consumes.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, r"d:\Documents\EECS_199_Shoukry")
import solver_server_dB as S

ROOT = Path(r"d:\Documents\EECS_199_Shoukry\dB_target_sweeps\prioritarian\step3_baseline_sweep")
cfg = json.load(open(r"d:\Documents\EECS_199_Shoukry\uam-config_finalized.json"))
ADJ, M = cfg["adjacency"], cfg["M"]
AIRCRAFT_DB = cfg["dbPerCraft"]
START, END, MULT = cfg["startPos"], cfg["endPos"], cfg["aircraftMultipliers"]
BASE_DEFAULT = cfg["stationBaselines"]

COMBO_OVERRIDES = {
    "s2-65_s6-55": {1: 65, 5: 55},
    "s2-65_s6-45": {1: 65, 5: 45},
    "s2-55_s6-55": {1: 55, 5: 55},
    "s2-55_s6-45": {1: 55, 5: 45},
}
LENSES = {
    "low_income": [6, 12],
    "transit_desert": [6, 12, 15],
    "few_jobs": [4, 6, 12, 14],
    "mostly_renters": [1, 3, 5, 10, 15, 16],
}
D, U, T_MAX, W_TIME, W_PRIOR, N = 18, 50, 5, 0.1, 1.0, 14


def baseline_for(combo):
    b = list(BASE_DEFAULT)
    for idx, val in COMBO_OVERRIDES[combo].items():
        b[idx] = val
    return b


def write_csv(path, meta, count_matrix, noise_matrix, baseline, T):
    lines = [f"# {k},{v}" for k, v in meta.items()]
    lines.append(f"Time Steps (T),{T}")
    lines.append("")
    lines.append("Zone,Avg Added dB,Avg Total dB,Peak Added dB,Peak Total dB,Avg Aircraft,Peak Aircraft")
    for m in range(M):
        added = [noise_matrix[m][t] for t in range(T)]
        counts = [count_matrix[m][t] for t in range(T)]
        avg_a = sum(added) / T
        peak_a = max(added)
        avg_c = sum(counts) / T
        peak_c = max(counts)
        lines.append(
            f"Zone {m+1},{avg_a:.2f},{baseline[m]+avg_a:.2f},{peak_a:.2f},{baseline[m]+peak_a:.2f},{avg_c:.2f},{peak_c}"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


total_t0 = time.time()
for combo in COMBO_OVERRIDES:
    baseline = baseline_for(combo)
    p1 = S.find_min_T(N, M, D, U, ADJ, START, END, baseline, AIRCRAFT_DB, multipliers=MULT)
    assert p1["status"] == "sat", f"{combo}: phase1 failed: {p1}"
    T_min = p1["T"]
    T_use = max(T_min, T_MAX)
    for lens, stations in LENSES.items():
        t0 = time.time()
        r = S.optimize_objectives(
            N, T_use, M, D, U, ADJ, START, END,
            optimize_util=False, optimize_prior=True, optimize_prop=False,
            protected_stations=stations, proportional_stations=[],
            w_util=1.0, w_prior=W_PRIOR, w_prop=1.0,
            soft_T=True, w_time=W_TIME,
            prop_alloc=False, station_transit_weights=None, util_noise_mode=False,
            aircraft_multipliers=MULT, baseline=baseline, aircraft_dB=AIRCRAFT_DB,
        )
        dt = time.time() - t0
        assert r["status"] == "sat", f"{combo}/{lens}: FAILED {r.get('reason')} ({dt:.1f}s)"
        meta = {
            "combo": combo, "lens": lens, "protectedStations": stations,
            "hardT": False, "T_max": T_MAX, "D": D, "U": U,
            "weightPrioritarian": W_PRIOR, "weightTime": W_TIME, "N": N,
            "protectedNoise": round(r["protectedNoise"], 2),
        }
        out = ROOT / combo / f"{lens}.csv"
        write_csv(out, meta, r["countMatrix"], r["noiseMatrix"], baseline, T_use)
        print(f"{combo}/{lens}: wrote {out.relative_to(ROOT.parent.parent)} ({dt:.1f}s, T={T_use}, protectedNoise={r['protectedNoise']:.2f})")

print(f"\nDone in {time.time()-total_t0:.1f}s total")
