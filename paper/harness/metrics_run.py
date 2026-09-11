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


def build(files=None, agg=False):
    # A row that carries no answer carries no metrics either: `derive` would return a
    # shell of Nones that then reads as a cell with data in every table downstream.
    # These are reported as unfinished, from the runner log and the checkpoints, not
    # as rows with empty columns.
    import runner as _R
    rows = []
    for r in _best(load(files or DEFAULT_FILES)):
        st = str(r.get("status", ""))
        if st in _R.UNANSWERED:
            continue
        # A phase-2 failure carries phase 1's UNWEIGHTED route -- the solver's fallback,
        # with no principle applied at all. `derive` would happily compute a full set of
        # metrics from it and the cell would then read as the principle's answer. It is
        # not one. These are reported as fallbacks by table_frontier and by the runner
        # log; they do not become cells.
        if st.startswith("phase2_failed") or r.get("fellBackToPhase1"):
            continue
        rows.append(r)
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
        m["perm"] = r.get("perm")
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
                             m.get("condition") or "", m.get("perm") or 0))
    return aggregate(recs) if agg else recs


def write(recs, stem="fleet_metrics", cells_recs=None):
    """Write the flat per-run table, and -- when given -- the banded cell table.

    Both, deliberately. The CSV is every individual solve, so any number in the paper
    can be traced to the run that produced it; the `<stem>.json` is the K runs collapsed
    into one cell with its permutation band, which is what every table and figure reads.
    Keeping only the second would hide which run any value came from; keeping only the
    first would let a figure quietly plot one draw as if it were the answer.
    """
    os.makedirs(RES, exist_ok=True)
    jp = os.path.join(RES, stem + ".json")
    with io.open(jp, "w", encoding="utf-8") as f:
        json.dump(cells_recs if cells_recs is not None else recs, f, indent=1)

    keys = list(LEAD)
    for m in recs:
        for k in m:
            if k not in keys:
                keys.append(k)
    cp = os.path.join(RES, stem + ".csv")
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


# Metrics that are averaged and banded across a cell's permutation runs. Everything
# else on a cell record (D, U, T, the setup, the status counts) is either identical
# across the runs or is reported per run.
BANDED = ("avg_trip_hops", "total_trip_hops", "extra_vs_floor", "extra_vs_baseline",
          "arrivalPenalty", "departure_delay_total", "hover_steps_total",
          "max_count", "mean_count_occupied", "shared_tile_timesteps",
          "occupied_tile_timesteps", "stations_touched",
          "capacity_utilisation_max", "capacity_utilisation_mean",
          "total_added", "total_added_energy", "peak_added", "peak_spread",
          "protected_peak", "occ_dist_vs_baseline", "wall", "t_phase1", "t_phase2")


def aggregate(recs):
    """Collapse a cell's K permutation runs into one record with a band.

    For each banded metric the record carries `<m>` (the mean), `<m>_min`, `<m>_max`
    and `floor_<m>` = max - min. That floor is the tie-break measured with no confound:
    the permuted problems are the same problem, so the only thing separating the runs
    is which member of the optimal set came back.

    ONLY PROVEN RUNS contribute to a band. An unproven run is at whatever point the
    search reached, which is not a sample from the optimal set, and averaging it in
    would inflate the floor and make every comparison look unattributable. A cell with
    no proven run is kept -- its routing is still real -- but carries no band, and
    `attributable()` refuses to rule on it.
    """
    by = {}
    for m in recs:
        by.setdefault((m.get("setup_name"), m.get("condition"), m.get("N")),
                      []).append(m)
    out = []
    for (setup, cond, n), runs in by.items():
        proven = [r for r in runs if r.get("optimality") == "optimal"]
        base = dict(sorted(proven or runs, key=lambda r: (r.get("perm") or 0))[0])
        base["runs"] = len(runs)
        base["runs_proven"] = len(proven)
        base["perm_keys"] = sorted(str(r.get("key")) for r in runs)
        base["optimality"] = "optimal" if len(proven) == len(runs) else (
            "partial" if proven else (runs[0].get("optimality") or "none"))
        base["all_proven"] = len(proven) == len(runs) and len(runs) > 0
        for f in BANDED:
            vals = [r.get(f) for r in proven if r.get(f) is not None]
            if not vals:
                base.pop(f"floor_{f}", None)
                continue
            base[f] = sum(vals) / len(vals)
            base[f + "_min"] = min(vals)
            base[f + "_max"] = max(vals)
            base["floor_" + f] = max(vals) - min(vals)
        out.append(base)
    out.sort(key=lambda m: (m.get("setup_name") or "", m.get("N") or 0,
                            m.get("condition") or ""))
    return out


def attributable(a, b, field):
    """Is the difference between two cells on `field` evidence about the condition?

    Two conditions must clear BOTH tests:
      * their means differ by more than the larger of the two floors, and
      * their permutation ranges do not overlap.

    The second is the stricter one and is what stops a claim resting on two bands that
    happen to have different centres. Returns None when either cell has no band, which
    is not the same as False and must not be reported as one.
    """
    if a is None or b is None:
        return None
    fa, fb = a.get("floor_" + field), b.get("floor_" + field)
    if fa is None or fb is None or a.get(field) is None or b.get(field) is None:
        return None
    if not (a.get("all_proven") and b.get("all_proven")):
        return None
    gap = abs(a[field] - b[field])
    if gap <= max(fa, fb):
        return False
    lo_a, hi_a = a[field + "_min"], a[field + "_max"]
    lo_b, hi_b = b[field + "_min"], b[field + "_max"]
    return hi_a < lo_b or hi_b < lo_a


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
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    stem = "fleet_metrics"
    if "--stem" in sys.argv:
        stem = sys.argv[sys.argv.index("--stem") + 1]
        args = [a for a in args if a != stem]
    files = args or None
    recs = build(files)
    if not recs:
        print("no rows yet"); sys.exit(0)
    write(recs, stem=stem, cells_recs=aggregate(recs))
    by = {}
    for m in recs:
        by.setdefault((m["setup_name"], m["N"]), []).append(m)
    print("\nsetup            N   conditions  proven")
    for (s, n), ms in sorted(by.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0)):
        prov = sum(1 for m in ms if m.get("optimality") == "optimal")
        print(f"{s:<16} {str(n):>3}   {len(ms):>9}  {prov:>6}")
