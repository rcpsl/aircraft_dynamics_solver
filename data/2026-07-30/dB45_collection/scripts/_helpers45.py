"""Solve + CSV-write core for the 45 dB collection.

Adapted from dB_target_sweeps/scripts/_solve_helpers.py with four deliberate
changes:

1. Reads `data/base_model/uam-config_45dB.json` (dbPerCraft = 45), asserted on
   import. The 55 dB config is never touched.
2. Drops the `expect_value` / `historicalValue` / `matchesHistorical`
   machinery entirely -- it compared against 55 dB published numbers, which are
   meaningless here.
3. Stamps `dbPerCraft` into every CSV preamble. With two collections in
   existence it is no longer safe to leave implicit.
4. Adds `phase1_feasible()` -- a find_min_T-only probe used by the D-floor and
   ladder searches, which are far too expensive to run through the full
   two-phase solve.

Note on failure behaviour: this module calls `optimize_objectives` directly,
NOT through the Flask /solve route. The route's "phase-2 timeout silently
falls back to the phase-1 route with a warning field" path therefore does not
apply -- a phase-2 timeout here surfaces as status "phase2_failed" and the
caller drops the file. Failures are loud, not silent.
"""
import json
import os
import sys
import time

from _paths45 import REPO, CONFIG_JSON, DB_PER_CRAFT

sys.path.insert(0, str(REPO))
import solver_server_dB as S  # noqa: E402  -- never modified by this collection

# Optional Z3 search diversification; identical semantics to the 55 dB helper.
_seed = os.environ.get("Z3_RANDOM_SEED")
if _seed is not None:
    import z3
    z3.set_param("smt.random_seed", int(_seed))
    z3.set_param("sat.random_seed", int(_seed))

CFG = json.loads(CONFIG_JSON.read_text(encoding="utf-8"))
ADJ, M = CFG["adjacency"], CFG["M"]
AIRCRAFT_DB = CFG["dbPerCraft"]
assert AIRCRAFT_DB == DB_PER_CRAFT, (
    f"config dbPerCraft={AIRCRAFT_DB} but this collection is {DB_PER_CRAFT} dB"
)
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
COMBOS = list(COMBO_OVERRIDES)

# High=10 / Medium=5 / Low=1 population, CYO slots (stations 2, 6, 11, 13)
# pinned to a neutral 5. Regenerates exactly from the workbook Population
# column -- lens_definitions.people_weights() asserts this on every run, so if
# the grid changes again the mismatch is caught rather than silently used.
#
# Station 6 is CYO slot B and station 8 is Dove Springs (High population).
# The 55 dB collection had these two transposed, giving station 6 the weight 10
# and station 8 the neutral 5; this vector is NOT interchangeable with that one.
PEOPLE_WEIGHTS = [10, 5, 10, 5, 10, 5, 5, 10, 5, 10, 5, 5, 5, 5, 1, 5]


def baseline_for(combo):
    b = list(BASE_DEFAULT)
    for idx, val in COMBO_OVERRIDES[combo].items():
        b[idx] = val
    return b


VARIANT_INFO = {
    "baseline_mult": {"n": 14, "mult": None},  # None -> use FULL_MULT
    "N14_mult1": {"n": 14, "mult": 1},
    "N7_mult1": {"n": 7, "mult": 1},
    "N4_mult1": {"n": 4, "mult": 1},
}


def subsample_fleet(n):
    """'Every other' subsample of the 14 original start/end pairs."""
    if n >= len(FULL_START):
        return list(FULL_START), list(FULL_END)
    idx = list(range(0, len(FULL_START), max(1, len(FULL_START) // n)))[:n]
    return [FULL_START[i] for i in idx], [FULL_END[i] for i in idx]


def variant_to_fleet(variant):
    info = VARIANT_INFO[variant]
    n = info["n"]
    start, end = subsample_fleet(n)
    mult = list(FULL_MULT) if info["mult"] is None else [info["mult"]] * n
    return n, mult, start, end


def demand_pct(mult):
    return round(100 * sum(mult) / MAX_TRAFFIC, 2)


# ---------------------------------------------------------------- phase 1 only

def phase1_feasible(D, U, N, mult, start, end, baseline):
    """find_min_T only -- settles feasibility without paying for z3.Optimize.

    Returns (ok: bool, T_min: int|None, elapsed_s: float, status: str).
    """
    t0 = time.time()
    try:
        r = S.find_min_T(N, M, D, U, ADJ, start, end, baseline, AIRCRAFT_DB,
                         multipliers=mult)
    except Exception as e:  # Z3 access violations have been seen at large D
        return False, None, time.time() - t0, f"error:{type(e).__name__}"
    dt = time.time() - t0
    ok = r.get("status") == "sat"
    return ok, (r.get("T") if ok else None), dt, r.get("status", "?")


def search_d_floor(U, N, mult, start, end, baseline, lo=0.05, hi=20.0, tol=0.01):
    """Smallest D (to `tol`) for which any routing exists, by bisection on
    phase 1. Returns (d_floor, n_probes) or (None, n_probes) if even `hi` is
    infeasible."""
    probes = 0
    ok_hi, *_ = phase1_feasible(hi, U, N, mult, start, end, baseline)
    probes += 1
    if not ok_hi:
        return None, probes
    ok_lo, *_ = phase1_feasible(lo, U, N, mult, start, end, baseline)
    probes += 1
    if ok_lo:
        return lo, probes
    while hi - lo > tol:
        mid = (lo + hi) / 2
        ok, *_ = phase1_feasible(mid, U, N, mult, start, end, baseline)
        probes += 1
        if ok:
            hi = mid
        else:
            lo = mid
    return round(hi, 2), probes


# ---------------------------------------------------------------- full solve

def solve_scenario(N, D, U, T_max, baseline, multipliers, start, end,
                   optimize_util=False, optimize_prior=False, optimize_prop=False,
                   protected_stations=None, proportional_stations=None,
                   w_util=1.0, w_prior=1.0, w_prop=1.0,
                   w_time=0.1, station_transit_weights=None,
                   util_noise_mode=False):
    """Phase 1 + phase 2 exactly as solver_server_dB.py's /solve route would for
    soft-T (hardT=false), which every domain in this collection uses."""
    p1 = S.find_min_T(N, M, D, U, ADJ, start, end, baseline, AIRCRAFT_DB,
                      multipliers=multipliers)
    if p1["status"] != "sat":
        return p1
    T_use = max(p1["T"], T_max)
    return S.optimize_objectives(
        N, T_use, M, D, U, ADJ, start, end,
        optimize_util=optimize_util, optimize_prior=optimize_prior,
        optimize_prop=optimize_prop,
        protected_stations=protected_stations or [],
        proportional_stations=proportional_stations or [],
        w_util=w_util, w_prior=w_prior, w_prop=w_prop,
        soft_T=True, w_time=w_time,
        prop_alloc=False, station_transit_weights=station_transit_weights,
        util_noise_mode=util_noise_mode,
        aircraft_multipliers=multipliers, baseline=baseline,
        aircraft_dB=AIRCRAFT_DB,
    )


def zone_stats(count_matrix, noise_matrix, baseline, T):
    rows = []
    for m in range(M):
        added = [noise_matrix[m][t] for t in range(T)]
        counts = [count_matrix[m][t] for t in range(T)]
        avg_a = sum(added) / T
        rows.append({
            "zone": m + 1, "avg_added": avg_a, "avg_total": baseline[m] + avg_a,
            "peak_added": max(added), "peak_total": baseline[m] + max(added),
            "avg_aircraft": sum(counts) / T, "peak_aircraft": max(counts),
        })
    return rows


def travel_time(start, end, path_list):
    """First timestep index at which the aircraft reaches its destination.
    t=0 is always Start, so this is the arrival tick read straight off the
    routing table; it includes any time parked at Start before departing,
    which soft-T schedules do use to stagger active-noise windows. Aircraft
    with Start == End never travel.
    """
    if start == end:
        return 0
    for t, station in enumerate(path_list):
        if station == end:
            return t
    return len(path_list) - 1  # end pin guarantees arrival; defensive


def travel_stats(paths, mult, start, end, T):
    """(weighted mean, min, max) per-aircraft travel time.

    The mean is MULTIPLIER-WEIGHTED -- sum(t_i * mult_i) / sum(mult_i) -- so it
    answers "average trip length across all the traffic served", consistent
    with the zone table, which also reports weighted rather than physical
    aircraft counts. min/max are the unweighted range (weighting cannot change
    which values are extremes).
    """
    times = [travel_time(start[i], end[i], paths[i][:T]) for i in range(len(paths))]
    total_w = sum(mult)
    avg = sum(t * m for t, m in zip(times, mult)) / total_w if total_w else 0.0
    return round(avg, 3), min(times), max(times)


def metric_maxima(result, baseline):
    """(max avg added dB, max peak added dB) over the 16 zones -- the two
    numbers the equal_allocation ladder is selected against."""
    zs = zone_stats(result["countMatrix"], result["noiseMatrix"], baseline, result["T"])
    return (max(r["avg_added"] for r in zs), max(r["peak_added"] for r in zs))


def write_full_csv(path, meta, paths, mult, start, end, count_matrix,
                   noise_matrix, baseline, T, extra_zone_cols=None):
    """Route-CSV format: '#' preamble, Time Steps, routing block, zone table.

    `extra_zone_cols` is (header_list, {zone_1indexed: [values]}) for the
    proportional domain's Benefit/Tier/Income/Demand Served columns.
    """
    N = len(paths)
    traffic = sum(mult)
    lines = [f"# {k},{v}" for k, v in meta.items()]
    lines.append(f"# dbPerCraft,{AIRCRAFT_DB}")
    lines.append(f"# N,{N}")
    lines.append(f"# aircraftMultipliers,{mult}")
    lines.append(f"# totalTraffic,{traffic}")
    lines.append(f"# maxTraffic,{MAX_TRAFFIC}")
    lines.append(f"# demandFulfilledPct,{demand_pct(mult)}")
    avg_tt, min_tt, max_tt = travel_stats(paths, mult, start, end, T)
    lines.append(f"# avgTravelTimeWeighted,{avg_tt}")
    lines.append(f"# minTravelTime,{min_tt}")
    lines.append(f"# maxTravelTime,{max_tt}")
    lines.append(f"Time Steps (T),{T}")
    lines.append("")
    lines.append("Routing (station per aircraft per timestep):")
    lines.append(",".join(["Aircraft", "Multiplier", "Start", "End"]
                          + [f"T{t}" for t in range(T)]))
    for i in range(N):
        lines.append(",".join([str(i + 1), str(mult[i]), str(start[i]), str(end[i])]
                              + [str(p) for p in paths[i][:T]]))
    lines.append("")
    head = ("Zone,Avg Added dB,Avg Total dB,Peak Added dB,Peak Total dB,"
            "Avg Aircraft,Peak Aircraft")
    if extra_zone_cols:
        head += "," + ",".join(extra_zone_cols[0])
    lines.append(head)
    for row in zone_stats(count_matrix, noise_matrix, baseline, T):
        line = (f"Zone {row['zone']},{row['avg_added']:.2f},{row['avg_total']:.2f},"
                f"{row['peak_added']:.2f},{row['peak_total']:.2f},"
                f"{row['avg_aircraft']:.2f},{row['peak_aircraft']}")
        if extra_zone_cols:
            line += "," + ",".join(str(v) for v in extra_zone_cols[1][row["zone"]])
        lines.append(line)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_and_write(path, meta, N, D, U, T_max, baseline, multipliers, start, end,
                  extra_zone_cols=None, **solve_kw):
    """Solve and write one scenario. Skips if the file already exists, so reruns
    are always safe. Returns True on success."""
    if path.exists():
        print(f"  skip {path.name} (already exists)")
        return True
    t0 = time.time()
    r = solve_scenario(N, D, U, T_max, baseline, multipliers, start, end, **solve_kw)
    dt = time.time() - t0
    if r.get("status") != "sat":
        print(f"  FAILED {path.name}: {r.get('status')}/{r.get('reason')} ({dt:.1f}s)")
        return False
    meta = dict(meta)
    # The solver's own objective readouts are the direct evidence of whether the
    # objective did anything -- keep them in the file, not just in a log.
    for key in ("protectedNoise", "proportionalNoise", "totalTransit", "totalUtilNoise"):
        if key in r:
            meta[key] = r[key]
    write_full_csv(path, meta, r["paths"], multipliers, start, end,
                   r["countMatrix"], r["noiseMatrix"], baseline, r["T"],
                   extra_zone_cols=extra_zone_cols)
    print(f"  wrote {path.name} ({dt:.1f}s, T={r['T']})")
    return True
