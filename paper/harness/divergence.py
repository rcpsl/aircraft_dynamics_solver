"""The Phase-1 divergence check: do the five principles route differently enough?

The fleet-size study asks how each principle REACTS to a growing fleet. A setup where
all five return the same routing cannot answer that -- not because the principles are
alike, but because the setup gives them nowhere to differ. This module decides whether
a setup separates them, on a rule fixed in advance so the answer is not chosen after
seeing it.

    DIVERGENT ENOUGH  =  at least three of the five principles produce mutually
                         distinct routings (pairwise occupancy distance > 0)
                    AND  at least two headline metrics differ across the five by a
                         margin a reader can see on a plot:
                              >= 1 aircraft   in a count metric
                              >= 1 dB         in a noise metric
                              >= 0.25 hops    in a travel metric

Routings are compared by OCCUPANCY, not by path lists: relabelling two interchangeable
aircraft rewrites every path without changing the map anyone sees or the noise anyone
hears. Occupancy is invariant to that, and it is what the noise -- and therefore the
fairness -- actually depends on.

usage: python divergence.py <setup-name> <file.jsonl> [more.jsonl ...] [--N 16]
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import metrics as MX
import payload as P

RES = os.path.join(HERE, "results")
LOG = os.path.join(RES, "screen_log.md")
ORDER = ["equal", "sufficientarian", "prioritarian", "utilitarian", "proportional"]

# metric -> (label, kind). The kind fixes the threshold, so "visible on a plot" means
# the same thing for every metric of that kind.
HEADLINE = [
    ("max_count",             "max aircraft per tile",   "count"),
    ("shared_tile_timesteps", "shared tile-timesteps",   "count"),
    ("aircraft_in_shared",    "aircraft on a shared route", "count"),
    ("total_added",           "total added dB",          "noise"),
    ("peak_added",            "peak added dB",           "noise"),
    ("avg_trip_hops",         "avg trip hops",           "travel"),
]
THRESH = {"count": 1.0, "noise": 1.0, "travel": 0.25}


def load_rows(paths):
    rows = []
    for p in paths:
        p = p if os.path.isabs(p) else os.path.join(HERE, p)
        if not os.path.exists(p):
            continue
        for line in io.open(p, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            r["_file"] = os.path.basename(p)
            rows.append(r)
    return rows


CONDITION_NAMES = tuple(ORDER) + (
    "baseline",
    "prioritarian_off",                             # Prioritarian's ablation control
    "utilitarian_count", "proportional_count",      # the count-weighted encodings
    "utilitarian_db", "proportional_db",            # the decibel encodings (Exp. 5)
)


def principle_of(row):
    """The CONDITION a row measures -- which is not always its cfg principle.

    `baseline` is built from the Equal payload with the caps opened and the objectives
    off, and `prioritarian_off` from the Prioritarian payload with its objective
    cleared, so both report a cfg principle that is not the condition. The key is the
    only thing that distinguishes them.

    Scanned rather than taken from a fixed position: keys gained a `|p<k>` permutation
    suffix in session 3, which silently broke a `parts[-2]` lookup and made every cell
    in the setup screen read as "no cell".
    """
    parts = str(row.get("key", "")).split("|")
    for p in reversed(parts):
        if p in CONDITION_NAMES:
            return p
    return row.get("cfg", {}).get("principle")


def occupancy(row, req):
    """Aircraft-timesteps each community carries, as an M-vector."""
    counts, _ = MX.counts_from(row, req)
    if counts is None:
        return None
    return [sum(c) for c in counts]


def distance(a, b):
    """L1 between occupancy vectors, normalised by total flight time.

    0 = the same map; 1 = no community carries traffic in both.
    """
    denom = max(sum(a), sum(b)) or 1
    return sum(abs(x - y) for x, y in zip(a, b)) / (2 * denom)


def setup_of(row):
    """The setup a row was solved on. Rows written before the setup stamp existed
    (the Phase-1 pilot and its probes) are all default-setup, hence the fallback."""
    return (row.get("setup") or {}).get("name", "default")


def check(rows, N=None, setup=None):
    """Run the rule over ONE setup's rows. Returns a verdict dict.

    The setup filter is not optional in practice: screen.jsonl holds every screened
    setup in one file, and two setups' rows for the same principle are indistinguishable
    by key prefix alone. Without it a check silently mixes them -- which it did once,
    reporting the default setup's Utilitarian trip length under the slack-3 heading.
    """
    by = {}
    for r in rows:
        if not r.get("paths"):
            continue
        p = principle_of(r)
        if p is None:
            continue
        if N is not None and r.get("N") != N:
            continue
        if setup is not None and setup_of(r) != setup:
            continue
        # Prefer the stronger row if a condition somehow appears twice.
        cur = by.get(p)
        rank = {"optimal": 2, "partial": 1}.get(r.get("optimality"), 0)
        if cur is None or rank > cur[0]:
            by[p] = (rank, r)
    by = {p: r for p, (_, r) in by.items()}

    present = [p for p in ORDER if p in by]
    out = {"present": present, "have_baseline": "baseline" in by,
           "N": by[present[0]]["N"] if present else None}
    if len(present) < 2:
        out["pass"] = False
        out["why"] = f"only {len(present)} principle(s) have a routing"
        return out

    reqs = {p: MX._req_for(by[p]) for p in by}
    mets = {p: MX.derive(by[p], reqs[p]) for p in by}
    occ = {p: occupancy(by[p], reqs[p]) for p in present}

    # ---- (1) mutually distinct routings
    pair = {}
    for i, a in enumerate(present):
        for b in present[i + 1:]:
            pair[(a, b)] = distance(occ[a], occ[b])
    vals = list(pair.values())
    out["pair_min"] = min(vals)
    out["pair_mean"] = sum(vals) / len(vals)
    out["pairs"] = {f"{a}|{b}": round(v, 4) for (a, b), v in pair.items()}

    # The largest set of principles that are mutually distinct: a clique on
    # "distance > 0". Greedy over ORDER is exact enough here -- with five nodes the
    # relation is an equivalence (identical routings are transitively identical), so
    # one representative per distinct routing IS the maximum clique.
    reps = []
    for p in present:
        if all(pair.get((q, p), pair.get((p, q), 0)) > 0 for q in reps):
            reps.append(p)
    out["distinct_routings"] = len(reps)
    out["distinct_set"] = reps

    # ---- (2) headline metric spreads
    spreads = []
    for key, label, kind in HEADLINE:
        vs = []
        for p in present:
            v = mets[p].get(key)
            if key == "aircraft_in_shared":
                v = (mets[p].get("identical_routes") or {}).get("aircraft_in_shared")
            if v is not None:
                vs.append(float(v))
        if len(vs) < 2:
            continue
        sp = max(vs) - min(vs)
        spreads.append({"metric": key, "label": label, "kind": kind,
                        "spread": round(sp, 4), "threshold": THRESH[kind],
                        "visible": sp >= THRESH[kind],
                        "values": {p: mets[p].get(key) if key != "aircraft_in_shared"
                                   else (mets[p].get("identical_routes") or {}).get("aircraft_in_shared")
                                   for p in present}})
    out["spreads"] = spreads
    out["visible_metrics"] = sum(1 for s in spreads if s["visible"])

    out["pass"] = out["distinct_routings"] >= 3 and out["visible_metrics"] >= 2
    out["why"] = (f"{out['distinct_routings']} distinct routing(s), "
                  f"{out['visible_metrics']} metric(s) visibly spread")
    out["metrics"] = mets
    out["statuses"] = {p: (by[p].get("optimality") or by[p].get("status")) for p in by}
    out["is_probe"] = {p: bool(by[p].get("budget_s") and by[p]["budget_s"] < 100000)
                       for p in by}
    return out


def report(name, v, extra=""):
    """One block for screen_log.md, and the same thing on stdout."""
    L = []
    L.append(f"\n### {name}   N={v.get('N')}   ->  "
             f"**{'PASS' if v.get('pass') else 'FAIL'}**")
    if extra:
        L.append(f"\n{extra}")
    L.append(f"\n{v.get('why')}.")
    if "pair_min" in v:
        L.append(f"Pairwise occupancy distance: min {v['pair_min']:.3f}, "
                 f"mean {v['pair_mean']:.3f}. "
                 f"Distinct routings: {v['distinct_routings']}/{len(v['present'])} "
                 f"({', '.join(v['distinct_set'])}).")
        L.append("")
        L.append("| metric | " + " | ".join(p[:6] for p in v["present"]) +
                 " | spread | visible |")
        L.append("|---" * (len(v["present"]) + 3) + "|")
        for s in v["spreads"]:
            cells = []
            for p in v["present"]:
                x = s["values"].get(p)
                cells.append("--" if x is None else
                             (f"{x:.2f}" if isinstance(x, float) else str(x)))
            L.append(f"| {s['label']} | " + " | ".join(cells) +
                     f" | {s['spread']:.2f} | {'yes' if s['visible'] else 'no'} |")
        L.append("")
        st = ", ".join(f"{p}={v['statuses'].get(p)}"
                       + (" (probe)" if v["is_probe"].get(p) else "")
                       for p in v["present"])
        L.append(f"Status: {st}")
        if not v.get("have_baseline"):
            L.append("_No baseline row at this N; travel cost is against the "
                     "shortest-path floor only._")
    txt = "\n".join(L)
    print(txt)
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write(txt + "\n")
    return txt


def main(argv):
    name = argv[0]
    files = [a for a in argv[1:] if not a.startswith("--")]
    N = None
    if "--N" in argv:
        N = int(argv[argv.index("--N") + 1])
    setup = argv[argv.index("--setup") + 1] if "--setup" in argv else None
    rows = load_rows(files)
    v = check(rows, N, setup)
    v["setup"] = setup
    report(name, v, extra=(f"Setup filter: `{setup}`." if setup else
                           "_No setup filter; rows from every setup in these files "
                           "are pooled._"))
    return 0 if v.get("pass") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
