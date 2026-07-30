#!/usr/bin/env python3
"""Build the dashboard's embedded data blob from the dB45_collection CSVs.

Reads the 156 result files under data/full_routes/ plus
data/summaries/cyo_selection_map.csv, and writes:

  build/dashboard_data.json          inspectable blob
  <dashboard>.html                   same blob injected between
                                     /*DATA-START*/ ... /*DATA-END*/

Run from anywhere:  python build/build_dashboard_data.py

Nothing here reshapes, interpolates or substitutes data. The twelve cells the
solver could not finish (handoff section 6.2) are emitted as explicit
`unavailable` markers carrying their reason, never as missing keys.
"""
import csv
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
FR = os.path.join(DATA, "full_routes")
HTML = os.path.join(ROOT, "uam-dashboard-standalone-2026-07-20-v2.html")
OUT_JSON = os.path.join(HERE, "dashboard_data.json")

COMBOS = ["s2-65_s6-55", "s2-65_s6-45", "s2-55_s6-55", "s2-55_s6-45"]
MODES = ["community", "people"]
LENSES = ["low_income", "people_of_color", "transit_desert", "few_jobs"]

# mode -> per-domain directory name (handoff section 7.3)
MODE_DIR = {
    "equal_allocation": {"community": "community_equal", "people": "people_equal"},
    "utilitarian": {"community": "no_weight", "people": "weighted"},
    "utilitarian_peak": {"community": "no_weight", "people": "weighted"},
    "sufficientarian": {"community": "unweighted", "people": "weighted"},
    "prioritarian": {"community": "community", "people": "people"},
    "prioritarian_cyo": {"community": "community", "people": "people"},
}

# The twelve cells that exceeded the solver's time budget (handoff section 6.2).
# Phase 1 proved a full-demand routing exists in every one; only the optimiser
# ran out of compute. This is NOT infeasibility and must never read as one.
UNAVAILABLE_BUDGETS = {
    ("s2-65_s6-55", "utilitarian_peak", "no_weight", "result"): "1800 s budget, gave up at 1879 s",
    ("s2-65_s6-55", "utilitarian_peak", "weighted", "result"): "1800 s budget, gave up at 1965 s",
    ("s2-55_s6-55", "utilitarian_peak", "no_weight", "result"): "1800 s budget, timed out",
    ("s2-55_s6-55", "utilitarian_peak", "weighted", "result"): "1800 s budget, timed out",
    ("s2-65_s6-45", "utilitarian_peak", "weighted", "result"): "1800 s budget, timed out",
    ("s2-55_s6-45", "utilitarian_peak", "weighted", "result"): "1800 s budget, timed out",
    ("s2-65_s6-55", "equal_allocation", "people_equal", "U3"): "600 s across three T_max settings, gave up at 625/624/644 s",
    ("s2-55_s6-55", "equal_allocation", "people_equal", "U3"): "600 s across three T_max settings, gave up at 628/637/633 s",
    ("s2-65_s6-55", "sufficientarian", "weighted", "D3"): "900 s across three random seeds, gave up at 916/920/915 s",
    ("s2-55_s6-55", "sufficientarian", "weighted", "D3"): "900 s across three random seeds, timed out",
    ("s2-65_s6-45", "sufficientarian", "weighted", "D8"): "900 s across three random seeds, gave up at 924/932/920 s",
    ("s2-55_s6-45", "sufficientarian", "weighted", "D8"): "900 s across three random seeds, timed out",
}

UNAVAILABLE_REASON = (
    "No result exists for this combination because the optimiser exceeded its "
    "time budget. A routing that serves full demand is known to exist here — "
    "the first solve phase proved it. This is a limit of the solver, not "
    "infeasibility, not unfairness, and not a limit on service."
)


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------

def read_result(path):
    """Parse one result CSV. Preamble splits on the FIRST comma only."""
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.read().split("\n")

    pre = {}
    i = 0
    while i < len(lines) and lines[i].startswith("#"):
        key, _, value = lines[i][1:].strip().partition(",")
        pre[key.strip()] = value
        i += 1

    assert lines[i].startswith("Time Steps (T),"), (path, lines[i])
    T = int(lines[i].split(",", 1)[1])
    i += 1

    while i < len(lines) and not lines[i].strip():
        i += 1
    assert lines[i].startswith("Routing"), (path, lines[i])
    i += 2  # skip the "Routing:" line and the column header

    routing = []
    while i < len(lines) and lines[i].strip():
        row = next(csv.reader(io.StringIO(lines[i])))
        routing.append({"mult": int(row[1]), "path": [int(x) for x in row[4:]]})
        i += 1

    while i < len(lines) and not lines[i].strip():
        i += 1
    assert lines[i].startswith("Zone,Avg Added dB"), (path, lines[i])
    i += 1

    zones = []
    while i < len(lines) and lines[i].strip():
        r = next(csv.reader(io.StringIO(lines[i])))
        zones.append({"aa": float(r[1]), "at": float(r[2]), "pa": float(r[3]),
                      "pt": float(r[4]), "ac": float(r[5]), "pc": float(r[6])})
        i += 1
    assert len(zones) == 16, (path, len(zones))

    return {"pre": pre, "T": T, "routing": routing, "zones": zones}


def routing_signature(res):
    """Order-insensitive signature of the physical routing."""
    return tuple(sorted((tuple(collapse(c["path"])), c["mult"]) for c in res["routing"]))


def collapse(path):
    """Drop consecutive duplicates: pre-departure parking and the arrival tail."""
    out = []
    for station in path:
        if not out or out[-1] != station:
            out.append(station)
    return out


def routes_of(res, path):
    grouped, order = {}, []
    for craft in res["routing"]:
        key = tuple(collapse(craft["path"]))
        if key not in grouped:
            grouped[key] = 0
            order.append(key)
        grouped[key] += craft["mult"]
    routes = sorted(({"path": list(k), "flights": grouped[k]} for k in order),
                    key=lambda r: -r["flights"])
    total = sum(r["flights"] for r in routes)
    expected = int(float(res["pre"]["totalTraffic"]))
    assert total == expected, f"{path}: flights {total} != totalTraffic {expected}"
    return routes


def num(pre, key, cast=float):
    v = pre.get(key, "")
    if v == "" or v is None:
        return None
    try:
        return cast(v)
    except ValueError:
        return None


def flag(pre, key):
    v = pre.get(key)
    if v is None:
        return None
    return v.strip().lower().startswith("true")


def stations(pre, key):
    v = pre.get(key)
    if not v:
        return None
    return [int(x) for x in re.findall(r"\d+", v)]


def leaf(path, extra):
    res = read_result(path)
    pre = res["pre"]
    assert pre.get("dbPerCraft") == "45", (path, pre.get("dbPerCraft"))

    meta = {
        "T": res["T"],
        "N": int(float(pre["N"])),
        "traffic": int(float(pre["totalTraffic"])),
        "demandPct": num(pre, "demandFulfilledPct"),
        "maxAvgAddedDb": num(pre, "maxAvgAddedDb"),
        "maxPeakAddedDb": num(pre, "maxPeakAddedDb"),
    }
    for key, value in extra(pre).items():
        if value is not None:
            meta[key] = value

    return {
        "meta": meta,
        "zones": res["zones"],
        "routes": routes_of(res, path),
        "travelTime": {
            "avg": num(pre, "avgTravelTimeWeighted"),
            "min": num(pre, "minTravelTime", int),
            "max": num(pre, "maxTravelTime", int),
        },
    }


def unavailable(combo, domain, mode_dir, stem):
    return {
        "unavailable": True,
        "reason": UNAVAILABLE_REASON,
        "budget": UNAVAILABLE_BUDGETS[(combo, domain, mode_dir, stem)],
    }


def cell(combo, domain, mode, stem, extra):
    """A leaf if the file exists, an explicit unavailability marker if not."""
    mode_dir = MODE_DIR[domain][mode]
    path = os.path.join(FR, combo, domain, mode_dir, stem + ".csv")
    key = (combo, domain, mode_dir, stem)
    if os.path.exists(path):
        assert key not in UNAVAILABLE_BUDGETS, f"{path} exists but is listed unavailable"
        return leaf(path, extra)
    assert key in UNAVAILABLE_BUDGETS, f"{path} missing and not a known-unavailable cell"
    return unavailable(*key)


# --------------------------------------------------------------------------
# per-domain meta
# --------------------------------------------------------------------------

def equal_extra(pre):
    return {
        "U": num(pre, "U"),
        "variant": pre.get("variant"),
        "fullFleetFeasible": flag(pre, "fullFleetFeasible"),
        "substituted": flag(pre, "substituted"),
        "solvedAs": pre.get("solvedAs"),
        "substitutionBasis": pre.get("substitutionBasis"),
    }


def utilitarian_extra(pre):
    return {"D_used": num(pre, "D"), "Drole": pre.get("Drole")}


def sufficientarian_extra(pre):
    return {
        "D_used": num(pre, "D"),
        "Dbinding": flag(pre, "Dbinding"),
        "variant": pre.get("variant"),
        "fullFleetFeasible": flag(pre, "fullFleetFeasible"),
        "phase2TimeoutMs": num(pre, "phase2TimeoutMs", int),
        "totalTransit": num(pre, "totalTransit", int),
    }


def prioritarian_extra(pre):
    return {
        "lens": pre.get("lens"),
        "lensSelector": pre.get("lensSelector"),
        "protected": stations(pre, "protectedStations"),
        "protectedNoise": num(pre, "protectedNoise"),
        "degenerate": flag(pre, "protectedNoiseDegenerate"),
        "routingForcedByT": flag(pre, "routingForcedByT"),
        "T_floor": num(pre, "T_floor", int),
        "T_max": num(pre, "T_max", int),
        "gainedFromCyo": stations(pre, "lensGainedFromCyo"),
        "frozenStations": stations(pre, "lensFrozenStations"),
        "gainedOnPath": stations(pre, "gainedOnPathStations"),
    }


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------

def build():
    data = {
        "equal": {}, "utilitarian": {}, "sufficientarian": {},
        "prioritarian": {}, "prioritarianCyo": {},
    }

    for combo in COMBOS:
        for domain in data:
            data[domain][combo] = {}

        for mode in MODES:
            # one file feeds both the avg and the peak reading of a solution
            data["equal"][combo][mode] = {
                u: cell(combo, "equal_allocation", mode, "U" + u, equal_extra)
                for u in ("3", "8", "18")
            }
            data["utilitarian"][combo][mode] = {
                "avg": cell(combo, "utilitarian", mode, "result", utilitarian_extra),
                "peak": cell(combo, "utilitarian_peak", mode, "result", utilitarian_extra),
            }
            data["sufficientarian"][combo][mode] = {
                d: cell(combo, "sufficientarian", mode, "D" + d, sufficientarian_extra)
                for d in ("3", "8", "18")
            }
            data["prioritarian"][combo][mode] = {
                lens: cell(combo, "prioritarian", mode, lens, prioritarian_extra)
                for lens in LENSES
            }

            # Once Create-Your-Own picks feed lens membership, protectedNoise == 0
            # no longer means "the lens did nothing" — it can equally mean the
            # solver rerouted off the protected set entirely, which is the
            # opposite. Classify against a routing that no lens constrained, so
            # the UI can tell a no-op from a success. (handoff section 5.5)
            reference = routing_signature(read_result(os.path.join(
                FR, combo, "prioritarian", mode, "people_of_color.csv")))

            cyo_dir = os.path.join(FR, combo, "prioritarian_cyo", mode)
            variants = {}
            for fname in sorted(os.listdir(cyo_dir)):
                if not fname.endswith(".csv"):
                    continue
                path = os.path.join(cyo_dir, fname)
                node = leaf(path, prioritarian_extra)
                same = routing_signature(read_result(path)) == reference
                pn = node["meta"].get("protectedNoise") or 0
                node["meta"]["effect"] = (
                    ("no-op" if same else "succeeded") if pn == 0
                    else ("forced" if same else "traded")
                )
                variants[fname[:-4]] = node
            data["prioritarianCyo"][combo][mode] = variants

    # selection code (st2 st6 st11 st13, each 0|1) -> combo, and per mode+lens
    # the prioritarian_cyo variant that answers it.
    selection = {}
    with open(os.path.join(DATA, "summaries", "cyo_selection_map.csv"), encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            code = row["cyoSelection"]
            entry = selection.setdefault(code, {"combo": row["combo"]})
            assert entry["combo"] == row["combo"], code
            variant = os.path.basename(row["file"])[:-4]
            entry.setdefault(row["mode"], {})[row["lens"]] = variant
            assert variant in data["prioritarianCyo"][row["combo"]][row["mode"]], variant

    data["cyoSelectionMap"] = selection

    # every one of the 16 selections must resolve for both modes and all lenses
    assert len(selection) == 16, len(selection)
    for code, entry in selection.items():
        for mode in MODES:
            assert sorted(entry[mode]) == sorted(LENSES), (code, mode)

    data["notes"] = {
        "dbPerCraft": 45,
        "maxTraffic": 56,
        "source": "dB45_collection/data/full_routes",
        "unavailableCount": sum(
            1 for domain in ("equal", "utilitarian", "sufficientarian")
            for combo in COMBOS for mode in MODES
            for v in data[domain][combo][mode].values()
            if isinstance(v, dict) and v.get("unavailable")
        ),
    }
    return data


def inject(blob):
    with open(HTML, "r", encoding="utf-8") as fh:
        html = fh.read()
    payload = "/*DATA-START*/" + blob + "/*DATA-END*/"
    pattern = re.compile(r"/\*DATA-START\*/.*?/\*DATA-END\*/", re.S)
    if pattern.search(html):
        html = pattern.sub(lambda _: payload, html, count=1)
    else:
        # first run: replace the old 55 dB literal wholesale
        old = re.compile(r"(const dashboardData = )(\{.*?\});\n", re.S)
        match = old.search(html)
        if not match:
            sys.exit("could not find `const dashboardData = {...};` to replace — "
                     "add /*DATA-START*/ /*DATA-END*/ markers manually")
        html = html[:match.start()] + f"const dashboardData = {payload};\n" + html[match.end():]
    with open(HTML, "w", encoding="utf-8") as fh:
        fh.write(html)


def main():
    data = build()
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, sort_keys=True)
    blob = json.dumps(data, separators=(",", ":"), sort_keys=True)
    inject(blob)
    print(f"wrote {OUT_JSON} ({os.path.getsize(OUT_JSON) / 1024:.0f} KB)")
    print(f"injected {len(blob) / 1024:.0f} KB into {os.path.basename(HTML)}")
    print(f"unavailable cells: {data['notes']['unavailableCount']} (expected 12)")


if __name__ == "__main__":
    main()
