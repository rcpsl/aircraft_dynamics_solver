"""Apply metrics.derive to every fleet-study row -> results/fleet_metrics.{csv,json}.

One row per solve. The CSV is the flat table every number in Sec. IV is traceable to;
the JSON keeps the vector-valued metrics (`total_added_by_t`, `count_hist`,
`per_station_peak`, `tripHops`) that a CSV cell cannot hold, JSON-encoded in the CSV
so nothing is silently lost.

`extra_vs_baseline` is joined here rather than inside `derive`, because it is the only
metric that needs a second row: the `baseline` condition at the same fleet size and the
same setup. Where that row is missing the field is None, never 0 -- an absent
comparison is not a zero difference.

usage: python metrics_run.py [file.jsonl ...]      default: fleet, fleet_default, pilot
"""
import csv
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import metrics as MX
import divergence as DV

RES = os.path.join(HERE, "results")
# `pilot.jsonl` is deliberately NOT here. Its four cells are the same experiment as the
# fleet sweep's N=16 cells -- same setup, same conditions, same unlimited budget -- run
# under different keys, so including it would seat two rows for one cell and let an
# arbitrary one win. The pilot stays on disk as the Phase-1 record; the fleet sweep is
# the paper's data. Pass it explicitly if you want it.
DEFAULT_FILES = ["results/fleet.jsonl", "results/fleet_default.jsonl"]

# Vector- or dict-valued metrics: kept whole in the JSON, JSON-encoded in the CSV.
COMPOUND = ("count_hist", "identical_paths", "identical_routes", "tier_share",
            "capacity_utilisation_by_tier", "tile_capacity", "total_added_by_t",
            "total_added_by_t_energy", "per_station_peak", "tripHops",
            "protected_stations", "setup")

# Column order for the CSV: identity, then the four metric families, then the solver.
LEAD = ["key", "sweep", "setup_name", "condition", "N", "demand_factor", "D", "U",
        "slack", "T", "T_used", "status", "optimality", "stoppedEarly",
        "avg_trip_hops", "total_trip_hops", "total_floor_hops", "extra_vs_floor",
        "extra_vs_floor_per_ac", "extra_vs_baseline", "extra_vs_baseline_per_ac",
        "arrivalPenalty",
        "max_count", "mean_count_occupied", "shared_tile_timesteps",
        "occupied_tile_timesteps", "stations_touched",
        "capacity_utilisation_max", "capacity_utilisation_mean",
        "occ_dist_vs_baseline",
        "total_added", "total_added_energy", "peak_added", "peak_spread",
        "protected_peak",
        "wall", "t_phase1", "t_phase2", "runner_par", "budget_s", "aircraft_flown"]


def load(files):
    rows = []
    for f in files:
        p = f if os.path.isabs(f) else os.path.join(HERE, f)
        if not os.path.exists(p):
            continue
        sweep = os.path.basename(p)[:-6]
        for line in io.open(p, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            r["_sweep"] = sweep
            rows.append(r)
    return rows


def _best(rows):
    """One row per key, keeping the strongest if a key was somehow run twice."""
    rank = {"optimal": 3, "partial": 2}
    out = {}
    for r in rows:
        k = r.get("key")
        cur = out.get(k)
        if cur is None or rank.get(r.get("optimality"), 0) > rank.get(cur.get("optimality"), 0):
            out[k] = r
    return list(out.values())


def build(files=None):
    # A row that carries no answer carries no metrics either: `derive` would return a
    # shell of Nones that then reads as a cell with data in every table downstream.
    # These are reported as unfinished, from the runner log and the checkpoints, not
    # as rows with empty columns.
    import runner as _R
    rows = [r for r in _best(load(files or DEFAULT_FILES))
            if str(r.get("status", "")) not in _R.UNANSWERED]
    recs = []
    for r in rows:
        try:
            req = MX._req_for(r)
        except Exception as e:
            print(f"  skip {r.get('key')}: cannot rebuild request ({e})")
            continue
        m = MX.derive(r, req)
        m["key"] = r.get("key")
        m["sweep"] = r.get("_sweep")
        m["condition"] = DV.principle_of(r)
        m["setup"] = r.get("setup") or {}
        m["setup_name"] = (r.get("setup") or {}).get("name", "default")
        m["demand_factor"] = r.get("cfg", {}).get("demand_factor")
        m["slack"] = r.get("slack")
        m["probe"] = r.get("probe", False)
        recs.append(m)

    # Join each condition to the baseline at the same setup and fleet size.
    base = {(m["setup_name"], m["N"]): m for m in recs if m["condition"] == "baseline"}
    for m in recs:
        m.update(MX.extra_vs_baseline(m, base.get((m["setup_name"], m["N"]))))

    # Distance from the no-fairness routing, on occupancy rather than path lists.
    # This is the quantity that says whether choosing a principle changed anything at
    # all: 0 means the principle returned exactly the routing the solver serves when
    # no principle is selected. Occupancy, because relabelling two interchangeable
    # aircraft rewrites every path without changing the map or the noise.
    occ = {}
    for r in _best(load(files or DEFAULT_FILES)):
        if not r.get("paths") or r.get("probe"):
            continue
        k = ((r.get("setup") or {}).get("name", "default"), DV.principle_of(r), r.get("N"))
        try:
            occ[k] = DV.occupancy(r, MX._req_for(r))
        except Exception:
            pass
    for m in recs:
        b = occ.get((m["setup_name"], "baseline", m["N"]))
        a = occ.get((m["setup_name"], m["condition"], m["N"]))
        m["occ_dist_vs_baseline"] = (round(DV.distance(a, b), 4)
                                     if a is not None and b is not None else None)

    recs.sort(key=lambda m: (m.get("setup_name") or "", m.get("N") or 0,
                             m.get("condition") or ""))
    return recs


def write(recs):
    os.makedirs(RES, exist_ok=True)
    jp = os.path.join(RES, "fleet_metrics.json")
    with io.open(jp, "w", encoding="utf-8") as f:
        json.dump(recs, f, indent=1)

    keys = list(LEAD)
    for m in recs:
        for k in m:
            if k not in keys:
                keys.append(k)
    cp = os.path.join(RES, "fleet_metrics.csv")
    with io.open(cp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for m in recs:
            row = {}
            for k in keys:
                v = m.get(k)
                row[k] = json.dumps(v) if (k in COMPOUND or isinstance(v, (dict, list))) else v
            w.writerow(row)
    print(f"{len(recs)} rows -> {cp}")
    print(f"{len(recs)} rows -> {jp}")
    return cp, jp


def cells(files=None, include_probes=False):
    """RAW rows of the fleet study, keyed (setup_name, condition, N).

    Figures that draw a routing need `paths`, which fleet_metrics.json does not carry.
    This is the one loader they share with the tables, so a figure can never be built
    from a different set of rows than the table beside it.

    Probe rows are excluded by default: they were run under a cap, they exist only to
    have decided the setup, and nothing in the paper may rest on one.
    """
    out = {}
    rank = {"optimal": 3, "partial": 2}
    for r in _best(load(files or DEFAULT_FILES)):
        if r.get("probe") and not include_probes:
            continue
        if not r.get("paths"):
            continue
        k = ((r.get("setup") or {}).get("name", "default"),
             DV.principle_of(r), r.get("N"))
        cur = out.get(k)
        if cur is None or rank.get(r.get("optimality"), 0) > rank.get(cur.get("optimality"), 0):
            out[k] = r
    return out


def metrics_index(path=None):
    """fleet_metrics.json keyed the same way, or {} if it has not been built."""
    p = path or os.path.join(RES, "fleet_metrics.json")
    if not os.path.exists(p):
        return {}
    recs = json.load(io.open(p, encoding="utf-8"))
    return {(m.get("setup_name", "default"), m.get("condition"), m.get("N")): m
            for m in recs if not m.get("probe")}


if __name__ == "__main__":
    files = sys.argv[1:] or None
    recs = build(files)
    if not recs:
        print("no rows yet"); sys.exit(0)
    write(recs)
    by = {}
    for m in recs:
        by.setdefault((m["setup_name"], m["N"]), []).append(m)
    print("\nsetup            N   conditions  proven")
    for (s, n), ms in sorted(by.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0)):
        prov = sum(1 for m in ms if m.get("optimality") == "optimal")
        print(f"{s:<16} {str(n):>3}   {len(ms):>9}  {prov:>6}")
