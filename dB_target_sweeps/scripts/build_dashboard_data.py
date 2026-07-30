"""Precompute dashboard_data.json from the dB_target_sweeps CSV domains.

Also re-injects the blob into fairness-dashboard-v2.html between the
/*DATA-START*/ and /*DATA-END*/ markers, if that file exists.

Run:  python build_dashboard_data.py
"""
import csv
import json
import re
from pathlib import Path

from _paths import AGG as ROOT, DATA, DASHBOARDS
COMBOS = ["s2-65_s6-55", "s2-65_s6-45", "s2-55_s6-55", "s2-55_s6-45"]
MODES = ["community", "people"]


def parse_zone_csv(path):
    """Parse any of the domain CSVs -> (meta, zones[16])."""
    meta = {}
    zones = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row or not any(c.strip() for c in row):
                continue
            head = row[0].strip()
            if head.startswith("#"):
                key = head.lstrip("# ").strip()
                val = ",".join(row[1:]).strip()
                meta[key] = val
                continue
            if head.startswith("Time Steps"):
                meta["T"] = int(float(row[1]))
                continue
            if head.startswith("Flights"):
                meta["N"] = int(float(row[1]))
                continue
            if head.startswith("Total Traffic"):
                meta["traffic"] = int(float(row[1]))
                continue
            if head == "Zone":
                continue  # column header
            m = re.match(r"Zone\s*(\d+)", head)
            if m:
                zones.append({
                    "aa": float(row[1]),  # Avg Added dB
                    "at": float(row[2]),  # Avg Total dB
                    "pa": float(row[3]),  # Peak Added dB
                    "pt": float(row[4]),  # Peak Total dB
                    "ac": float(row[5]),  # Avg traffic (weighted)
                    "pc": float(row[6]),  # Peak traffic (weighted)
                })
    assert len(zones) == 16, f"{path}: expected 16 zones, got {len(zones)}"
    # normalize sufficientarian '#' metadata
    if "T_used" in meta:
        meta["T"] = int(float(meta["T_used"]))
    if "N" in meta and not isinstance(meta["N"], int):
        meta["N"] = int(float(meta["N"]))
    if "aircraftMultipliers" in meta:
        mults = json.loads(meta["aircraftMultipliers"])
        meta["N"] = len(mults)
        meta["traffic"] = sum(mults)
    if "protectedNoise" in meta:
        meta["protectedNoise"] = float(meta["protectedNoise"])
    keep = {k: meta[k] for k in ("T", "N", "traffic", "variant", "protectedNoise") if k in meta}
    keep.setdefault("N", 14)
    keep.setdefault("traffic", 56)
    return keep, zones


def build():
    data = {}

    # ---- Equal --------------------------------------------------------
    eq = {}
    for combo in COMBOS:
        eq[combo] = {}
        for mode, folder in [("community", "community_equal"), ("people", "people_equal")]:
            eq[combo][mode] = {}
            base = ROOT / "equal_allocation" / combo / folder
            picks = {}
            with open(base / "picks_summary.csv", newline="", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    picks[(r["target_dB"], r["metric"])] = r
            for metric in ("avg", "peak"):
                eq[combo][mode][metric] = {}
                for target in ("3", "8", "18"):
                    meta, zones = parse_zone_csv(base / f"{target}dB_{metric}.csv")
                    p = picks.get((target, metric), {})
                    if p:
                        meta["achieved"] = round(float(p["value"]), 2)
                        if p.get("note"):
                            meta["note"] = p["note"]
                    eq[combo][mode][metric][target] = {"meta": meta, "zones": zones}
    data["equal"] = eq

    # ---- Utilitarian ----------------------------------------------------
    ut = {}
    for combo in COMBOS:
        ut[combo] = {}
        dmin = {}
        for line in (ROOT / "utilitarian" / "utilitarian_peak" / combo / "d_min.txt").read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                dmin[k.strip()] = v.strip()
        for mode, fname in [("community", "no_weight.csv"), ("people", "weighted.csv")]:
            ut[combo][mode] = {}
            for metric, domain in [("avg", "utilitarian"), ("peak", "utilitarian_peak")]:
                meta, zones = parse_zone_csv(ROOT / "utilitarian" / domain / combo / fname)
                if metric == "peak":
                    meta["D_floor"] = float(dmin["D_feasibility_min"])
                    meta["D_used"] = float(dmin["D_used_for_final_csvs"])
                else:
                    meta["D_used"] = 12.0
                ut[combo][mode][metric] = {"meta": meta, "zones": zones}
    data["utilitarian"] = ut

    # ---- Sufficientarian ------------------------------------------------
    sf = {}
    for combo in COMBOS:
        sf[combo] = {}
        for mode, folder in [("community", "unweighted"), ("people", "weighted")]:
            sf[combo][mode] = {}
            for cap, fname in [("3.02", "Dmin_3.02.csv"), ("8", "D8.csv"), ("18", "D18.csv")]:
                meta, zones = parse_zone_csv(ROOT / "sufficientarian" / combo / folder / fname)
                sf[combo][mode][cap] = {"meta": meta, "zones": zones}
    data["sufficientarian"] = sf

    # ---- Prioritarian ---------------------------------------------------
    pr = {}
    for combo in COMBOS:
        pr[combo] = {}
        for mode in ("community", "people"):
            pr[combo][mode] = {}
            for lens in ("low_income", "transit_desert", "few_jobs", "mostly_renters"):
                meta, zones = parse_zone_csv(ROOT / "prioritarian" / "step3_baseline_sweep" / combo / mode / f"{lens}.csv")
                pr[combo][mode][lens] = {"meta": meta, "zones": zones}
    data["prioritarian"] = pr

    return data


def inject(blob_text):
    html_path = DASHBOARDS / "fairness-dashboard-v2.html"
    if not html_path.exists():
        return False
    html = html_path.read_text(encoding="utf-8")
    new = re.sub(
        r"/\*DATA-START\*/.*?/\*DATA-END\*/",
        "/*DATA-START*/const SOLVED=" + blob_text + ";/*DATA-END*/",
        html, flags=re.S)
    html_path.write_text(new, encoding="utf-8")
    return True


if __name__ == "__main__":
    data = build()
    blob = json.dumps(data, separators=(",", ":"))
    (DATA / "dashboard_data.json").write_text(blob, encoding="utf-8")
    print(f"dashboard_data.json written ({len(blob)/1024:.0f} KB)")
    if inject(blob):
        print("re-injected into fairness-dashboard-v2.html")
    else:
        print("fairness-dashboard-v2.html not found - skipped injection")
