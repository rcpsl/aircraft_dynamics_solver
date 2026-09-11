"""Does the choice of fairness principle change performance? Three metrics, one answer each.

The fleet ladder measures every condition on the same instance, so the honest way to
report it is one question per performance family, asked the same way each time:

    CONGESTION   how hard does the busiest community get hit at once?
    TRAVEL TIME  how much longer does the fleet fly than it has to?
    ADDED NOISE  how much noise is created, and who carries the peak?

For each, the question is the same: across the conditions solved at one fleet size, is
the SPREAD between them large enough that a reader could act on it? A spread of zero is
a result, not a gap in the data -- but only once you have shown what does move the metric,
which is why `lever()` reports the same three families under the slack and cap sweeps.

Two rules the module keeps to, both learned from this project's retraction record:

  * Only PROVEN cells are compared. A stopped search pays a worse arrival penalty
    simply for having been stopped, so an unproven row manufactures exactly the
    travel-time difference this analysis exists to look for. Unproven rows are counted
    and named, never mixed in.
  * Spread is reported with the condition names at each end, so "1.76 dB" is always
    traceable to which two principles produced it.

usage: python compare.py            # -> results/comparison.md, and stdout
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RES = os.path.join(HERE, "results")
OUT = os.path.join(RES, "comparison.md")

CONDS = ["equal", "sufficientarian", "prioritarian", "utilitarian", "proportional",
         "baseline"]
LABEL = {"equal": "Equal", "sufficientarian": "Sufficientarian",
         "prioritarian": "Prioritarian", "utilitarian": "Utilitarian",
         "proportional": "Proportional", "baseline": "Baseline"}

# family -> (metric, printed name, unit, "visible on a plot" threshold, decimals)
# Thresholds are the ones fixed before the fleet sweep ran (divergence.py): one whole
# aircraft, one decibel, a quarter of a hop.
FAMILIES = {
    "congestion": [
        ("max_count", "peak aircraft over one community", "aircraft", 1.0, 0),
        ("shared_tile_timesteps", "tile-timesteps carrying 2+", "t-steps", 1.0, 0),
        ("stations_touched", "communities overflown", "of 25", 1.0, 0),
    ],
    "travel time": [
        ("extra_vs_floor", "fleet hops above the shortest-path floor", "hops", 1.0, 0),
        ("avg_trip_hops", "mean trip length", "hops", 0.25, 2),
        ("arrivalPenalty", "arrival penalty", "ac-timesteps", 1.0, 0),
        ("departure_delay_total", "aircraft-timesteps spent waiting to depart",
         "ac-timesteps", 1.0, 0),
    ],
    "added noise": [
        ("peak_added", "worst added level at any community", "dB", 1.0, 2),
        ("total_added", "added noise summed over all communities", "dB", 1.0, 1),
        ("tier45", "share of flight time over 45 dBA communities", "%", 1.0, 1),
    ],
}


def val(m, f):
    if f == "tier45":
        return (m.get("tier_share") or {}).get("45")
    return m.get(f)


def load(path="fleet_metrics.json"):
    p = os.path.join(RES, path)
    if not os.path.exists(p):
        return []
    return [m for m in json.load(io.open(p, encoding="utf-8")) if not m.get("probe")]


def spread(rows, f):
    """(lo_label, lo, hi_label, hi, hi-lo) over rows that carry the metric."""
    got = [(m, val(m, f)) for m in rows]
    got = [(m, v) for m, v in got if v is not None]
    if len(got) < 2:
        return None
    lo = min(got, key=lambda g: g[1])
    hi = max(got, key=lambda g: g[1])
    return (LABEL.get(lo[0]["condition"], "?"), lo[1],
            LABEL.get(hi[0]["condition"], "?"), hi[1], hi[1] - lo[1])


def by_size(recs, proven_only=True):
    """{N: [rows]} — proven cells only unless told otherwise."""
    out = {}
    for m in recs:
        if proven_only and m.get("optimality") != "optimal":
            continue
        out.setdefault(m["N"], []).append(m)
    return {n: sorted(v, key=lambda m: CONDS.index(m["condition"])
                      if m["condition"] in CONDS else 99)
            for n, v in sorted(out.items())}


def verdict(recs, L):
    """The headline: for each family, does the principle change performance?"""
    sizes = by_size(recs)
    dropped = [m for m in recs if m.get("optimality") != "optimal"]

    L.append("## Does the choice of principle change performance?\n")
    L.append("Spread across the conditions **proven optimal** at each fleet size. "
             "\"Visible spread\" means only that the difference is large enough to see "
             "on a plot. **It is not yet a claim about the principle** &mdash; the "
             "next section measures how large a difference has to be before it is "
             "evidence, and most of these do not reach it. A metric flat at zero "
             "everywhere is the one case that needs no such test.\n")
    if dropped:
        L.append(f"_{len(dropped)} unproven cell(s) excluded: "
                 + ", ".join(sorted(f"{LABEL.get(m['condition'],m['condition'])} N={m['N']}"
                                    for m in dropped))
                 + ". A stopped search pays a worse arrival penalty for having been "
                   "stopped, which would manufacture exactly the travel-time "
                   "difference this table looks for._\n")

    for fam, metrics in FAMILIES.items():
        L.append(f"\n### {fam.title()}\n")
        L.append("| metric | " + " | ".join(f"N={n}" for n in sizes)
                 + " | verdict |")
        L.append("|---" * (len(sizes) + 2) + "|")
        for f, name, unit, thr, nd in metrics:
            cells, best = [], 0.0
            for n, rows in sizes.items():
                s = spread(rows, f)
                if s is None:
                    cells.append("--")
                    continue
                cells.append(f"{s[4]:.{nd}f}")
                best = max(best, abs(s[4]))
            # "Separates" here means only "bigger than a reader could see on a plot".
            # Whether it is evidence about the PRINCIPLE is a separate question, and
            # the section below answers it -- for most of these metrics, in the
            # negative. The wording says so rather than letting the reader carry a
            # verdict forward that the next table withdraws.
            mark = ("visible spread" if best >= thr else "no difference")
            L.append(f"| {name} ({unit}) | " + " | ".join(cells)
                     + f" | {mark} |")
        L.append("")
        # Who sits at each end, at the largest size where the family separates.
        for f, name, unit, thr, nd in metrics:
            hits = [(n, spread(rows, f)) for n, rows in sizes.items()]
            hits = [(n, s) for n, s in hits if s and abs(s[4]) >= thr]
            if not hits:
                continue
            n, s = hits[-1]
            L.append(f"- At N={n}, **{name}** runs {s[1]:.{nd}f} ({s[0]}) to "
                     f"{s[3]:.{nd}f} ({s[2]}) — a spread of {s[4]:.{nd}f} {unit}.")
        L.append("")


def sensitivity(L):
    """How large must a difference be before it is a difference?

    The slack sweep turns out to measure something more useful than the travel time it
    was built for. Across slack 1 to 4, every cap-based condition attains the SAME
    arrival penalty -- 22 at N=8, 44 at N=16, at every horizon -- because arrival is
    the only quantity they optimise and the horizon does not change its optimum. Yet
    the routing returned differs, and with it the noise and the congestion.

    That variation is not the principle doing anything. It is the solver picking
    among routings it is indifferent between, with the choice falling out of an
    incidental parameter. It therefore sets a NOISE FLOOR: any between-condition
    difference smaller than it cannot be attributed to the condition.

    The check is fair for all four:
      * Equal and Sufficientarian carry no objective at all, so nothing about a wider
        horizon should improve them, and arrival confirms nothing does.
      * Prioritarian carries one, but its `protectedNoise` is 0.0 at every slack and
        every fleet size -- the objective is satisfied for free, so it pins nothing.
      * The baseline is the control and wanders the most of the four.
    """
    import metrics_run as MR
    try:
        sl = [m for m in MR.build(["results/slack.jsonl"])
              if m.get("optimality") == "optimal"]
    except Exception as e:
        L.append(f"\n## Noise floor\n\n_[slack sweep unreadable: {e}]_\n")
        return
    for m in sl:
        m["_x"] = (m.get("setup") or {}).get("slack")
    sl = [m for m in sl if m.get("_x") is not None]
    if not sl:
        L.append("\n## Noise floor\n\n_Slack sweep not on disk yet._\n")
        return

    fleet = {(m["condition"], m["N"]): m for m in load()
             if m.get("optimality") == "optimal"}
    C = ["baseline", "equal", "sufficientarian", "prioritarian"]
    METRICS = [("max_count", "max aircraft over one community", 0),
               ("shared_tile_timesteps", "tile-timesteps carrying 2+", 0),
               ("peak_added", "peak added noise (dB)", 2),
               ("total_added", "total added noise (dB)", 1),
               ("tier45", "share of flight time over 45 dBA (%)", 1),
               ("extra_vs_floor", "extra hops above the floor", 0),
               ("departure_delay_total", "departure delay (ac-timesteps)", 0)]

    L.append("\n## How large must a difference be before it is a difference?\n")
    L.append("For each metric: the range one **single condition** covers when only the "
             "horizon moves — an incidental parameter that provably leaves its arrival "
             "optimum untouched — against the spread **between conditions** at the "
             "default horizon. A between-condition difference smaller than the "
             "within-condition range is not evidence about the condition.\n")

    allx = sorted({m["_x"] for m in sl})
    for n in sorted({m["N"] for m in sl} & {k[1] for k in fleet}):
        # A floor measured over fewer horizons is an underestimate, which would inflate
        # the comparison and make a difference read as attributable when it is not.
        missing = [(c, x) for c in C for x in allx
                   if not any(m["condition"] == c and m["N"] == n and m["_x"] == x
                              for m in sl)]
        if missing:
            L.append(f"\n**N = {n}** — floor not yet complete "
                     f"({len(missing)} of {len(C)*len(allx)} cells missing); "
                     "omitted rather than reported as an underestimate.\n")
            continue
        arr = sorted({m["arrivalPenalty"] for m in sl if m["N"] == n
                      and m["condition"] in C})
        L.append(f"\n**N = {n}** — arrival penalty is {arr[0] if len(arr)==1 else arr} "
                 f"at every horizon and for every condition, so nothing any of these "
                 f"four optimises is improving.\n")
        L.append("| metric | arbitrary (one condition, horizon 1-4) | "
                 "between conditions (default horizon) | verdict |")
        L.append("|---|---|---|---|")
        for f, lab, nd in METRICS:
            w = 0.0
            for c in C:
                v = [val(m, f) for m in sl if m["condition"] == c and m["N"] == n]
                v = [x for x in v if x is not None]
                if len(v) > 1:
                    w = max(w, max(v) - min(v))
            got = [val(fleet[(c, n)], f) for c in C if (c, n) in fleet
                   and val(fleet[(c, n)], f) is not None]
            b = (max(got) - min(got)) if len(got) > 1 else 0.0
            if b == 0 and w == 0:
                verd = "no difference either way"
            elif b > w:
                verd = "**attributable**"
            else:
                verd = "**below the floor** — not evidence"
            L.append(f"| {lab} | {w:.{nd}f} | {b:.{nd}f} | {verd} |")
        L.append("")


def perm_floor(L):
    """The floor again, with the one confound the slack instrument still carries removed.

    Widening the horizon enlarges the feasible set, so a sceptic can say a condition
    might genuinely have done better in the larger space -- even though arrival says
    none of them did. Permuting the aircraft list removes that objection completely:
    relabelling which aircraft is listed first leaves the same origin-destination pairs,
    the same fleet and the same feasible set. Every routing available before is
    available after, and the optimum is the same routing under a different name.

    So whatever range the permutations cover is the tie-break with nothing else in it.
    Z3's search order follows the order its variables are created, which follows the
    order the aircraft arrive in, so the permutations do land on different members of
    the optimal set -- which is the finding, not an artefact.
    """
    import metrics_run as MR
    try:
        pm = [m for m in MR.build(["results/perm.jsonl"])
              if m.get("optimality") == "optimal"]
    except Exception:
        pm = []
    if not pm:
        L.append("\n## The floor, measured a second way\n\n"
                 "_Permutation sweep not on disk yet._\n")
        return
    for m in pm:
        try:
            m["_seed"] = int(str(m["key"]).split("|")[1])
        except (IndexError, ValueError):
            m["_seed"] = None

    fleet = {(m["condition"], m["N"]): m for m in load()
             if m.get("optimality") == "optimal"}
    C = ["baseline", "equal", "sufficientarian", "prioritarian"]
    METRICS = [("max_count", "max aircraft over one community", 0),
               ("peak_added", "peak added noise (dB)", 2),
               ("total_added", "total added noise (dB)", 1),
               ("extra_vs_floor", "extra hops above the floor", 0),
               ("arrivalPenalty", "arrival penalty", 0)]

    L.append("\n## The floor, measured a second way: permute the aircraft\n")
    L.append("Same fleet, same origin&ndash;destination pairs, same feasible set &mdash; "
             "only the order the aircraft are listed in changes. Any difference in what "
             "comes back is the tie-break with no confound at all.\n")
    for n in sorted({m["N"] for m in pm}):
        seeds = sorted({m["_seed"] for m in pm if m["N"] == n})
        L.append(f"\n**N = {n}**, {len(seeds)} orderings.\n")
        L.append("| metric | range over orderings (one condition) | "
                 "between conditions | verdict |")
        L.append("|---|---|---|---|")
        for f, lab, nd in METRICS:
            w = 0.0
            for c in C:
                v = [val(m, f) for m in pm if m["condition"] == c and m["N"] == n]
                v = [x for x in v if x is not None]
                if len(v) > 1:
                    w = max(w, max(v) - min(v))
            got = [val(fleet[(c, n)], f) for c in C if (c, n) in fleet
                   and val(fleet[(c, n)], f) is not None]
            b = (max(got) - min(got)) if len(got) > 1 else 0.0
            if b == 0 and w == 0:
                verd = "invariant"
            elif b > w:
                verd = "**attributable**"
            else:
                verd = "**below the floor**"
            L.append(f"| {lab} | {w:.{nd}f} | {b:.{nd}f} | {verd} |")
        L.append("")


def lever(recs, L, name, xfield, xlabel, note):
    """The same three families, but against a SETUP knob instead of fleet size.

    This is what a flat metric needs: not an argument that it should have moved, but
    a second sweep in which it does.
    """
    if not recs:
        L.append(f"\n## {name}\n\n_No rows on disk yet._\n")
        return
    L.append(f"\n## {name}\n")
    L.append(note + "\n")
    xs = sorted({m[xfield] for m in recs if m.get(xfield) is not None})
    conds = [c for c in CONDS if any(m["condition"] == c for m in recs)]

    for fam, metrics in FAMILIES.items():
        f, mname, unit, thr, nd = metrics[0]
        L.append(f"\n**{fam.title()} — {mname} ({unit})**\n")
        L.append(f"| condition | " + " | ".join(f"{xlabel}={x}" for x in xs) + " |")
        L.append("|---" * (len(xs) + 1) + "|")
        for c in conds:
            cells = []
            for x in xs:
                rows = [m for m in recs if m["condition"] == c and m.get(xfield) == x
                        and m.get("optimality") == "optimal"]
                v = val(rows[0], f) if rows else None
                cells.append("--" if v is None else f"{v:.{nd}f}")
            L.append(f"| {LABEL.get(c, c)} | " + " | ".join(cells) + " |")
        L.append("")


def slack_rows():
    """Proven slack-sweep rows, with `slack` promoted to a top-level field."""
    import metrics_run as MR
    recs = MR.build(["results/slack.jsonl"])
    for m in recs:
        m["slack"] = (m.get("setup") or {}).get("slack", m.get("slack"))
    return recs


def cap_rows():
    import metrics_run as MR
    recs = MR.build(["results/captight.jsonl"])
    for m in recs:
        m["limit"] = (m.get("setup") or {}).get("limit")
    return recs


def main():
    L = ["# Performance against principle: what changes, and what does not", "",
         "Generated by `paper/harness/compare.py`. Every figure is read from a solve "
         "recorded in `results/`; nothing here is typed in by hand.", ""]

    recs = load()
    if not recs:
        L.append("_No fleet rows on disk._")
    else:
        verdict(recs, L)
        sensitivity(L)
        perm_floor(L)

    try:
        sr = slack_rows()
    except Exception as e:
        sr = []
        L.append(f"\n_[slack sweep unreadable: {type(e).__name__}: {e}]_\n")
    lever(sr, L, "Lever 1 — horizon slack", "slack", "slack",
          "The tool sends `T_max` = Chebyshev floor + 1, which is barely a timestep of "
          "room to detour into. If travel time is flat because no condition *can* "
          "detour, widening the horizon should separate the conditions that would "
          "spend it from the conditions that would not. Unlimited budget, so a zero "
          "here means the principle **declined** the room rather than ran out of clock.")

    try:
        cr = cap_rows()
    except Exception as e:
        cr = []
        L.append(f"\n_[cap sweep unreadable: {type(e).__name__}: {e}]_\n")
    lever(cr, L, "Lever 2 — cap tightness", "limit", "D",
          "Horizon slack acts on the two principles carrying an objective. The cap-based "
          "principles need the other lever: a cap that actually binds forces traffic off "
          "full tiles, and routing around them is the only way. Equal and Sufficientarian "
          "only, since the other conditions send the wide cap by construction and have "
          "nothing to tighten.")

    io.open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    print("\n".join(L))
    print("\nwrote", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
