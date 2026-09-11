"""Derived metrics for the fleet-size study: one pure function over one solved row.

`derive(row, req) -> dict` reads only what the solver returned -- `paths`, and where
present `countMatrix` / `noiseMatrix` -- plus the request that produced it. No solver,
no I/O, no state. Everything the figures and tables in Sec. IV report comes through
here, so that a number in the paper has exactly one definition.

Two rules the module keeps to.

THE ACTIVE-NOISE WINDOW IS THE SOLVER'S. An aircraft contributes noise from its first
move through its first arrival, `[t_fm, t_arr]`, which is exactly the
`active[i][t] = moved[i][t] AND NOT arrived[i][t-1]` that Z3 constrained
(solver_server_dB._active_output_matrices). Occupancy rebuilt on any other window
would describe a routing the solver never agreed to.

STORED MATRICES WIN. When a row carries `countMatrix` / `noiseMatrix` they are used as
they stand, because they are what the solver constrained. Rows written before
2026-09-09 dropped them, so the same quantities are rebuilt from `paths` for those --
by the same arithmetic, which is what `selftest()` checks.

usage: python metrics.py            # self-test against three pre-existing rows
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import payload as P

AMBIENT_TIERS = (45, 55, 65)


# ---------------------------------------------------------------- primitives
def dB_increase(baseline_val, n, aircraft_dB):
    """Added level at a tile with `n` aircraft over it. Mirrors the solver's own."""
    if n <= 0:
        return 0.0
    return 10 * math.log10(1 + n * 10 ** ((aircraft_dB - baseline_val) / 10))


def tile_capacity(D, ambient, aircraft_dB=P.AIRCRAFT_DB):
    """How many simultaneous overflights a tile at `ambient` absorbs under cap `D`.

    Inverts dB_increase: n <= (10^(D/10) - 1) / 10^((alpha - ambient)/10). Analytic,
    no solver involved; the same expression figures.py: fig_capacity plots. A quiet
    tile has a SMALLER capacity than a loud one under the same cap, which is the
    whole reason a uniform D is not a uniform rule.
    """
    return max(0, math.floor((10 ** (D / 10) - 1) / 10 ** ((aircraft_dB - ambient) / 10)))


def _windows(paths, starts, ends):
    """(t_fm, t_arr) per aircraft, or None for one that never leaves."""
    out = []
    for i, p in enumerate(paths):
        s0, e0 = starts[i], ends[i]
        if s0 == e0:
            out.append(None)
            continue
        t_fm = next((t for t in range(len(p)) if p[t] != s0), None)
        if t_fm is None:
            out.append(None)
            continue
        t_arr = next((t for t in range(len(p)) if p[t] == e0), len(p) - 1)
        out.append((t_fm, t_arr))
    return out


def _bfs_floor(adj, src, dst, M):
    """Fewest hops from src to dst. The travel-time zero every detour is measured
    against, and independent of any principle."""
    from collections import deque
    if src == dst:
        return 0
    seen = [False] * (M + 1)
    seen[src] = True
    q = deque([(src, 0)])
    while q:
        n, d = q.popleft()
        for nb in range(1, M + 1):
            if nb != n and adj[n - 1][nb - 1] == 1 and not seen[nb]:
                if nb == dst:
                    return d + 1
                seen[nb] = True
                q.append((nb, d + 1))
    return None


def counts_from(row, req):
    """The count matrix, preferring the solver's own."""
    cm = row.get("countMatrix")
    if cm:
        return cm, len(cm[0])
    paths = row.get("paths")
    if not paths:
        return None, 0
    starts, ends = req["startPositions"], req["endPositions"]
    mult = req.get("aircraftMultipliers") or [1] * len(paths)
    T = len(paths[0])
    M = req["M"]
    counts = [[0] * T for _ in range(M)]
    for i, w in enumerate(_windows(paths, starts, ends)):
        if w is None:
            continue
        for t in range(w[0], w[1] + 1):
            counts[paths[i][t] - 1][t] += mult[i]
    return counts, T


def noise_from(row, req, counts=None):
    """The added-dB matrix, preferring the solver's own."""
    nm = row.get("noiseMatrix")
    if nm:
        return nm
    if counts is None:
        counts, _ = counts_from(row, req)
    if counts is None:
        return None
    base, a = req["baseline"], req["aircraftDB"]
    return [[dB_increase(base[m], c, a) for c in counts[m]] for m in range(len(counts))]


def _energy_sum(levels):
    """Add a list of added-dB contributions in ENERGY space.

    Summing decibels arithmetically, which `total_added` does, is not a physical
    quantity -- it is an index. Both are reported because they can rank routings
    differently and the paper has to say which one a figure shows: the arithmetic sum
    is what the Utilitarian objective minimises, the energy sum is what a city would
    actually hear.
    """
    tot = 0.0
    for L in levels:
        if L > 0:
            tot += 10 ** (L / 10)
    return 10 * math.log10(tot) if tot > 0 else 0.0


# ---------------------------------------------------------------- the function
def derive(row, req):
    """Every metric Sec. IV reports, for one solved row. Pure."""
    out = {}
    paths = row.get("paths")
    M = req["M"]
    D = float(req["D"])
    base = req["baseline"]
    aircraft_dB = float(req["aircraftDB"])
    starts, ends = req["startPositions"], req["endPositions"]
    mult = req.get("aircraftMultipliers") or [1] * len(starts)
    N = req["N"]

    # ---- solver ---------------------------------------------------------
    out["status"] = row.get("status")
    out["optimality"] = row.get("optimality")
    out["wall"] = row.get("wall")
    out["t_phase1"] = row.get("t_phase1")
    out["t_phase2"] = row.get("t_phase2")
    out["runner_par"] = row.get("runner_par")
    out["budget_s"] = row.get("budget_s")
    out["stoppedEarly"] = row.get("stoppedEarly")
    out["N"] = N
    out["D"] = D
    out["U"] = float(req["U"])
    out["T_used"] = row.get("T_used") or row.get("T_max_used")
    out["arrivalPenalty"] = row.get("arrivalPenalty")

    if not paths:
        return out

    counts, T = counts_from(row, req)
    noise = noise_from(row, req, counts)
    win = _windows(paths, starts, ends)
    out["T"] = T

    # ---- travel time ----------------------------------------------------
    # Trip length in hops, read off the paths. Not from totalTransit, whose units are
    # raw-scaled and deliberately left that way (see the UNITS WARNING in the solver).
    hops = [0 if w is None else w[1] - w[0] + 1 for w in win]
    floors = [_bfs_floor(req["adjacency"], starts[i], ends[i], M) for i in range(len(paths))]
    flown = [i for i, w in enumerate(win) if w is not None]
    out["tripHops"] = hops
    out["total_trip_hops"] = sum(hops)
    out["avg_trip_hops"] = (sum(hops) / len(flown)) if flown else 0.0
    known = [i for i in flown if floors[i] is not None]
    out["total_floor_hops"] = sum(floors[i] for i in known)
    out["extra_vs_floor"] = sum(hops[i] - floors[i] for i in known)
    out["extra_vs_floor_per_ac"] = (out["extra_vs_floor"] / len(known)) if known else 0.0
    out["aircraft_flown"] = len(flown)

    # Time spent NOT flying, which the hop count cannot see.
    #
    # `tripHops` counts an aircraft's active window, first move to first arrival. Two
    # routings can therefore agree on every trip length and still differ in when the
    # fleet is in the air: an aircraft held on the ground for two timesteps flies the
    # same number of hops and arrives two steps later. That shows up in the solver's
    # arrival penalty and nowhere else in the hop metrics, so it is measured here.
    #
    # It matters because it is a second currency a principle can spend. On this
    # instance the decibel-valued objectives pay in exactly this one: zero extra hops,
    # a later departure, which thins the peak by de-conflicting aircraft in time
    # rather than routing them apart in space.
    delays = [win[i][0] for i in flown]
    holds = [sum(1 for t in range(win[i][0] + 1, win[i][1] + 1)
                 if paths[i][t] == paths[i][t - 1]) for i in flown]
    out["departure_delay_total"] = sum(delays)
    out["departure_delay_max"] = max(delays) if delays else 0
    out["hover_steps_total"] = sum(holds)

    # ---- congestion -----------------------------------------------------
    # Over tile-timesteps that carry anything: an empty tile is not a low count, it
    # is an absence, and averaging it in would make a fleet look less concentrated
    # simply for using fewer tiles.
    occupied = [c for rowc in counts for c in rowc if c > 0]
    hist = {}
    for c in occupied:
        hist[c] = hist.get(c, 0) + 1
    out["max_count"] = max(occupied) if occupied else 0
    out["mean_count_occupied"] = (sum(occupied) / len(occupied)) if occupied else 0.0
    out["occupied_tile_timesteps"] = len(occupied)
    out["count_hist"] = {str(k): hist[k] for k in sorted(hist)}
    out["shared_tile_timesteps"] = sum(n for c, n in hist.items() if c >= 2)
    out["stations_touched"] = sum(1 for m in range(M) if any(c > 0 for c in counts[m]))

    # ---- capacity -------------------------------------------------------
    # Utilisation is per TILE against that tile's own capacity under D, because the
    # capacity a cap grants depends on the tile's ambient level. Reported over touched
    # tiles only: an untouched tile's utilisation is 0 by definition and would drag
    # the mean toward whatever fraction of the map went unused.
    cap = {b: tile_capacity(D, b, aircraft_dB) for b in AMBIENT_TIERS}
    out["tile_capacity"] = cap
    util, by_tier = [], {b: [] for b in AMBIENT_TIERS}
    for m in range(M):
        peak = max(counts[m]) if counts[m] else 0
        if peak <= 0:
            continue
        c = tile_capacity(D, base[m], aircraft_dB)
        u = (peak / c) if c > 0 else float("inf")
        util.append(u)
        if base[m] in by_tier:
            by_tier[base[m]].append(u)
    finite = [u for u in util if u != float("inf")]
    out["capacity_utilisation_max"] = max(util) if util else 0.0
    out["capacity_utilisation_mean"] = (sum(finite) / len(finite)) if finite else 0.0
    out["capacity_utilisation_by_tier"] = {
        str(b): (sum(v) / len(v)) if v else None for b, v in by_tier.items()}

    # ---- route sharing --------------------------------------------------
    # Two groupings, and the difference between them is the point. `identical_paths`
    # requires the same tiles at the same timesteps -- two aircraft genuinely flying
    # in formation. `identical_routes` ignores time: same corridor, possibly minutes
    # apart. The second is what "how many aircraft share a route" means to a reader.
    out["identical_paths"] = _grouping(
        [tuple(paths[i]) for i in flown])
    out["identical_routes"] = _grouping(
        [tuple(_dedupe(paths[i][win[i][0] - 1 if win[i][0] > 0 else 0: win[i][1] + 1]))
         for i in flown])

    # ---- noise ----------------------------------------------------------
    per_t = [sum(noise[m][t] for m in range(M)) for t in range(T)]
    out["total_added_by_t"] = [round(v, 4) for v in per_t]
    out["total_added_by_t_energy"] = [
        round(_energy_sum([noise[m][t] for m in range(M)]), 4) for t in range(T)]
    out["total_added"] = round(sum(per_t), 4)
    out["total_added_energy"] = round(
        _energy_sum([noise[m][t] for m in range(M) for t in range(T)]), 4)
    station_peak = [max(noise[m]) if noise[m] else 0.0 for m in range(M)]
    out["per_station_peak"] = [round(v, 4) for v in station_peak]
    out["peak_added"] = round(max(station_peak), 4) if station_peak else 0.0
    spread = [max(noise[m][t] for m in range(M)) - min(noise[m][t] for m in range(M))
              for t in range(T)]
    out["peak_spread"] = round(max(spread), 4) if spread else 0.0
    prot = req.get("protectedStations") or []
    out["protected_peak"] = (round(max(station_peak[s - 1] for s in prot), 4)
                             if prot else None)
    out["protected_stations"] = list(prot)

    # Where the traffic went, by ambient tier: the empirical counterpart to capacity.
    tiers = {b: 0 for b in AMBIENT_TIERS}
    tot = 0
    for i in flown:
        for t in range(win[i][0], win[i][1] + 1):
            b = base[paths[i][t] - 1]
            if b in tiers:
                tiers[b] += mult[i]
            tot += mult[i]
    out["tier_share"] = {str(b): (100.0 * tiers[b] / tot if tot else 0.0)
                         for b in AMBIENT_TIERS}
    return out


def _dedupe(seq):
    """Collapse runs of the same tile: a hover is not a new leg of the route."""
    out = []
    for x in seq:
        if not out or out[-1] != x:
            out.append(x)
    return out


def _grouping(items):
    """Group identical items and report what sharing looks like."""
    g = {}
    for x in items:
        g[x] = g.get(x, 0) + 1
    sizes = sorted(g.values(), reverse=True)
    return {"groups": len(sizes),
            "largest_group": sizes[0] if sizes else 0,
            "aircraft_in_shared": sum(s for s in sizes if s >= 2),
            "size_hist": {str(s): sizes.count(s) for s in sorted(set(sizes))}}


# ---------------------------------------------------------------- comparison
def extra_vs_baseline(m, m_base):
    """Travel cost of a principle against the no-fairness routing at the same N.

    Total and per-aircraft, in hops. `None` when the baseline cell is missing, never
    0 -- a missing comparison is not a zero difference.
    """
    if m is None or m_base is None:
        return {"extra_vs_baseline": None, "extra_vs_baseline_per_ac": None}
    a, b = m.get("total_trip_hops"), m_base.get("total_trip_hops")
    n = m.get("aircraft_flown") or 0
    if a is None or b is None:
        return {"extra_vs_baseline": None, "extra_vs_baseline_per_ac": None}
    return {"extra_vs_baseline": a - b,
            "extra_vs_baseline_per_ac": ((a - b) / n) if n else None}


# ---------------------------------------------------------------- self-test
def _req_for(row):
    """Rebuild the request a stored row was solved from."""
    req = P.build_request(**row["cfg"])
    job = _job_for(row.get("key"))
    if job and job.get("req"):
        req.update(job["req"])
    return req


_JOBS = None


def _job_for(key):
    global _JOBS
    if _JOBS is None:
        import glob
        _JOBS = {}
        for p in glob.glob(os.path.join(HERE, "plans", "*.json")):
            try:
                for j in json.load(open(p, encoding="utf-8"))["jobs"]:
                    _JOBS[j["key"]] = j
            except Exception:
                pass
    return _JOBS.get(str(key))


def selftest(n=3, verbose=True):
    """Check `derive` against the fields the solver and worker already recorded.

    Run on rows written BEFORE this module existed, which carry no countMatrix or
    noiseMatrix, so the check is a genuine second derivation rather than a copy:
    peakAddedDB, totalAddedDB, maxCount and tripHops must come out identical.
    """
    import glob
    rows = []
    for p in sorted(glob.glob(os.path.join(HERE, "results", "*.jsonl"))):
        if os.path.basename(p) in ("pilot.jsonl", "fleet.jsonl", "screen.jsonl",
                                   "fleet_default.jsonl", "smoke.jsonl", "ckt.jsonl"):
            continue
        for line in open(p, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("paths") and r.get("countMatrix") is None and "peakAddedDB" in r:
                rows.append(r)
    if len(rows) < n:
        print(f"FAIL: only {len(rows)} usable pre-existing rows"); return False

    step = max(1, len(rows) // n)
    picked = rows[::step][:n]
    ok = True
    for r in picked:
        m = derive(r, _req_for(r))
        checks = [
            ("peakAddedDB", r["peakAddedDB"], m["peak_added"]),
            ("totalAddedDB", r["totalAddedDB"], m["total_added"]),
            ("maxCount", r["maxCount"], m["max_count"]),
            ("tripHops", r["tripHops"], m["tripHops"]),
            ("stationsTouched", r["stationsTouched"], m["stations_touched"]),
            ("peakSpreadDB", r["peakSpreadDB"], m["peak_spread"]),
        ]
        for name, want, got in checks:
            same = (abs(want - got) < 5e-4) if isinstance(want, float) else (want == got)
            if not same:
                ok = False
                print(f"  MISMATCH {r['key']:<34} {name}: stored={want} derived={got}")
            elif verbose:
                print(f"  ok       {r['key']:<34} {name}")
    print("metrics.selftest:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    sys.exit(0 if selftest() else 1)
