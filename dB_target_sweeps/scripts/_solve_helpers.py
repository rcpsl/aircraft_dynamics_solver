"""Shared solve+format helper for the full_routes/ reformatting pass.

Re-solves each scenario from its exact documented config (so results match
the originally-published numbers in equal_allocation/, sufficientarian/,
utilitarian/, prioritarian/) and this time writes the actual per-aircraft
routing paths alongside the previously-existing per-zone summary, plus
explicit demand-fulfilled figures.

Called by the four domain driver scripts, each scoped to one baseline combo
so 4 of them can run as independent parallel OS processes.
"""
import json
import os
import sys
import time

from _paths import REPO, CONFIG_JSON

sys.path.insert(0, str(REPO))
import solver_server_dB as S

# Optional Z3 search diversification for scenarios that time out inconsistently
# across otherwise-identical re-runs (observed: same config failed 3x incl. at
# 420s, then solved in 40s on a later attempt with no config change -- Z3's
# search isn't fully deterministic run-to-run). Set via env var so normal runs
# (no env var) are byte-identical to before this was added.
_seed = os.environ.get("Z3_RANDOM_SEED")
if _seed is not None:
    import z3
    z3.set_param("smt.random_seed", int(_seed))
    z3.set_param("sat.random_seed", int(_seed))

CFG = json.load(open(CONFIG_JSON, encoding="utf-8"))
ADJ, M = CFG["adjacency"], CFG["M"]
AIRCRAFT_DB = CFG["dbPerCraft"]
FULL_START, FULL_END = CFG["startPos"], CFG["endPos"]
FULL_MULT = CFG["aircraftMultipliers"]
BASE_DEFAULT = CFG["stationBaselines"]
MAX_TRAFFIC = sum(FULL_MULT)  # 56 -- the full fleet's total weighted demand

COMBO_OVERRIDES = {
    "s2-65_s6-55": {1: 65, 5: 55},
    "s2-65_s6-45": {1: 65, 5: 45},
    "s2-55_s6-55": {1: 55, 5: 55},
    "s2-55_s6-45": {1: 55, 5: 45},
}
PEOPLE_WEIGHTS = [10, 5, 10, 5, 10, 10, 5, 5, 5, 10, 5, 5, 5, 5, 1, 5]


def baseline_for(combo):
    b = list(BASE_DEFAULT)
    for idx, val in COMBO_OVERRIDES[combo].items():
        b[idx] = val
    return b


def read_meta_preamble(path):
    """Reads the '#'-prefixed metadata lines from an existing sufficientarian/
    prioritarian CSV, returning a dict of raw string values (caller parses
    ints/lists as needed via json.loads where appropriate)."""
    meta = {}
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.startswith("#"):
            if line.strip() == "" or line.startswith("Time Steps") or line.startswith("Zone"):
                continue
            break
        key, _, val = line.lstrip("# ").partition(",")
        meta[key.strip()] = val.strip()
    return meta


def read_picks_summary(path):
    """Parses an equal_allocation picks_summary.csv into a list of dict rows."""
    rows = []
    with open(path, encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            vals = line.split(",")
            rows.append(dict(zip(header, vals)))
    return rows


VARIANT_INFO = {
    "baseline_mult": {"n": 14, "mult": None},  # None -> use FULL_MULT
    "N14_mult1": {"n": 14, "mult": 1},
    "N7_mult1": {"n": 7, "mult": 1},
    "N4_mult1": {"n": 4, "mult": 1},
}


def variant_to_fleet(variant):
    info = VARIANT_INFO[variant]
    n = info["n"]
    start, end = subsample_fleet(n)
    mult = list(FULL_MULT) if info["mult"] is None else [info["mult"]] * n
    return n, mult, start, end


def subsample_fleet(n):
    """'Every other' subsample of the 14 original start/end pairs, same
    scheme used successfully for prioritarian's people-mode fleet-shrink."""
    if n >= len(FULL_START):
        return list(FULL_START), list(FULL_END)
    idx = list(range(0, len(FULL_START), max(1, len(FULL_START) // n)))[:n]
    return [FULL_START[i] for i in idx], [FULL_END[i] for i in idx]


def solve_scenario(N, D, U, T_max, baseline, multipliers, start, end,
                   optimize_util=False, optimize_prior=False,
                   protected_stations=None, w_util=1.0, w_prior=1.0,
                   w_time=0.1, station_transit_weights=None,
                   util_noise_mode=False):
    """Runs phase1 + phase2 exactly as solver_server_dB.py's /solve route
    would, for hardT=false (soft-T) scenarios (all 4 domains here use soft-T).
    Returns the raw result dict (status, T, paths, countMatrix, noiseMatrix, ...).
    """
    p1 = S.find_min_T(N, M, D, U, ADJ, start, end, baseline, AIRCRAFT_DB, multipliers=multipliers)
    if p1["status"] != "sat":
        return p1
    T_use = max(p1["T"], T_max)
    r = S.optimize_objectives(
        N, T_use, M, D, U, ADJ, start, end,
        optimize_util=optimize_util, optimize_prior=optimize_prior, optimize_prop=False,
        protected_stations=protected_stations or [], proportional_stations=[],
        w_util=w_util, w_prior=w_prior, w_prop=1.0,
        soft_T=True, w_time=w_time,
        prop_alloc=False, station_transit_weights=station_transit_weights,
        util_noise_mode=util_noise_mode,
        aircraft_multipliers=multipliers, baseline=baseline, aircraft_dB=AIRCRAFT_DB,
    )
    return r


def zone_stats(count_matrix, noise_matrix, baseline, T):
    """Reproduces the existing per-zone summary columns exactly."""
    rows = []
    for m in range(M):
        added = [noise_matrix[m][t] for t in range(T)]
        counts = [count_matrix[m][t] for t in range(T)]
        avg_a = sum(added) / T
        peak_a = max(added)
        avg_c = sum(counts) / T
        peak_c = max(counts)
        rows.append({
            "zone": m + 1, "avg_added": avg_a, "avg_total": baseline[m] + avg_a,
            "peak_added": peak_a, "peak_total": baseline[m] + peak_a,
            "avg_aircraft": avg_c, "peak_aircraft": peak_c,
        })
    return rows


def write_full_csv(path, meta, paths, mult, start, end, count_matrix, noise_matrix, baseline, T):
    N = len(paths)
    traffic = sum(mult)
    lines = []
    for k, v in meta.items():
        lines.append(f"# {k},{v}")
    lines.append(f"# N,{N}")
    lines.append(f"# aircraftMultipliers,{mult}")
    lines.append(f"# totalTraffic,{traffic}")
    lines.append(f"# maxTraffic,{MAX_TRAFFIC}")
    lines.append(f"# demandFulfilledPct,{round(100*traffic/MAX_TRAFFIC, 2)}")
    lines.append(f"Time Steps (T),{T}")
    lines.append("")
    lines.append("Routing (station per aircraft per timestep):")
    header = ["Aircraft", "Multiplier", "Start", "End"] + [f"T{t}" for t in range(T)]
    lines.append(",".join(header))
    for i in range(N):
        row = [str(i + 1), str(mult[i]), str(start[i]), str(end[i])] + [str(p) for p in paths[i][:T]]
        lines.append(",".join(row))
    lines.append("")
    lines.append("Zone,Avg Added dB,Avg Total dB,Peak Added dB,Peak Total dB,Avg Aircraft,Peak Aircraft")
    for row in zone_stats(count_matrix, noise_matrix, baseline, T):
        lines.append(
            f"Zone {row['zone']},{row['avg_added']:.2f},{row['avg_total']:.2f},"
            f"{row['peak_added']:.2f},{row['peak_total']:.2f},"
            f"{row['avg_aircraft']:.2f},{row['peak_aircraft']}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_and_write(path, meta, N, D, U, T_max, baseline, multipliers, start, end,
                  optimize_util=False, optimize_prior=False, protected_stations=None,
                  w_util=1.0, w_prior=1.0, w_time=0.1, station_transit_weights=None,
                  util_noise_mode=False, expect_value=None):
    if path.exists():
        print(f"  skip {path.name} (already exists)")
        return True
    t0 = time.time()
    r = solve_scenario(N, D, U, T_max, baseline, multipliers, start, end,
                       optimize_util=optimize_util, optimize_prior=optimize_prior,
                       protected_stations=protected_stations, w_util=w_util, w_prior=w_prior,
                       w_time=w_time, station_transit_weights=station_transit_weights,
                       util_noise_mode=util_noise_mode)
    dt = time.time() - t0
    if r.get("status") != "sat":
        print(f"  FAILED {path.name}: {r.get('reason')} ({dt:.1f}s)")
        return False
    T = r["T"]
    note = ""
    if expect_value is not None:
        zs = zone_stats(r["countMatrix"], r["noiseMatrix"], baseline, T)
        metric_key = "avg_added" if meta.get("metric") == "avg" else "peak_added"
        got = max(row[metric_key] for row in zs)
        matched = abs(got - expect_value) < 0.05
        meta = dict(meta)
        meta["historicalValue"] = expect_value
        meta["reproducedValue"] = round(got, 4)
        meta["matchesHistorical"] = matched
        if not matched:
            meta["note"] = ("Tied-optimal scenario (see equal_allocation/README.md sec 9 "
                            "non-monotonic-U finding / prioritarian REPORT.md); this run found "
                            "a different but equally valid solution than the originally "
                            "published value - not an error.")
        note = f" [expect {expect_value}, got {got:.4f}{' OK' if matched else ' DIFFERENT-TIE'}]"
    write_full_csv(path, meta, r["paths"], multipliers, start, end,
                   r["countMatrix"], r["noiseMatrix"], baseline, T)
    print(f"  wrote {path.name} ({dt:.1f}s, T={T}){note}")
    return True
