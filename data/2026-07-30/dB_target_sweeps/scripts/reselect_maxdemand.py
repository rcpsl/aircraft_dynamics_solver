"""Re-select equal_allocation's target picks under a max-demand rule.

WHY: the published picks (`<combo>/<mode>/picks_summary.csv`) use a
"closest achievable value strictly below the target" rule (README.md §6).
That rule effectively *maximizes* noise subject to staying under the target,
which is close to the opposite of what a noise target usually means. Where
the target exceeds what the network can reach -- which is the case for the
`avg` metric, whose ceiling is ~6-9 dB, far below the 18 dB target -- it
degenerates into "find the loudest thing you can," and rewards small-fleet
configs that concentrate traffic onto a single station (the `avg` metric
being a max-over-stations of a per-station time average).

Observed consequence in the published data: for `avg`, the 18 dB pick is a
byte-duplicate of the 8 dB pick in 6 of 8 cells, and in the other 2 it is
*worse* than the 8 dB pick -- `s2-55_s6-45/community_equal` is strictly
dominated (louder AND 75% less demand served).

THE ALTERNATIVE RULE implemented here, for the reading "target = a noise
budget we are willing to tolerate":

    among all sat candidates with metric value strictly below the target,
    pick the one serving the MOST demand; tie-break toward the QUIETEST.

NO NEW SOLVES. This is a pure re-selection over the existing raw sweep in
`<combo>/<mode>/_search_log/search_log.csv`, which already contains every
(fleet-variant x U) candidate the original search evaluated.

Writes `picks_maxdemand.csv` alongside this script. Does NOT modify or
overwrite any published file.

Usage: python reselect_maxdemand.py
"""
import csv
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import AGG, SUMMARIES

HERE = SUMMARIES
EQ_ROOT = AGG / "equal_allocation"

COMBOS = ["s2-65_s6-55", "s2-65_s6-45", "s2-55_s6-55", "s2-55_s6-45"]
MODES = ["community_equal", "people_equal"]
TARGETS = ["3", "8", "18"]
METRICS = {"avg": "avg_max_stn", "peak": "peak_added_db"}

# Weighted demand (sum of aircraft multipliers) per fleet variant. 56 = full
# demand; matches `maxTraffic` in the full_routes/ preambles.
VARIANT_TRAFFIC = {"baseline_mult": 56, "N14_mult1": 14, "N7_mult1": 7, "N4_mult1": 4}
MAX_TRAFFIC = 56


def load_candidates(combo, mode):
    """All sat rows from the raw sweep, as (config, U, avg, peak) tuples."""
    path = EQ_ROOT / combo / mode / "_search_log" / "search_log.csv"
    out = []
    # errors="replace": some search logs carry non-UTF-8 bytes in the free-text
    # `reason` column. Only the numeric/status columns are read here, so lenient
    # decoding cannot corrupt anything this script actually uses.
    for r in csv.DictReader(open(path, encoding="utf-8", errors="replace")):
        if r["status"] != "sat":
            continue
        try:
            avg = float(r["avg_max_stn"])
            peak = float(r["peak_added_db"])
        except (ValueError, TypeError):
            continue
        out.append({"config": r["config"], "U": float(r["U"]), "avg": avg, "peak": peak})
    return out


def pick_closest_below(cands, metric, target):
    """The ORIGINAL rule: closest achievable value strictly below target."""
    key = "avg" if metric == "avg" else "peak"
    ok = [c for c in cands if c[key] < target]
    if not ok:
        return None
    return max(ok, key=lambda c: c[key])


def pick_max_demand(cands, metric, target):
    """The ALTERNATIVE rule: most demand served, tie-broken toward quietest."""
    key = "avg" if metric == "avg" else "peak"
    ok = [c for c in cands if c[key] < target]
    if not ok:
        return None
    # max traffic first, then quietest among those
    return min(
        ok,
        key=lambda c: (-VARIANT_TRAFFIC[c["config"]], c[key]),
    )


def main():
    rows = []
    for combo in COMBOS:
        for mode in MODES:
            cands = load_candidates(combo, mode)
            published = {
                (r["target_dB"], r["metric"]): r
                for r in csv.DictReader(
                    open(EQ_ROOT / combo / mode / "picks_summary.csv", encoding="utf-8")
                )
            }
            for metric in METRICS:
                for target in TARGETS:
                    t = float(target)
                    orig = pick_closest_below(cands, metric, t)
                    new = pick_max_demand(cands, metric, t)
                    pub = published.get((target, metric))

                    key = "avg" if metric == "avg" else "peak"
                    # Validation: does our reproduction of the ORIGINAL rule
                    # match the actually-published pick? If not, the search log
                    # doesn't fully explain the published data and the
                    # re-selection below can't be trusted for that cell.
                    repro_ok = ""
                    if pub and orig:
                        repro_ok = "yes" if abs(float(pub["value"]) - orig[key]) < 0.001 else "NO"
                    elif pub and not orig:
                        repro_ok = "NO(no-candidate)"

                    if not new:
                        rows.append({
                            "combo": combo, "mode": mode, "target_dB": target, "metric": metric,
                            "published_value": pub["value"] if pub else "",
                            "published_config": pub["config"] if pub else "",
                            "published_demandPct": "",
                            "reproducesPublished": repro_ok,
                            "maxdemand_value": "", "maxdemand_config": "", "maxdemand_U": "",
                            "maxdemand_demandPct": "", "changed": "no-candidate",
                        })
                        continue

                    pub_cfg = pub["config"] if pub else ""
                    pub_demand = (100 * VARIANT_TRAFFIC[pub_cfg] / MAX_TRAFFIC) if pub_cfg else ""
                    new_demand = 100 * VARIANT_TRAFFIC[new["config"]] / MAX_TRAFFIC

                    changed = "same"
                    if pub and (abs(float(pub["value"]) - new[key]) > 0.001 or pub_cfg != new["config"]):
                        changed = "CHANGED"

                    rows.append({
                        "combo": combo, "mode": mode, "target_dB": target, "metric": metric,
                        "published_value": round(float(pub["value"]), 4) if pub else "",
                        "published_config": pub_cfg,
                        "published_demandPct": round(pub_demand, 1) if pub_cfg else "",
                        "reproducesPublished": repro_ok,
                        "maxdemand_value": round(new[key], 4),
                        "maxdemand_config": new["config"],
                        "maxdemand_U": new["U"],
                        "maxdemand_demandPct": round(new_demand, 1),
                        "changed": changed,
                    })

    out = HERE / "picks_maxdemand.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "combo", "mode", "target_dB", "metric",
            "published_value", "published_config", "published_demandPct",
            "reproducesPublished",
            "maxdemand_value", "maxdemand_config", "maxdemand_U", "maxdemand_demandPct",
            "changed",
        ])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    n_repro = sum(1 for r in rows if r["reproducesPublished"] == "yes")
    n_bad = sum(1 for r in rows if r["reproducesPublished"].startswith("NO"))
    n_changed = sum(1 for r in rows if r["changed"] == "CHANGED")
    print(f"wrote {out}")
    print(f"  validation: reproduced the published pick in {n_repro}/{len(rows)} cells, {n_bad} mismatches")
    print(f"  max-demand rule changes the pick in {n_changed}/{len(rows)} cells")


if __name__ == "__main__":
    main()
