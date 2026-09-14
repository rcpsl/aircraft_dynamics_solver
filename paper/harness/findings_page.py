"""Regenerate the figure-and-metrics block of ../session3_findings.html.

The page is hand-written prose everywhere else; only the region between the
`<!--BEGIN:map-->` and `<!--END:map-->` sentinels is machine-made, because it is the
part that has to agree with `results/fleet_main_metrics.json` cell for cell. Hand-copying
48 cells x 8 metrics out of the index is exactly how the retracted claims got written, so
this reads the index instead.

The two figures are inlined as base64 data URIs: an Artifact page is a single file and
the published sandbox will not fetch an image from any host, so a `<img src="figs/...">`
would render as a broken box.

usage: python findings_page.py           # rewrite the block in place
       python findings_page.py --check   # non-zero exit if the block is out of date
"""
import base64
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
FIGS = os.path.join(HERE, "..", "tex", "figs")
PAGE = os.path.join(HERE, "..", "session3_findings.html")
BEGIN, END = "<!--BEGIN:map-->", "<!--END:map-->"

LADDER = (6, 8, 14, 16, 22, 24, 30, 32)
ORDER = [("equal", "Equal"), ("sufficientarian", "Sufficientarian"),
         ("prioritarian", "Prioritarian"), ("utilitarian", "Utilitarian"),
         ("proportional", "Proportional"), ("baseline", "Baseline")]

# (field, column head, decimals). `extra_vs_baseline` is signed against the no-fairness
# condition at the same N, so the baseline's own row is 0 by construction and is blanked.
METRICS = [
    ("peak_added",            "peak dB",        2),
    ("total_added",           "total dB",       1),
    ("max_count",             "max/tile",       0),
    ("shared_tile_timesteps", "shared t-steps", 0),
    ("avg_trip_hops",         "avg hops",       2),
    ("extra_vs_baseline",     "extra hops",     2),
    ("departure_delay_total", "dep. delay",     0),
]

# The head-to-head columns. `extra_vs_baseline` is already a difference from the
# baseline, so it is shown as itself, not differenced again; every other column is
# principle minus baseline at the same fleet size.
COMPARE = [
    ("peak_added",              "peak dB",        2, "peak added noise"),
    ("total_added",             "total dB",       1, "total added noise"),
    ("max_count",               "max/tile",       2, "peak occupancy"),
    ("occupied_tile_timesteps", "tiles used",     2, "tile-timesteps occupied"),
    ("shared_tile_timesteps",   "shared t-steps", 2, "shared tile-timesteps"),
    ("avg_trip_hops",           "avg hops",       2, "average trip length"),
    ("extra_vs_baseline",       "extra hops",     2, "extra fleet hops"),
    ("departure_delay_total",   "dep. delay",     1, "departure delay"),
]
ALREADY_RELATIVE = {"extra_vs_baseline"}

# One line per principle, written against the numbers the table below it prints. The
# claim in each is the one the attributability test actually licenses -- no principle
# gets credit here for a difference that sits inside the permutation band.
KICKER = {
    "equal": ("A cap on any one community&rsquo;s level. Nothing separates it from the "
              "baseline until the cap binds, and then it buys 1.93&nbsp;dB off the peak "
              "for 2.75 extra fleet-hops."),
    "sufficientarian": ("The same absolute cap, at a threshold rather than an equality. "
                        "It makes the same trade as Equal and pays the most distance for "
                        "it &mdash; and it is the one cap that survives past "
                        "N&nbsp;=&nbsp;24."),
    "prioritarian": ("Weights the worst-off communities first, and empties them "
                     "completely: its objective is zero at every fleet size, in every "
                     "ordering. It is also the only cap that lowers total added noise "
                     "attributably <i>before</i> its cap binds, and later it buys the "
                     "same quieter peak for the least distance of the three."),
    "utilitarian": ("Minimises fleet transit time &mdash; and the baseline already "
                    "minimises it, exactly, at every size. The objective is inert, so "
                    "what this condition returns is a tie-break; it still buys a quieter "
                    "peak, and pays for it in departure delay rather than distance."),
    "proportional": ("Burden follows benefit, by proximity ring. It is the only condition "
                     "that beats the baseline on total added noise at every proven size, "
                     "and it does it by concentrating traffic rather than spreading it."),
}


def load():
    p = os.path.join(RES, "fleet_main_metrics.json")
    recs = [m for m in json.load(io.open(p, encoding="utf-8")) if not m.get("probe")]
    return {(m["condition"], m["N"]): m for m in recs}


def load_objectives():
    """Each principle's objective scored on every condition's routing, banded like a metric.

    The solver only reports the objective the run optimised, so the baseline carries no
    score at all for any of them; these are rebuilt from the stored matrices by
    objectives.py, which self-tests against the values the solver DID report. The band
    is taken over proven runs only, on the same rule metrics_run.aggregate uses -- a
    stopped search is not a sample from the optimal set.
    """
    import metrics as MX
    import objectives as OB
    rows = OB._rows()
    prot, weights = OB.reference(rows)
    by = {}
    for x in rows:
        # A phase-2 failure carries phase 1's unweighted route, or no route at all, so
        # it is not this condition's answer and is dropped here the same way
        # metrics_run drops it from the metrics index.
        if x.get("probe") or "paths" not in x or str(x.get("status", "")).startswith(
                "phase2_failed"):
            continue
        cond = x["key"].split("|")[2]
        vals = OB.evaluate(x, MX._req_for(x), prot=prot, weights=weights)
        vals["transit_time"] = vals["transit_time"]        # already unscaled
        by.setdefault((cond, x["N"]), []).append(
            (x.get("optimality") == "optimal", vals))
    out = {}
    for k, runs in by.items():
        proven = [v for ok, v in runs if ok]
        cell = {"all_proven": len(proven) == len(runs) and len(runs) > 0}
        for f in ("protected_noise", "transit_time", "proximity_cost"):
            got = [v[f] for v in (proven or []) if v[f] is not None]
            if not got:
                continue
            cell[f] = sum(got) / len(got)
            cell[f + "_min"], cell[f + "_max"] = min(got), max(got)
            cell["floor_" + f] = max(got) - min(got)
        out[k] = cell
    return out, prot


def img(stem, alt):
    p = os.path.join(FIGS, stem + ".png")
    b64 = base64.b64encode(io.open(p, "rb").read()).decode("ascii")
    return f'<img src="data:image/png;base64,{b64}" alt="{alt}">'


def num(m, field, dp, mark_zero=True):
    """Mean over the four orderings, with the permutation band when it is non-zero.

    A zero band is the finding, not a rounding artefact, so it is marked rather than
    left blank: it says every ordering returned the same value for this metric. It is
    only marked where some other condition at the same size did disagree with itself,
    though -- where the whole column is zero the metric simply does not vary with the
    ordering, and colouring all six green would say something the data does not.
    """
    v = m.get(field)
    if v is None:
        return "&mdash;"
    lo, hi = m.get(field + "_min"), m.get(field + "_max")
    cell = f"{v:.{dp}f}"
    if lo is None or hi is None or not m.get("all_proven"):
        return cell
    if abs(hi - lo) < 5e-9:
        return f'<span class="zero">{cell}</span>' if mark_zero else cell
    return f'{cell}<span class="band"> {lo:.{dp}f}&ndash;{hi:.{dp}f}</span>'


def varies(I, n, field):
    """Did any condition at this fleet size return a non-zero band on this metric?"""
    return any(abs(m.get(field + "_max", 0) - m.get(field + "_min", 0)) > 5e-9
               for m in (I.get((k, n)) for k, _ in ORDER)
               if m is not None and m.get("all_proven"))


def status_pill(m):
    if m.get("all_proven"):
        return '<span class="pill ok">proven 4/4</span>'
    k = m.get("runs_proven") or 0
    return f'<span class="pill no">harvested {k}/{m.get("runs", 4)}</span>'


def metrics_table(I):
    head = "".join(f"<th>{h}</th>" for _, h, _ in METRICS)
    rows = []
    for n in LADDER:
        rows.append(f'<tr class="grp"><td colspan="{len(METRICS) + 3}">'
                    f'<b>N = {n}</b> aircraft</td></tr>')
        for key, label in ORDER:
            m = I.get((key, n))
            if m is None:
                rows.append(f'<tr><td class="name">{label}</td>'
                            f'<td colspan="{len(METRICS) + 2}" class="absent">'
                            f'no verified routing in four orderings</td></tr>')
                continue
            cells = []
            for field, _, dp in METRICS:
                if field == "extra_vs_baseline" and key == "baseline":
                    cells.append("<td></td>")
                else:
                    cells.append(f"<td>{num(m, field, dp, varies(I, n, field))}</td>")
            rows.append(f'<tr><td class="name">{label}</td>{"".join(cells)}'
                        f'<td>{m["wall"]:,.0f}</td><td>{status_pill(m)}</td></tr>')
    return (f'<div class="scroll"><table>\n'
            f'<caption>Every cell of the ladder: means over four aircraft orderings, '
            f'with the permutation band beside the mean where the orderings disagreed. '
            f'A value in green has a band of exactly zero where some other condition at '
            f'the same size did vary &mdash; all four orderings returned it, and the '
            f'ordering was free to matter. Harvested cells were stopped at the '
            f'one-hour horizon and '
            f'carry a verified incumbent, not a proved optimum; their travel-time '
            f'figures include the cost of having been stopped, so they bound the '
            f'principle rather than stating it. Wall time is the mean seconds per '
            f'solve, unlimited Z3 budget.</caption>\n'
            f'<thead><tr><th>condition</th>{head}<th>wall s</th><th>status</th></tr>'
            f'</thead>\n<tbody>\n' + "\n".join(rows) + '\n</tbody></table></div>')


def panel_table(I):
    """The routing-grid panel titles, reproduced as text for every size on the ladder."""
    heads = "".join(f"<th>N = {n}</th>" for n in LADDER)
    rows = []
    for key, label in ORDER:
        cells = []
        for n in LADDER:
            m = I.get((key, n))
            if m is None:
                cells.append('<td class="absent">&mdash;</td>')
                continue
            dag = "" if m.get("all_proven") else "<sup>&dagger;</sup>"
            cls = ' class="zero"' if (m.get("all_proven")
                                      and abs(m["floor_peak_added"]) < 1e-9) else ""
            cells.append(f'<td{cls}>{m["peak_added"]:.2f} / +{m["extra_vs_floor"]:g}'
                         f'{dag}</td>')
        rows.append(f'<tr><td class="name">{label}</td>{"".join(cells)}</tr>')
    return (f'<div class="scroll"><table>\n'
            f'<caption>The two numbers in each panel title above: peak added noise in '
            f'decibels, and fleet hops above the shortest-path floor. Green marks a '
            f'peak that all four orderings agreed on. A dagger marks a cell harvested '
            f'at the horizon.</caption>\n'
            f'<thead><tr><th>condition</th>{heads}</tr></thead>\n<tbody>\n'
            + "\n".join(rows) + '\n</tbody></table></div>')


def delta(I, cond, n, field, dp):
    """principle minus baseline at one cell, marked when it clears the indifference floor.

    `attributable` returns None, not False, when either side has no band -- a harvested
    cell is not a sample from the optimal set, so the test cannot be run rather than
    failing. That third state is drawn as its own thing; collapsing it into "no
    difference" would claim the comparison was made.
    """
    import metrics_run as MR
    a, b = I.get((cond, n)), I.get(("baseline", n))
    if a is None or b is None or a.get(field) is None:
        return '<td class="absent">&mdash;</td>', None
    d = a[field] if field in ALREADY_RELATIVE else a[field] - b[field]
    att = MR.attributable(a, b, field)
    # round first, then add zero: IEEE 754 turns -0.0 + 0.0 into +0.0, which stops a
    # difference of exactly nothing printing as "-0.0" and reading as a small loss.
    txt = f"{round(d, dp) + 0.0:+.{dp}f}"
    if att:
        return f'<td class="att">{txt}</td>', True
    if att is None:
        return f'<td class="dim">{txt}<sup>&dagger;</sup></td>', None
    return f'<td class="dim">{txt}</td>', False


def verdict(hits):
    """Prose from the attributable set: what cleared the floor, on what, and where."""
    if not hits:
        return ("Nothing this principle did to the routing clears the indifference floor "
                "at any fleet size on the ladder.")
    order = [f for f, _, _, _ in COMPARE]
    names = dict((f, nm) for f, _, _, nm in COMPARE)
    parts = []
    for f in order:
        ns = sorted(hits.get(f, []))
        if ns:
            sizes = ", ".join(str(n) for n in ns)
            parts.append(f"<b>{names[f]}</b> at <i>N</i>&nbsp;=&nbsp;{sizes}")
    return ("Clears the indifference floor against the baseline on "
            + "; ".join(parts) + ". Every other difference in the table sits inside the "
            "permutation band and is not something the principle did.")


OBJ_INTRO = {
    "equal": ("Equal is not an objective at all &mdash; it is a hard cap, so there is no "
              "score to minimise and the question is only whether the cap binds. "
              "Utilisation is the busiest tile&rsquo;s occupancy as a fraction of what "
              "<i>D</i>&nbsp;=&nbsp;6 allows it: 2 aircraft over a 45&nbsp;dBA "
              "community, 29 over a 55, 298 over a 65. At 1.00 the cap is the thing "
              "deciding the routing; the baseline runs at 0.00 because its cap is wide "
              "enough never to be reached."),
    "sufficientarian": ("Also a hard cap rather than an objective, at a sufficiency "
                        "threshold rather than an equality. Above N&nbsp;=&nbsp;25 the "
                        "tool switches Equal to a <i>disparity</i> cap while "
                        "Sufficientarian keeps sending the absolute one, which is why "
                        "this column still has answers at N&nbsp;=&nbsp;30 and 32 where "
                        "Equal has none."),
    "prioritarian": ("Prioritarian minimises the added noise summed over the three "
                     "protected communities across every timestep &mdash; stations 4, 8 "
                     "and 14, outlined on the maps above. The baseline optimises nothing "
                     "and is scored here on the same quantity, so the two columns are "
                     "the same objective evaluated on two routings."),
    "utilitarian": ("Utilitarian in count form minimises total fleet transit time: the "
                    "aircraft-timesteps between an aircraft&rsquo;s first move and its "
                    "arrival, summed over the fleet. The baseline is scored on the same "
                    "quantity."),
    "proportional": ("Proportional minimises occupancy priced by proximity ring &mdash; "
                     "every aircraft-timestep over a community costs that "
                     "community&rsquo;s weight, so burden is pushed toward the "
                     "communities the service benefits. The baseline is scored on the "
                     "same weights."),
}


# What the objective table above it actually showed. Written against the numbers, and
# in one case against the author's preferred story: Utilitarian's objective turns out to
# be inert, and saying so is the point of scoring the baseline on it at all.
OBJ_NOTE = {
    "equal": ("The cap goes from slack to binding between N&nbsp;=&nbsp;8 and "
              "N&nbsp;=&nbsp;14, and everything this principle does to the routing "
              "happens after that. Below it the cap is a constraint the routing was "
              "never going to violate, and Equal and the baseline are the same "
              "condition wearing different labels."),
    "sufficientarian": ("Binding from N&nbsp;=&nbsp;14 and still binding at "
                        "N&nbsp;=&nbsp;30 and 32, where Equal has no verified routing "
                        "at all. The absolute cap is the more tractable of the two "
                        "encodings at the top of the ladder, not the more demanding."),
    "prioritarian": ("<b>The objective is driven to exactly zero at every fleet size, in "
                     "all four orderings.</b> Not low &mdash; zero: no aircraft is ever "
                     "over a protected community, at any timestep, at any size on the "
                     "ladder. The baseline puts 2.2 to 11.0&nbsp;dB on the same three "
                     "communities and swings by up to 16.8 depending on nothing but "
                     "aircraft ordering. Two of the six sizes clear the indifference "
                     "floor; the other four miss only because the baseline&rsquo;s own "
                     "band is wider than the gap, which is a statement about how "
                     "arbitrary the baseline is, not about what the principle achieved. "
                     "This is the cleanest result in the study, and it is invisible in "
                     "every aggregate metric &mdash; the protected set is three tiles, "
                     "and what happens on them washes out of a map-wide total."),
    "utilitarian": ("<b>The objective is inert.</b> Fleet transit time is identical to "
                    "the baseline&rsquo;s at all eight sizes on the ladder, to the "
                    "aircraft-timestep, and at the seven where both sides are proven the "
                    "band on each is zero &mdash; the "
                    "quantity Utilitarian minimises is already at its floor before the "
                    "objective is switched on, because every aircraft is already flying "
                    "a shortest path. So Utilitarian&rsquo;s distinctive routings are "
                    "tie-breaks among equally optimal answers, not the result of "
                    "optimisation, and that is also why it is the cheapest condition in "
                    "the study to solve: the objective prunes the search without ever "
                    "having to trade anything away. The departure delay it does pay is "
                    "real, but it is not bought by this objective &mdash; transit time "
                    "is measured from first move to arrival and does not count waiting "
                    "on the ground."),
    "proportional": ("The objective falls by 31 to 52 per cent against the baseline at "
                     "every size, with a zero band throughout: all four orderings return "
                     "the same proximity cost. Four of the six sizes clear the "
                     "indifference floor, and the two that do not are the two where the "
                     "baseline&rsquo;s own band is widest. This is the one principle "
                     "whose objective both binds and moves &mdash; unlike the caps, "
                     "which do nothing until they bind, and unlike Utilitarian, whose "
                     "objective never has anything to do."),
}


def cap_block(I, cond, label):
    """For the two caps: does the constraint bind, and at what fleet size."""
    rows = []
    for key, lab in ((cond, label), ("baseline", "Baseline")):
        cells = []
        for n in LADDER:
            m = I.get((key, n))
            if m is None:
                cells.append('<td class="absent">&mdash;</td>')
                continue
            u = m["capacity_utilisation_max"]
            cls = ' class="att"' if u >= 0.999 else ' class="dim"'
            cells.append(f'<td{cls}>{u:.2f}</td>')
        rows.append(f'<tr><td class="name">{lab}</td>{"".join(cells)}</tr>')
    heads = "".join(f"<th><i>N</i> = {n}</th>" for n in LADDER)
    return (f'<div class="scroll"><table>\n<caption>Capacity utilisation of the busiest '
            f'tile: 1.00 means the cap is holding the routing against its limit, and is '
            f'marked. Below 1.00 nothing in the routing is touching the cap, so the '
            f'principle is not the thing choosing it.</caption>\n'
            f'<thead><tr><th>cap utilisation</th>{heads}</tr>'
            f'</thead>\n<tbody>\n' + "\n".join(rows) + '\n</tbody></table></div>')


def objective_block(O, cond, label):
    """For the three objectives: the principle's own score, and the baseline's on it."""
    import metrics_run as MR
    if cond not in OBJ_FIELD:
        return ""
    field, unit, dp = OBJ_FIELD[cond]
    rows, hits = [], []
    for n in LADDER:
        a, b = O.get((cond, n)), O.get(("baseline", n))
        if not a or not b or field not in a or field not in b:
            rows.append(f'<tr><td class="name"><i>N</i> = {n}</td>'
                        f'<td colspan="4" class="absent">no proven pair at this '
                        f'size</td></tr>')
            continue
        att = MR.attributable(a, b, field)
        if att:
            hits.append(n)
        d = a[field] - b[field]
        cls = "att" if att else "dim"
        rows.append(
            f'<tr><td class="name"><i>N</i> = {n}</td>'
            f'<td>{a[field]:,.{dp}f}{band_span(a, field, dp)}</td>'
            f'<td>{b[field]:,.{dp}f}{band_span(b, field, dp)}</td>'
            f'<td class="{cls}">{d:+,.{dp}f}</td>'
            f'<td class="{cls}">{"yes" if att else ("&mdash;" if att is None else "no")}'
            f'</td></tr>')
    note = (f'Attributably better than the baseline at <i>N</i>&nbsp;=&nbsp;'
            + ", ".join(str(n) for n in hits) + "." if hits else
            "No size on the ladder separates the two on this objective.")
    return (f'<div class="scroll"><table>\n<caption>{label}&rsquo;s own objective '
            f'({unit}), lower is better, evaluated on both routings. Bands are over the '
            f'four orderings. The last column is the same indifference test the rest of '
            f'the page uses. {note}</caption>\n'
            f'<thead><tr><th>fleet size</th><th>{label}</th><th>Baseline</th>'
            f'<th>&Delta;</th><th>clears the floor</th></tr></thead>\n<tbody>\n'
            + "\n".join(rows) + '\n</tbody></table></div>')


def band_span(cell, field, dp):
    lo, hi = cell.get(field + "_min"), cell.get(field + "_max")
    if lo is None or abs(hi - lo) < 5e-9:
        return ""
    return f'<span class="band"> {lo:,.{dp}f}&ndash;{hi:,.{dp}f}</span>'


OBJ_FIELD = {"prioritarian": ("protected_noise", "dB summed over stations 4, 8, 14", 2),
             "utilitarian": ("transit_time", "fleet transit, aircraft-timesteps", 1),
             "proportional": ("proximity_cost", "proximity-weighted occupancy", 1)}


def pair_section(I, O, cond, label, idx, protected):
    # Grouped by the three performance families the study set out to compare, because
    # the whole question is which family a principle pays in -- a flat run of eight
    # columns hides that the two objectives never touch the middle group and the three
    # caps never touch the last.
    groups, gi = [], 0
    for title, k in (("added noise", 2), ("congestion", 3), ("travel time", 3)):
        groups.append((title, COMPARE[gi:gi + k]))
        gi += k
    heads = "".join(f'<th colspan="{len(g)}" class="grph">{t}</th>' for t, g in groups)
    sub = "".join(f"<th>{h}</th>" for _, h, _, _ in COMPARE)
    rows, hits = [], {}
    for n in LADDER:
        cells = []
        for field, _, dp, _ in COMPARE:
            td, ok = delta(I, cond, n, field, dp)
            cells.append(td)
            if ok:
                hits.setdefault(field, []).append(n)
        a = I.get((cond, n))
        tag = "" if (a is None or a.get("all_proven")) else ' class="dim"'
        rows.append(f'<tr><td class="name"{tag}><i>N</i> = {n}</td>{"".join(cells)}</tr>')
    fig = img(f"pair_{cond}", f"{label} over the baseline, eight fleet sizes")
    prot_note = ("" if cond != "prioritarian" else
                 " The three protected communities are outlined: the baseline flies "
                 "straight through them, and the principle does not.")
    obj = objective_block(O, cond, label) or cap_block(I, cond, label)
    return f"""<div class="finding">
  <span class="fnum">EXPERIMENT {idx:02d} &middot; {label.upper()} vs BASELINE</span>
  <div class="col">
  <p class="kicker">{KICKER[cond]}</p>
  </div>
  <div class="figbox">{fig}
    <p class="figcap"><b>{label} (top) over the no-fairness baseline (bottom)</b>, the
    same problem at each fleet size with and without the principle. Panel titles carry
    peak added noise and fleet hops above the shortest-path floor; a dagger marks a cell
    stopped at the one-hour horizon.{prot_note}</p>
  </div>
  <div class="col">
  <p class="subh">What the principle was asked to do</p>
  <p>{OBJ_INTRO[cond]}</p>
  </div>
  {obj}
  <div class="col">
  <p>{OBJ_NOTE[cond]}</p>
  <p class="subh">What it cost, in the three currencies</p>
  </div>
  <div class="scroll"><table>
<caption>{label} minus the baseline at the same fleet size, one row per size. Negative
is less of the metric. A figure in green clears the indifference floor &mdash; the two
means are further apart than the wider of their two permutation bands and the bands do
not overlap. A grey figure does not, and is therefore not a difference the principle
made, however large it looks. A dagger marks a pair where one side was harvested rather
than proven, so the test could not be run at all. <i>extra hops</i> is already measured
against the baseline and is printed as itself.</caption>
<thead><tr><th rowspan="2">fleet size</th>{heads}</tr><tr>{sub}</tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody></table></div>
  <div class="col">
  <p class="note">{verdict(hits)}</p>
  </div>
</div>"""


CSS = """<style>
.figbox{margin:18px 0 8px; border:1px solid var(--rule); border-radius:5px;
  background:var(--panel); padding:14px}
.figbox img{display:block; width:100%; height:auto; border-radius:3px}
.figcap{font-family:"IBM Plex Sans",sans-serif; font-size:.8rem; color:var(--ink-2);
  margin:11px 2px 0; line-height:1.5}
.figcap b{color:var(--ink)}
.band{color:var(--ink-3); font-size:.82em; padding-left:.25em}
tr.grp td{background:var(--sunk); font-family:"IBM Plex Sans",sans-serif;
  font-size:.78rem; letter-spacing:.03em; color:var(--ink-2)}
td.absent{color:var(--ink-3); font-style:italic; text-align:left}
/* The one distinction the head-to-head tables exist to draw: a number that clears the
   indifference floor, versus one that does not and is therefore not evidence. */
td.att{color:var(--yes); font-weight:600; background:var(--yes-bg)}
td.dim{color:var(--ink-3)}
th.grph{text-align:center; border-left:1px solid var(--rule-2); color:var(--ink-2);
  letter-spacing:.09em}
.subh{font-family:"IBM Plex Sans",sans-serif; font-size:.72rem; font-weight:600;
  letter-spacing:.11em; text-transform:uppercase; color:var(--ink-3);
  margin:22px 0 .45rem}
</style>"""


def build(I, O, prot):
    grid = img("routes_grid_full", "Routing grid: eight fleet sizes by six conditions")
    curves = img("metric_vs_N_full", "Seven metrics against fleet size, with "
                                     "permutation bands")
    sections = "\n\n".join(
        pair_section(I, O, cond, label, i + 1, prot)
        for i, (cond, label) in enumerate(ORDER[:5]))
    return f"""{BEGIN}{CSS}
<div class="finding">
  <span class="fnum">THE MAP</span>
  <div class="col">
  <p class="kicker">Every solve in the study, drawn: eight fleet sizes down, six
  conditions across.</p>
  <p>Rows are fleet sizes, columns are conditions, and each panel draws the routing one
  ordering returned &mdash; every aircraft&rsquo;s path, with line width proportional to
  the traffic on that leg. Circles are the two origins and the destination; the tile
  shading is the community&rsquo;s ambient level, 45 to 65&nbsp;dBA. The paper prints
  four of these rows; all eight are here.</p>
  </div>
  <div class="figbox">{grid}
    <p class="figcap"><b>Figure&nbsp;2 (full).</b> The central result is the
    <i>N</i>&nbsp;=&nbsp;14 row and everything below it: five principles, five different
    objectives, and one identical peak &mdash; 4.77&nbsp;dB &mdash; while the baseline in
    the last column climbs from 5.64 to 7.70. From that row on, the cap is binding, and
    a binding cap removes the arbitrariness: the peak stops depending on which optimal
    routing the solver happened to pick. The pictures still differ &mdash; the paths a
    principle chooses are its own &mdash; but the number they are chosen for does not.
    The bottom two rows were stopped at the one-hour horizon; their dense tangles are
    what an unfinished search looks like, not what the principle asks for.</p>
  </div>
  {panel_table(I)}
  <div class="col">
  <p>Read down the <b><i>N</i>&nbsp;=&nbsp;16</b> column and the collapse is a single
  repeated number. Read across the <b><i>N</i>&nbsp;=&nbsp;24</b> row and the two
  families separate: all five still pin 4.77&nbsp;dB, but the three caps have started
  paying 2.5 to 2.75 fleet-hops for it while the two objectives pay nothing in distance
  &mdash; they buy the same peak by departing later instead.</p>
  </div>
</div>

<div class="finding">
  <span class="fnum">THE METRICS</span>
  <div class="col">
  <p class="kicker">The same 46 cells as seven curves, and then as a table of every
  number behind them.</p>
  <p>Each panel is one performance metric against fleet size. The shaded band around a
  line is that condition&rsquo;s permutation band &mdash; the spread across four aircraft
  orderings of the identical problem. A band is the width of the solver&rsquo;s own
  indifference, so two lines only differ if their means are further apart than the wider
  band and the bands do not overlap. Lines break at cells that were harvested rather than
  proven; those appear as isolated hollow markers, because a stopped search is not a
  sample from the optimal set and joining it to a curve draws a trend that was never
  solved for.</p>
  </div>
  <div class="figbox">{curves}
    <p class="figcap"><b>Peak added noise</b> (top left) is the study in one panel: five
    principles pinned flat on 4.77&nbsp;dB from <i>N</i>&nbsp;=&nbsp;14 with no visible
    band at all, and a baseline that wanders above them inside a grey band up to four
    decibels wide &mdash; the same problem, the same optimum, four different answers.
    <b>Congestion</b> (max aircraft per tile, shared tile-timesteps) separates nothing:
    every principle sits inside the baseline&rsquo;s band at every size. <b>Travel
    time</b> splits along the two families &mdash; average trip length is flat everywhere,
    so the caps pay in extra fleet hops from <i>N</i>&nbsp;=&nbsp;22 while the objectives
    pay in departure delay instead. <b>Total added noise</b> is the one metric on which a
    principle beats the baseline outright: Proportional, along the bottom of that panel,
    lower at all six proven sizes with a zero band throughout, and attributably lower at
    five of them &mdash; N&nbsp;=&nbsp;24 misses only because the baseline&rsquo;s own
    band there is 25&nbsp;dB wide.</p>
  </div>
  {metrics_table(I)}
  <div class="col">
  <p class="note"><b>Reading the table.</b> <i>peak dB</i> is the loudest single
  community&rsquo;s added noise over the whole run; <i>total dB</i> sums added noise over
  every affected community and timestep. <i>max/tile</i> and <i>shared t-steps</i> are
  congestion &mdash; the most aircraft ever over one community, and the number of
  tile-timesteps holding more than one. <i>avg hops</i> is mean trip length,
  <i>extra hops</i> the fleet&rsquo;s total distance above the no-fairness baseline at the
  same size, and <i>dep. delay</i> the aircraft-timesteps spent waiting to launch. The
  last two are the two currencies a principle can pay in, and which one it picks is the
  clearest signature in the table.</p>
  </div>
</div>

<section class="col" style="border-top:2px solid var(--ink); padding-top:28px;
 margin-top:34px">
<p class="eyebrow">One principle at a time</p>
<h2>Five head-to-head experiments</h2>
<p>Everything above compares the principles with each other. The five sections below
take them one at a time against the same control &mdash; the no-fairness baseline at the
same fleet size, the same demand, the same orderings &mdash; and ask three questions of
each. Did it achieve <b>the thing it was asked to achieve</b>, scored on its own
objective? What did it cost in <b>added noise</b>, in <b>congestion</b>, and in
<b>travel time</b>? And does any of that clear the solver&rsquo;s indifference?</p>
<p>Scoring the objective on both routings is what makes the first question answerable.
The solver only reports the objective a run was optimising, so the baseline &mdash; which
optimises nothing &mdash; carries no score for any of them. The three objectives are
therefore recomputed from the stored routings by <code>harness/objectives.py</code>,
which checks itself against the values the solver <i>did</i> report: all 32 runs for
each of the three, reproduced exactly.</p>
</section>

{sections}{END}"""


def main():
    I = load()
    O, prot = load_objectives()
    src = io.open(PAGE, encoding="utf-8").read()
    i, j = src.index(BEGIN), src.index(END) + len(END)
    out = src[:i] + build(I, O, prot) + src[j:]
    if "--check" in sys.argv:
        ok = out == src
        print("up to date" if ok else "OUT OF DATE: rerun findings_page.py")
        return 0 if ok else 1
    io.open(PAGE, "w", encoding="utf-8", newline="\n").write(out)
    print(f"rewrote the map/metrics block: {len(out):,} bytes "
          f"({len(out) - len(src):+,})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
