"""Supplementary dataset: multiplier-weighted average per-aircraft travel
time, derived from the routing tables already present in every full_routes/
CSV.

Per-aircraft travel time: for aircraft with Start != End, the first
timestep index (0-indexed; t=0 is always Start) at which the aircraft's
path reaches End. Aircraft with Start == End never travel: travel time 0.
This is the arrival tick read directly off the routing table -- it does not
try to detect a "first departure" tick separately, so it also counts any
time the aircraft sits parked at Start before departing (soft-T schedules
can pick a later departure to space out active-noise windows). If you need
pure time-in-motion instead, see the `_active_output_matrices` t_fm/t_arr
logic in solver_server_dB.py and adjust accordingly -- that's a different,
also-defensible definition, not implemented here.

`avgTravelTimeWeighted` is the MULTIPLIER-WEIGHTED mean of those per-aircraft
times: sum(time_i * mult_i) / sum(mult_i). Each physical aircraft represents
`mult` virtual aircraft / traffic units, so this answers "average trip
length across all the traffic served," consistent with how the rest of this
dataset counts aircraft (the noise CSVs report multiplier-weighted, not
physical, counts). minTravelTime/maxTravelTime are the unweighted range of
per-aircraft times (weighting doesn't change which values are the extremes).

Walks every CSV under full_routes/<combo>/<domain-path>/, skipping any file
without a routing block (there shouldn't be any among the 127 present, but
this is defensive rather than assumed). Writes one consolidated summary:

    full_routes/travel_time/travel_time_summary.csv

One row per source CSV: combo, domain, mode/knob fields (whatever the
preamble carries), N, totalTraffic, T_used, weighted-avg / min / max travel
time across that file's aircraft.

Usage: python compute_travel_time.py
"""
import csv as csvmod
import sys
from pathlib import Path

from _paths import ROUTES as ROOT, SUMMARIES
COMBOS = ["s2-65_s6-55", "s2-65_s6-45", "s2-55_s6-55", "s2-55_s6-45"]
OUT_DIR = SUMMARIES
OUT_FILE = OUT_DIR / "travel_time_summary.csv"


def parse_file(path):
    """Returns (meta: dict, aircraft_rows: list of (mult, start, end, path_list)) or None if no routing block."""
    meta = {}
    aircraft_rows = []
    T = None
    with open(path, newline="", encoding="utf-8") as f:
        lines = f.read().splitlines()

    in_routing = False
    header_seen = False
    for line in lines:
        if line.startswith("#"):
            key, _, val = line[1:].strip().partition(",")
            meta[key.strip()] = val.strip()
            continue
        if line.startswith("Time Steps"):
            T = int(float(line.split(",", 1)[1]))
            continue
        if line.startswith("Routing ("):
            in_routing = True
            continue
        if in_routing and line.startswith("Aircraft,Multiplier,Start,End"):
            header_seen = True
            continue
        if in_routing and header_seen:
            if not line.strip():
                in_routing = False
                continue
            parts = line.split(",")
            # Aircraft,Multiplier,Start,End,T0,T1,...
            mult = float(parts[1])
            start = int(parts[2])
            end = int(parts[3])
            path_list = [int(p) for p in parts[4:4 + T]]
            aircraft_rows.append((mult, start, end, path_list))

    if not aircraft_rows:
        return None
    return meta, T, aircraft_rows


def travel_time(start, end, path_list):
    if start == end:
        return 0
    for t, station in enumerate(path_list):
        if station == end:
            return t
    return len(path_list) - 1  # shouldn't happen (end pin guarantees arrival) -- defensive fallback


def main():
    OUT_DIR.mkdir(exist_ok=True)
    rows = []
    n_files = 0
    n_skipped = 0

    for combo in COMBOS:
        combo_dir = ROOT / combo
        if not combo_dir.is_dir():
            continue
        for csv_path in sorted(combo_dir.rglob("*.csv")):
            parsed = parse_file(csv_path)
            if parsed is None:
                n_skipped += 1
                continue
            meta, T, aircraft_rows = parsed
            n_files += 1

            times = [travel_time(start, end, path_list) for (_mult, start, end, path_list) in aircraft_rows]
            mults = [mult for (mult, _s, _e, _p) in aircraft_rows]
            # Multiplier-weighted average: each physical aircraft represents `mult`
            # virtual aircraft / traffic units, so weighting answers "average trip
            # length across all the traffic served," matching how the rest of this
            # dataset counts aircraft (noise CSVs report weighted, not physical, counts).
            total_w = sum(mults)
            avg_t = sum(t * m for t, m in zip(times, mults)) / total_w if total_w else 0.0

            rel = csv_path.relative_to(ROOT).as_posix()
            domain = meta.get("domain", "")
            mode = meta.get("mode", "")
            extra = meta.get("target_dB") or meta.get("cap") or meta.get("lens") or ""

            rows.append({
                "file": rel,
                "combo": combo,
                "domain": domain,
                "mode": mode,
                "knob": extra,
                "N": len(aircraft_rows),
                "totalTraffic": round(total_w, 3),
                "T_used": T,
                "avgTravelTimeWeighted": round(avg_t, 3),
                "minTravelTime": min(times),
                "maxTravelTime": max(times),
            })

    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csvmod.DictWriter(f, fieldnames=[
            "file", "combo", "domain", "mode", "knob", "N", "totalTraffic",
            "T_used", "avgTravelTimeWeighted", "minTravelTime", "maxTravelTime",
        ])
        w.writeheader()
        for row in rows:
            w.writerow(row)

    print(f"wrote {OUT_FILE} -- {n_files} files summarized, {n_skipped} skipped (no routing block)")


if __name__ == "__main__":
    main()
