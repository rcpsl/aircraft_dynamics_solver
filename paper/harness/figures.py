"""Generate the paper's figures as PDF into ../tex/figs/.

usage: python figures.py
"""
import io
import json
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import payload as P

RES = os.path.join(HERE, "results")
FIGS = os.path.join(HERE, "..", "tex", "figs")
os.makedirs(FIGS, exist_ok=True)

plt.rcParams.update({
    "font.size": 8, "axes.labelsize": 8, "legend.fontsize": 7,
    "xtick.labelsize": 7, "ytick.labelsize": 7,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 200, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})

LABEL = {"equal": "Equal", "sufficientarian": "Sufficientarian",
         "prioritarian": "Prioritarian", "utilitarian": "Utilitarian",
         "proportional": "Proportional"}
ORDER = ["equal", "sufficientarian", "prioritarian", "utilitarian", "proportional"]
# Colour-blind safe (Okabe-Ito), and each series also gets its own marker so the
# figure survives greyscale printing.
COLOR = {"equal": "#0072B2", "sufficientarian": "#E69F00",
         "prioritarian": "#009E73", "utilitarian": "#D55E00",
         "proportional": "#CC79A7"}
MARK = {"equal": "o", "sufficientarian": "s", "prioritarian": "^",
        "utilitarian": "D", "proportional": "v"}


# Reuse analyze.py's loader so figures and tables see EXACTLY the same rows. That
# loader merges in the long-budget re-runs, which change several results materially;
# a figure built from the un-merged rows would silently contradict its own table.
import analyze as _A


def load(name):
    return _A.load(name)


def save(fig, stem):
    """Write the PDF the paper includes, plus a PNG twin for eyeballing the result
    without a PDF viewer. Only the PDF is referenced by the LaTeX."""
    fig.savefig(os.path.join(FIGS, stem + ".pdf"))
    fig.savefig(os.path.join(FIGS, stem + ".png"))


# --------------------------------------------------------------- Fig 1: capacity
def fig_capacity():
    """How many simultaneous overflights a community can absorb under a cap D.

    This is the whole 'a neutral cap is not neutral' argument in one panel, and it
    is analytic -- no solver involved.
    """
    alpha = P.AIRCRAFT_DB
    Ds = [x / 10 for x in range(5, 151)]
    fig, ax = plt.subplots(figsize=(3.3, 2.1))
    for b, ls in ((45.0, "-"), (55.0, "--"), (65.0, ":")):
        ys = [max(0, math.floor((10 ** (D / 10) - 1) / 10 ** ((alpha - b) / 10)))
              for D in Ds]
        ax.plot(Ds, [max(y, 0.4) for y in ys], ls, lw=1.5,
                label=f"{b:.0f} dBA ambient")
    ax.set_yscale("log")
    ax.set_xlabel(r"noise cap $D$ (dB of added noise)")
    ax.set_ylabel("aircraft a tile can hold")
    ax.axhline(1, color="0.6", lw=0.6, zorder=0)
    ax.set_xlim(0.5, 15)
    # A capacity of zero cannot be drawn on a log axis, so the curves are floored at
    # 0.4 and that band is labelled for what it is -- otherwise the 45 dBA line reads
    # as "0.4 aircraft" rather than "no aircraft at all".
    ax.axhspan(0.3, 0.55, color="0.92", zorder=0)
    ax.text(14.8, 0.36, "capacity 0: infeasible", ha="right", va="center",
            fontsize=6, color="0.35")
    ax.set_ylim(0.3, None)
    ax.legend(frameon=False, loc="upper left")
    save(fig, "capacity")
    plt.close(fig)
    print("wrote capacity.pdf")


# --------------------------------------------------------------- Fig 2: scaling
def fig_scaling():
    # Raw, for the same reason as table_scaling: the y axis is wall time.
    rows = [r for r in _A.load("scaling", raw=True)
            if r["cfg"].get("who", "communities") == "communities"]
    if not rows:
        print("no scaling rows"); return
    by = {(r["cfg"]["principle"], r["cfg"]["demand_factor"]): r for r in rows}
    factors = sorted({r["cfg"]["demand_factor"] for r in rows})

    fig, ax = plt.subplots(figsize=(3.3, 2.3))
    for p in ORDER:
        xs, ys, proven = [], [], []
        for f in factors:
            r = by.get((p, f))
            if not r or r.get("wall") is None:
                continue
            xs.append(r["N"]); ys.append(r["wall"])
            proven.append(r.get("optimality") == "optimal"
                          and not str(r.get("status", "")).startswith("phase2_failed"))
        if not xs:
            continue
        ax.plot(xs, ys, "-", color=COLOR[p], lw=1.2, alpha=0.85, zorder=2)
        # Filled = proven optimal; hollow = objective applied but unproven (or worse).
        for x, y, ok in zip(xs, ys, proven):
            ax.plot(x, y, MARK[p], ms=4, color=COLOR[p],
                    mfc=COLOR[p] if ok else "white", mew=1.0, zorder=3)
        ax.plot([], [], MARK[p] + "-", color=COLOR[p], ms=4, label=LABEL[p])
    ax.axhline(600, color="0.35", lw=0.8, ls="--", zorder=1)
    ax.text(16.5, 430, "600 s budget", fontsize=6, color="0.35", ha="center",
            bbox=dict(fc="white", ec="none", pad=0.8))
    ax.set_yscale("log")
    ax.set_xlabel(r"fleet size $N$")
    ax.set_ylabel("solve time (s)")
    ax.legend(frameon=False, loc="lower right", ncol=1)
    save(fig, "scaling")
    plt.close(fig)
    print("wrote scaling.pdf")


# --------------------------------------------------------------- Fig 3: tradeoff
def fig_tradeoff():
    """Peak vs total added noise. The aggregation objection, plotted."""
    rows = [r for r in load("scaling")
            if r["cfg"].get("who", "communities") == "communities"
            and "peakAddedDB" in r]
    if not rows:
        print("no tradeoff rows"); return
    fig, ax = plt.subplots(figsize=(3.3, 2.3))
    for p in ORDER:
        rs = sorted([r for r in rows if r["cfg"]["principle"] == p],
                    key=lambda r: r["N"])
        if not rs:
            continue
        ax.plot([r["totalAddedDB"] for r in rs], [r["peakAddedDB"] for r in rs],
                MARK[p] + "-", color=COLOR[p], ms=3.5, lw=0.9, alpha=0.85,
                label=LABEL[p])
    ax.set_xlabel("total added noise (summed dB, all communities)")
    ax.set_ylabel("peak added noise (dB)")
    ax.legend(frameon=False, loc="upper left", fontsize=6)
    save(fig, "tradeoff")
    plt.close(fig)
    print("wrote tradeoff.pdf")


# --------------------------------------------------------------- Fig 4: tier share
def fig_tiers():
    """Where each PRINCIPLE flies, by ambient tier, at N=16.

    The cap sweep was the obvious place to look for the decibel metric's pull toward
    already-loud communities and it is NOT there -- with no objective, the tier share
    is set by the tie-break. It shows up here instead, in the objectives.
    """
    from collections import defaultdict
    rows = [r for r in load("scaling")
            if r["cfg"].get("who", "communities") == "communities"
            and r["cfg"].get("demand_factor") == 1.0 and r.get("paths")]
    if not rows:
        print("no scaling rows for tiers"); return

    def share(r):
        starts, ends, mult = P.build_streams(r["cfg"].get("demand_factor", 1.0))
        tiers = defaultdict(int); tot = 0
        for i, path in enumerate(r["paths"]):
            s0, e0 = starts[i], ends[i]
            if s0 == e0:
                continue
            t_fm = next((t for t in range(len(path)) if path[t] != s0), None)
            if t_fm is None:
                continue
            t_arr = next((t for t in range(len(path)) if path[t] == e0), len(path) - 1)
            for t in range(t_fm, t_arr + 1):
                tiers[P.BASELINE[path[t] - 1]] += mult[i]; tot += mult[i]
        return {b: 100.0 * tiers[b] / tot for b in (45, 55, 65)} if tot else None

    by = {r["cfg"]["principle"]: r for r in rows}
    xs, data = [], {45: [], 55: [], 65: []}
    for p in ORDER:
        r = by.get(p)
        if not r:
            continue
        s = share(r)
        if not s:
            continue
        xs.append(LABEL[p].replace("Sufficientarian", "Suffic."))
        for b in (45, 55, 65):
            data[b].append(s[b])
    if not xs:
        print("no tier shares"); return

    fig, ax = plt.subplots(figsize=(3.3, 2.2))
    bottom = [0.0] * len(xs)
    for b, c in ((45, "#56B4E9"), (55, "#F0E442"), (65, "#D55E00")):
        ax.bar(xs, data[b], bottom=bottom, width=0.62,
               color=c, edgecolor="white", lw=0.5, label=f"{b} dBA")
        bottom = [a + v for a, v in zip(bottom, data[b])]
    # Annotate the quiet-tier share, which is the number the argument turns on.
    for i, v in enumerate(data[45]):
        ax.text(i, v / 2, f"{v:.0f}", ha="center", va="center", fontsize=6.5)
    ax.set_ylabel("% of flight time over tier")
    ax.set_ylim(0, 100)
    ax.tick_params(axis="x", rotation=25)
    for lbl in ax.get_xticklabels():
        lbl.set_ha("right")
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.20))
    save(fig, "tiers")
    plt.close(fig)
    print("wrote tiers.pdf")


# ------------------------------------------------- shared 5x5 map renderer
SHADE = {45: "#dceefb", 55: "#f5f0d8", 65: "#f2d6c4"}
# Prioritarian's protected set. Deliberately not the ambient palette and not the route
# red: the outline marks WHICH communities are protected, not how loud they are or how
# much traffic they take.
PROT_EC = "#1c6b52"


def _leg_usage(row, req):
    """How many aircraft fly each leg, over the solver's own active-noise window.

    Keyed on the unordered tile pair, so a corridor used in both directions reads as
    one thick line rather than two coincident thin ones.
    """
    from collections import defaultdict
    import metrics as MX
    paths = row["paths"]
    starts, ends = req["startPositions"], req["endPositions"]
    mult = req.get("aircraftMultipliers") or [1] * len(paths)
    use = defaultdict(int)
    for i, w in enumerate(MX._windows(paths, starts, ends)):
        if w is None:
            continue
        for t in range(max(0, w[0] - 1), w[1]):
            a, b = paths[i][t] - 1, paths[i][t + 1] - 1
            if a != b:
                use[(min(a, b), max(a, b))] += mult[i]
    return use


def _draw_map(ax, row, req, title=None, title_size=7.5, ring=9.0, protected=None):
    """One Fig.-2 panel: tiles shaded by ambient, vertiports ringed, every leg
    overlaid with width proportional to the aircraft on it.

    The ambient shading comes from `req["baseline"]`, not the module constant, so a
    panel drawn for an alternative ambient map shows the map it was actually solved on.
    """
    base = req["baseline"]
    for m in range(P.M):
        r_, c_ = divmod(m, 5)
        ax.add_patch(plt.Rectangle((c_ - .5, -r_ - .5), 1, 1,
                                   fc=SHADE.get(base[m], "#eeeeee"), ec="white",
                                   lw=1.0, zorder=0))
    # The protected set, drawn on the tile rather than beside it. Prioritarian's whole
    # objective is the noise summed over these three communities, and a reader cannot
    # judge the routing against that objective without seeing WHERE they are -- the
    # difference between a principle that reroutes around them and one that happens
    # not to overfly them is visible only on the map.
    for s in (protected or []):
        r_, c_ = divmod(s - 1, 5)
        ax.add_patch(plt.Rectangle((c_ - .5, -r_ - .5), 1, 1, fc="none",
                                   ec=PROT_EC, lw=1.5, ls=(0, (2.2, 1.4)), zorder=2))

    for v in P.vertiport_indices():
        r_, c_ = divmod(v, 5)
        ax.plot(c_, -r_, "o", ms=ring, mfc="none", mec="#222", mew=1.4, zorder=4)

    use = _leg_usage(row, req)
    mx = max(use.values()) if use else 1
    for (a, b), n in use.items():
        ra, ca = divmod(a, 5)
        rb, cb = divmod(b, 5)
        ax.plot([ca, cb], [-ra, -rb], "-", color="#b3261e",
                lw=0.7 + 2.6 * n / mx, alpha=0.8, solid_capstyle="round", zorder=3)
    if title:
        ax.set_title(title, fontsize=title_size, pad=3)
    ax.set_xlim(-.6, 4.6); ax.set_ylim(-4.6, .6)
    ax.set_aspect("equal"); ax.axis("off")
    return mx


def _ambient_legend(fig, y=0.0, size=7, protected=None):
    handles = [plt.Rectangle((0, 0), 1, 1, fc=SHADE[b], ec="white") for b in (45, 55, 65)]
    labels = ["45 dBA", "55 dBA", "65 dBA"]
    if protected:
        handles.append(plt.Rectangle((0, 0), 1, 1, fc="none", ec=PROT_EC, lw=1.5,
                                     ls=(0, (2.2, 1.4))))
        labels.append("protected: stations "
                      + ", ".join(str(s) for s in sorted(protected)))
    fig.legend(handles, labels, frameon=False, ncol=len(labels),
               loc="lower center", bbox_to_anchor=(0.5, y), fontsize=size,
               handlelength=1.1, handleheight=0.9, columnspacing=1.4)


def fig_routes():
    """The map, and what three principles actually do to the flight paths.

    Aggregate metrics say a principle changed the routing; only this shows how. Tiles
    are shaded by ambient level, vertiports ringed, and each panel overlays every
    aircraft's path with line width proportional to how many aircraft use that leg.
    """
    from collections import defaultdict
    rows = [r for r in load("scaling")
            if r["cfg"].get("who", "communities") == "communities"
            and r["cfg"].get("demand_factor") == 1.0 and r.get("paths")]
    by = {r["cfg"]["principle"]: r for r in rows}
    # Utilitarian and Proportional converge to the same occupancy map at this demand
    # once both are given a long budget, so showing both would waste a panel. Equal
    # and Prioritarian are the two hard-cap maps that differ most from each other.
    show = [p for p in ("equal", "prioritarian", "utilitarian") if p in by]
    if not show:
        print("no route rows"); return

    import metrics as MX
    fig, axes = plt.subplots(1, len(show), figsize=(7.0, 2.35), squeeze=False)

    for ax, p in zip(axes[0], show):
        r = by[p]
        det = sum(h - f for h, f in zip(r["tripHops"], r["tripFloorHops"]))
        _draw_map(ax, r, MX._req_for(r),
                  title=f"{LABEL[p]}\npeak {r['peakAddedDB']:.2f} dB, +{det} hops",
                  title_size=7.5, ring=9.0)

    _ambient_legend(fig, y=0.0, size=7)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.86, bottom=0.13, wspace=0.02)
    save(fig, "routes")
    plt.close(fig)
    print("wrote routes.pdf")


# =========================================================================
# FLEET-SIZE STUDY (2026-09-09). Everything below reads the unlimited-budget
# sweep through metrics_run, so a figure and the table beside it can never be
# built from different rows.
#
# One convention throughout: a marker is FILLED when the cell is proven optimal
# and HOLLOW when it is a verified feasible routing whose optimality is unproven.
# The distinction is load-bearing -- a hollow point is a real routing and a real
# upper bound on the metric, but it is not the optimum -- so it is drawn, never
# averaged away, and never silently dropped.
# =========================================================================
CONDITIONS = ORDER + ["baseline"]
CLABEL = dict(LABEL, baseline="Baseline")
CCOLOR = dict(COLOR, baseline="#555555")
CMARK = dict(MARK, baseline="x")
LADDER = (8, 16, 24, 32)          # the fleet sizes routes_grid shows


# The banded cell table the session-3 figures read. Set to None to fall back to the
# session-2 single-run table.
MAIN_STEM = "fleet_main_metrics"
MAIN_FILES = ["results/fleet_main.jsonl"]


def _fleet(setup=None):
    """(cells, metrics, setup_name) for the study, or (None, None, None)."""
    import metrics_run as MR
    import os as _os
    main = _os.path.join(RES, MAIN_STEM + ".json")
    if _os.path.exists(main):
        cells = MR.cells(MAIN_FILES)
        mets = MR.metrics_index(main)
    else:
        cells = MR.cells()
        mets = MR.metrics_index()
    if not cells:
        return None, None, None
    if setup is None:
        names = [k[0] for k in cells]
        setup = max(set(names), key=names.count)
    return cells, mets, setup


def _proven(m):
    return m is not None and m.get("optimality") == "optimal"


def _series(mets, setup, cond, field):
    """(Ns, values, proven-flags) for one condition, sorted by N."""
    pts = sorted(((k[2], m) for k, m in mets.items()
                  if k[0] == setup and k[1] == cond and m.get(field) is not None),
                 key=lambda p: p[0])
    return ([n for n, _ in pts], [m[field] for _, m in pts],
            [_proven(m) for _, m in pts])


def _plot_series(ax, mets, setup, field, conds=None, baseline_dashed=True):
    """A line through the mean, with the permutation range shaded behind it.

    The band IS the indifference floor at that cell, so a reader can see
    attributability directly: two lines whose bands overlap are not separated by
    anything the principle did.
    """
    for c in (conds or CONDITIONS):
        xs, ys, pv = _series(mets, setup, c, field)
        if not xs:
            continue
        lo = [(mets.get((setup, c, x)) or {}).get(field + "_min") for x in xs]
        hi = [(mets.get((setup, c, x)) or {}).get(field + "_max") for x in xs]
        if all(v is not None for v in lo + hi) and any(h > l for l, h in zip(lo, hi)):
            ax.fill_between(xs, lo, hi, color=CCOLOR[c], alpha=0.16, lw=0, zorder=1)
        dashed = (c == "baseline") and baseline_dashed
        # The line joins PROVEN cells only. A harvested cell sits wherever its search
        # was stopped, so joining it to the curve draws a trend out of how far the
        # solver got -- at N=30 that turns a stopped search into an apparent jump from
        # 0 to 115 extra hops. Unproven cells are drawn as isolated hollow markers,
        # which is what they are: a real routing, at an unknown distance from the
        # optimum.
        run_x, run_y = [], []
        for x, y, ok in zip(xs, ys, pv):
            if ok:
                run_x.append(x); run_y.append(y)
            else:
                if len(run_x) > 1:
                    ax.plot(run_x, run_y, "--" if dashed else "-", color=CCOLOR[c],
                            lw=1.1, alpha=0.9, zorder=2)
                run_x, run_y = [], []
        if len(run_x) > 1:
            ax.plot(run_x, run_y, "--" if dashed else "-", color=CCOLOR[c],
                    lw=1.1, alpha=0.9, zorder=2)
        for x, y, ok in zip(xs, ys, pv):
            ax.plot(x, y, CMARK[c], ms=3.8, color=CCOLOR[c],
                    mfc=CCOLOR[c] if ok else "white", mew=0.9, zorder=3)


def _legend_handles(mets, setup):
    hs, ls = [], []
    for c in CONDITIONS:
        if any(k[0] == setup and k[1] == c for k in mets):
            hs.append(plt.Line2D([], [], color=CCOLOR[c], marker=CMARK[c], ms=3.8,
                                 ls="--" if c == "baseline" else "-", lw=1.1))
            ls.append(CLABEL[c])
    return hs, ls


# ------------------------------------------------------------ F1 routes_grid
_ABSENT = None


def _absent_label(cond, n):
    """Why a cell has no panel: it failed, or it was never run."""
    global _ABSENT
    if _ABSENT is None:
        import glob
        import divergence as _DV
        _ABSENT = {}
        for p in glob.glob(os.path.join(RES, "fleet_main.jsonl")):
            for line in io.open(p, encoding="utf-8"):
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                st = str(r.get("status", ""))
                if st.startswith("phase2_failed") or r.get("fellBackToPhase1"):
                    _ABSENT[(_DV.principle_of(r), r.get("N"))] = "no verified routing"
    return _ABSENT.get((cond, n), "not run")


FULL_LADDER = (6, 8, 14, 16, 22, 24, 30, 32)


def fig_routes_grid_full(stem="routes_grid_full"):
    """Every cell of the ladder in one grid: 8 fleet sizes x 6 conditions.

    The paper's version shows four sizes because eight rows of six panels does not fit
    an IEEEtran float. A web page has no such limit, and the whole point of the figure is
    the progression down a column, so the screen version shows all of it.
    """
    return fig_routes_grid(sizes=FULL_LADDER, split=False, stem=stem, width=10.5,
                           panel_h=1.34)


def fig_pair_grid(cond, sizes=FULL_LADDER, stem=None, width=10.5, panel_h=1.34,
                  protected=None):
    """One principle over the no-fairness baseline, the whole ladder left to right.

    The six-column grid answers "how do the principles differ from each other"; it is
    the wrong shape for "what did THIS principle do", because the reader has to jump
    across four columns to reach the baseline. Here the comparison is vertical and
    adjacent -- the same fleet size, the same problem, with and without the principle --
    and the growth with N is the horizontal axis.
    """
    import metrics as MX
    cells, mets, setup = _fleet()
    if not cells:
        print("no fleet rows for pair_grid"); return
    stem = stem or f"pair_{cond}"
    rows = [cond, "baseline"]
    have = [n for n in sizes if any(k[0] == setup and k[2] == n for k in cells)]
    nr, nc = len(rows), len(have)
    fig, axes = plt.subplots(nr, nc, figsize=(width, panel_h * nr + 0.7),
                             squeeze=False)
    for ri, c in enumerate(rows):
        for ci, n in enumerate(have):
            ax = axes[ri][ci]
            row = cells.get((setup, c, n))
            if row is None:
                ax.axis("off")
                ax.text(0.5, 0.5, _absent_label(c, n), ha="center", va="center",
                        fontsize=6.5, color="0.45", transform=ax.transAxes)
            else:
                req = MX._req_for(row)
                m = mets.get((setup, c, n)) or MX.derive(row, req)
                mark = "" if _proven(m) else r"$^\dagger$"
                _draw_map(ax, row, req,
                          title=f"{m['peak_added']:.2f} dB, +{m['extra_vs_floor']}"
                                f" hops{mark}",
                          title_size=6.2, ring=6.0, protected=protected)
            if ri == 0:
                ax.text(0.5, 1.30, f"$N={n}$", fontsize=8, ha="center", va="bottom",
                        transform=ax.transAxes)
            if ci == 0:
                ax.text(-0.10, 0.5, CLABEL[c], rotation=90, fontsize=8, ha="center",
                        va="center", transform=ax.transAxes,
                        color=CCOLOR[c] if c != "baseline" else "0.35")
    _ambient_legend(fig, y=0.0, size=6.5, protected=protected)
    fig.subplots_adjust(left=0.045, right=0.995, top=0.86, bottom=0.10,
                        wspace=0.03, hspace=0.30)
    save(fig, stem)
    plt.close(fig)
    print(f"wrote {stem}.pdf  ({nr}x{nc}, {cond} vs baseline)")


def fig_routes_grid(sizes=LADDER, split=True, stem="routes_grid", width=7.0,
                    panel_h=1.30):
    """Rows = fleet size, columns = condition. The centrepiece.

    Aggregate metrics say a principle changed the routing; only this shows how, and
    putting the fleet sizes on rows is what makes the CHANGE with N visible rather
    than inferred from a curve.

    Split into two floats at N=16 by default: six columns of a 5x5 map across one
    IEEEtran text width is about 1.1 in per panel, which is legible for four rows but
    not for eight.
    """
    import metrics as MX
    import metrics_run as MR
    cells, mets, setup = _fleet()
    if not cells:
        print("no fleet rows for routes_grid"); return
    have = [n for n in sizes if any(k[0] == setup and k[2] == n for k in cells)]
    if not have:
        print("no fleet rows at the ladder sizes"); return
    conds = [c for c in CONDITIONS
             if any(k[0] == setup and k[1] == c and k[2] in have for k in cells)]

    # Split only when the panels would actually be too small to read. At IEEEtran's
    # 7.0 in text width six columns still leaves ~1.17 in per 5x5 map, which is legible
    # for four rows -- the maps are five tiles across and carry no text. Seven or more
    # columns drops below ~1.1 in, which is not, and that is where the split happens.
    wide = (width / max(1, len(conds))) < 1.1 and len(have) > 2
    groups = ([[n for n in have if n < 16], [n for n in have if n >= 16]]
              if split and wide else [have])
    groups = [g for g in groups if g]
    for gi, rows_n in enumerate(groups):
        this_stem = stem if len(groups) == 1 else f"{stem}{gi + 1}"
        nr, nc = len(rows_n), len(conds)
        fig, axes = plt.subplots(nr, nc, figsize=(width, panel_h * nr + 0.45),
                                 squeeze=False)
        for ri, n in enumerate(rows_n):
            for ci, c in enumerate(conds):
                ax = axes[ri][ci]
                row = cells.get((setup, c, n))
                if row is None:
                    # Distinguish "has not returned" from "returned nothing usable".
                    # A phase-2 failure IS finished -- it just produced no routing its
                    # own search could verify, so the solver fell back to the
                    # unweighted route. Labelling that "still solving" would promise a
                    # result that is not coming.
                    ax.axis("off")
                    ax.text(0.5, 0.5, _absent_label(c, n), ha="center", va="center",
                            fontsize=6.5, color="0.45", transform=ax.transAxes)
                    if ci == 0:
                        ax.text(-0.08, 0.5, f"$N={n}$", rotation=90, fontsize=8,
                                ha="center", va="center", transform=ax.transAxes)
                    continue
                req = MX._req_for(row)
                m = mets.get((setup, c, n)) or MX.derive(row, req)
                mark = "" if _proven(m) else r"$^\dagger$"
                t = (f"{m['peak_added']:.2f} dB, +{m['extra_vs_floor']} hops{mark}"
                     if ri or True else "")
                _draw_map(ax, row, req, title=t, title_size=6.2, ring=6.0)
                if ri == 0:
                    ax.text(0.5, 1.30, CLABEL[c], fontsize=7.5, ha="center",
                            va="bottom", transform=ax.transAxes)
                if ci == 0:
                    ax.text(-0.08, 0.5, f"$N={n}$", rotation=90, fontsize=8,
                            ha="center", va="center", transform=ax.transAxes)
        _ambient_legend(fig, y=0.0, size=6.5)
        fig.subplots_adjust(left=0.03, right=0.995, top=0.90 - 0.01 * nr,
                            bottom=0.075, wspace=0.03, hspace=0.30)
        save(fig, this_stem)
        plt.close(fig)
        print(f"wrote {this_stem}.pdf  ({nr}x{nc}, N={rows_n})")


# ----------------------------------------------------------- F2 metric_vs_N
METRIC_PANELS = [
    ("peak_added",             "peak added noise (dB)",       True),
    ("total_added",            "total added noise (dB, summed)", True),
    ("max_count",              "max aircraft per tile",       True),
    ("shared_tile_timesteps",  "shared tile-timesteps",       True),
    ("avg_trip_hops",          "avg trip length (hops)",      True),
    ("departure_delay_total",  "departure delay (ac-timesteps)", True),
    ("extra_vs_baseline",      "extra hops vs baseline",      False),
]


def fig_metric_vs_N_full(stem="metric_vs_N_full"):
    """All seven headline metrics, 4x2, peak added noise first.

    The paper's F2 has room for six panels and drops peak added noise, which the
    closed-form cap argument carries in the text instead. Nothing outside the paper
    is short of space, so this variant plots the whole set with the headline metric
    in the first cell.
    """
    return fig_metric_vs_N(panels=METRIC_PANELS, nrow=4, ncol=2, stem=stem,
                           figsize=(7.2, 8.2))


def fig_metric_vs_N(panels=None, nrow=2, ncol=3, stem="metric_vs_N",
                    figsize=(7.0, 3.7)):
    """Six panels, one per headline metric, five principles and a dashed baseline.

    `extra travel vs baseline` has no baseline series by construction -- it is the
    distance from it -- so that panel carries a zero line instead.
    """
    cells, mets, setup = _fleet()
    if not mets:
        print("no fleet metrics for metric_vs_N"); return
    PANELS = panels if panels is not None else [
        ("avg_trip_hops",          "avg trip length (hops)",      True),
        ("departure_delay_total",  "departure delay (ac-timesteps)", True),
        ("extra_vs_baseline",      "extra hops vs baseline",      False),
        ("max_count",              "max aircraft per tile",       True),
        ("shared_tile_timesteps",  "shared tile-timesteps",       True),
        ("total_added",            "total added noise (dB, summed)", True),
    ]
    fig, axes = plt.subplots(nrow, ncol, figsize=figsize)
    for ax in axes.ravel()[len(PANELS):]:
        ax.axis("off")
    for ax, (field, ylab, with_base) in zip(axes.ravel(), PANELS):
        conds = CONDITIONS if with_base else ORDER
        _plot_series(ax, mets, setup, field, conds=conds)
        if not with_base:
            ax.axhline(0, color="0.55", lw=0.8, ls="--", zorder=1)
        ax.set_xlabel(r"fleet size $N$")
        ax.set_ylabel(ylab)
        ax.axvline(16, color="0.85", lw=0.8, zorder=0)
    hs, ls = _legend_handles(mets, setup)
    fig.legend(hs, ls, frameon=False, ncol=len(ls), loc="lower center",
               bbox_to_anchor=(0.5, -0.02), fontsize=7)
    fig.tight_layout(rect=(0, 0.045, 1, 1))
    save(fig, stem)
    plt.close(fig)
    print(f"wrote {stem}.pdf")


# ---------------------------------------------------------- F3 route_sharing
def fig_route_sharing():
    """How many aircraft fly a route another aircraft is also flying, against N.

    `identical_routes` ignores timing: same sequence of tiles, possibly minutes apart.
    That is what "sharing a route" means to a reader, and it is the quantity that
    separates a principle which concentrates traffic into corridors from one which
    fans it out.
    """
    cells, mets, setup = _fleet()
    if not mets:
        print("no fleet metrics for route_sharing"); return
    # Single column. The time-insensitive grouping is the one a reader wants -- two
    # aircraft in the same corridor minutes apart still share a corridor -- and at
    # IEEEtran's column width one panel is legible where two are not. The strict
    # same-timestep grouping is in fleet_metrics.csv as `identical_paths`.
    fig, axes = plt.subplots(1, 1, figsize=(3.3, 2.3), squeeze=False)
    for ax, (kind, lab) in zip(axes[0], (("identical_routes", "same route, any time"),)):
        for c in CONDITIONS:
            pts = sorted(((k[2], m) for k, m in mets.items()
                          if k[0] == setup and k[1] == c and m.get(kind)),
                         key=lambda p: p[0])
            if not pts:
                continue
            xs = [n for n, _ in pts]
            ys = [100.0 * m[kind]["aircraft_in_shared"] / max(1, m["aircraft_flown"])
                  for _, m in pts]
            ax.plot(xs, ys, "--" if c == "baseline" else "-", color=CCOLOR[c],
                    lw=1.1, alpha=0.9, zorder=2)
            for x, y, (_, m) in zip(xs, ys, pts):
                ax.plot(x, y, CMARK[c], ms=3.8, color=CCOLOR[c],
                        mfc=CCOLOR[c] if _proven(m) else "white", mew=0.9, zorder=3)
        ax.set_xlabel(r"fleet size $N$")
        ax.set_ylabel("% of fleet on a shared route")
        ax.set_ylim(-3, 103)
        ax.axvline(16, color="0.85", lw=0.8, zorder=0)
    hs, ls = _legend_handles(mets, setup)
    fig.legend(hs, ls, frameon=False, ncol=2, loc="lower center",
               bbox_to_anchor=(0.5, -0.04), fontsize=6.5)
    fig.tight_layout(rect=(0, 0.14, 1, 1))
    save(fig, "route_sharing")
    plt.close(fig)
    print("wrote route_sharing.pdf")


# --------------------------------------------------------- F4 noise_over_time
def fig_noise_over_time():
    """Added noise per timestep, one panel per condition, one line per fleet size.

    The aggregate totals cannot show whether a principle spreads its burden over the
    horizon or concentrates it into one loud moment, and a community experiences the
    moment. Arithmetic dB sum over tiles, matching `total_added`; the energy-summed
    variant is in fleet_metrics.csv as `total_added_by_t_energy`.
    """
    cells, mets, setup = _fleet()
    if not mets:
        print("no fleet metrics for noise_over_time"); return
    conds = [c for c in CONDITIONS if any(k[0] == setup and k[1] == c for k in mets)]
    ns = sorted({k[2] for k in mets if k[0] == setup})
    if not ns:
        return
    cmap = plt.get_cmap("viridis")
    fig, axes = plt.subplots(1, len(conds), figsize=(7.0, 1.95), sharey=True,
                             squeeze=False)
    for ax, c in zip(axes[0], conds):
        for n in ns:
            m = mets.get((setup, c, n))
            if not m or not m.get("total_added_by_t"):
                continue
            y = m["total_added_by_t"]
            ax.plot(range(len(y)), y, lw=1.0,
                    color=cmap((n - min(ns)) / max(1, (max(ns) - min(ns)))),
                    alpha=0.95, ls="-" if _proven(m) else ":")
        ax.set_title(CLABEL[c], fontsize=7.5)
        ax.set_xlabel("timestep")
    axes[0][0].set_ylabel("added noise (dB, summed\nover communities)")
    sm = plt.cm.ScalarMappable(cmap=cmap,
                               norm=plt.Normalize(vmin=min(ns), vmax=max(ns)))
    cb = fig.colorbar(sm, ax=axes[0], fraction=0.02, pad=0.012)
    cb.set_label(r"fleet size $N$", fontsize=7)
    cb.ax.tick_params(labelsize=6)
    save(fig, "noise_over_time")
    plt.close(fig)
    print("wrote noise_over_time.pdf")


# --------------------------------------------------------------- F5 solve_time
def fig_solve_time(running=None):
    """Wall time to a PROVEN optimum, against N, per condition.

    `running` maps (condition, N) -> elapsed seconds for a cell that had not finished
    when the figure was drawn. Those are drawn as upward arrows: the solve time is at
    least that, and is not yet known. Reading them as data points would understate
    exactly the principles that are hardest, which is the finding.
    """
    cells, mets, setup = _fleet()
    if not mets:
        print("no fleet metrics for solve_time"); return
    fig, ax = plt.subplots(figsize=(3.3, 2.4))
    par = next((m.get("runner_par") for m in mets.values() if m.get("runner_par")), None)
    for c in CONDITIONS:
        xs, ys, pv = _series(mets, setup, c, "wall")
        if xs:
            ax.plot([x for x, p in zip(xs, pv) if p], [y for y, p in zip(ys, pv) if p],
                    "--" if c == "baseline" else "-", color=CCOLOR[c], lw=1.1,
                    alpha=0.9, zorder=2)
            for x, y, ok in zip(xs, ys, pv):
                ax.plot(x, y, CMARK[c], ms=4, color=CCOLOR[c],
                        mfc=CCOLOR[c] if ok else "white", mew=0.9, zorder=3)
        for (cc, n), el in (running or {}).items():
            if cc != c or not el:
                continue
            ax.annotate("", xy=(n, el * 2.6), xytext=(n, el), annotation_clip=False,
                        arrowprops=dict(arrowstyle="-|>", color=CCOLOR[c], lw=1.0))
            ax.plot(n, el, CMARK[c], ms=4, color=CCOLOR[c], mfc="white", mew=0.9)
    ax.set_yscale("log")
    # Room above the tallest arrow, so a lower bound is not clipped into looking like
    # a measurement that happens to sit on the frame.
    tops = [v * 4.0 for v in (running or {}).values() if v]
    walls = [m["wall"] for m in mets.values() if m.get("wall")]
    if tops or walls:
        ax.set_ylim(top=max(tops + [max(walls) * 1.6 if walls else 0]))
    ax.set_xlabel(r"fleet size $N$")
    ax.set_ylabel("solve time to proven optimum (s)")
    hs, ls = _legend_handles(mets, setup)
    ax.legend(hs, ls, frameon=False, loc="lower right", fontsize=6)
    if par:
        ax.text(0.98, 0.02, f"par = {par}", transform=ax.transAxes, fontsize=6,
                ha="right", va="bottom", color="0.4")
    save(fig, "solve_time")
    plt.close(fig)
    print("wrote solve_time.pdf")


def running_cells():
    """(condition, N) -> elapsed seconds, for cells still searching.

    Read from the checkpoint heartbeats, which are the only record of a solve that has
    not returned. These are lower bounds on the solve time, never solve times, and
    fig_solve_time draws them as arrows for that reason.

    Every `checkpoints*` directory is scanned and the LARGEST elapsed time per cell
    wins. A cell that ran 16.7 h before a machine restart and has since been relaunched
    has two heartbeat files, and the live one is younger; taking the live value would
    quietly weaken the bound from 16.7 h to however long the new run has been going.
    The bound is over everything observed, not over what happens to be running now.
    """
    import glob
    out = {}
    for p in glob.glob(os.path.join(RES, "checkpoints*", "*.json")):
        try:
            d = json.load(io.open(p, encoding="utf-8"))
        except Exception:
            continue
        key = str(d.get("key", ""))
        # ONLY the fleet study. Other sweeps write heartbeats into the same directory
        # and their keys end in the same (condition, factor) pair -- `sl|4|equal|1.0`
        # would otherwise be read as the fleet's Equal N=16 cell, which is proven, and
        # a live slack-sweep heartbeat would report a finished cell as still running.
        if not key.startswith("fleet|"):
            continue
        parts = key.split("|")
        if len(parts) < 4:
            continue
        cond = parts[-2]
        try:
            f = float(parts[-1])
        except ValueError:
            continue
        k = (cond, _A.fleet(f))
        el = d.get("elapsed_s")
        if el is not None and el > (out.get(k) or 0):
            out[k] = el
    # A cell that has since RETURNED is not running, however stale its heartbeat file.
    # The eight harvested cells have both a `partial` row and a leftover heartbeat;
    # without this they would be drawn twice, once as a marker at their stopped wall
    # time and again as an arrow. The marker is the better record -- it is hollow, so
    # it already says "ran this long, not proven" -- and the arrow is reserved for
    # cells that produced nothing at all.
    try:
        import metrics_run as MR
        answered = {(c, n) for (_s, c, n) in MR.metrics_index()}
        out = {k: v for k, v in out.items() if k not in answered}
    except Exception:
        pass
    return out


def fig_levers(stem="levers"):
    """What moves a metric the fleet ladder leaves flat.

    Two knobs, three metric families, one row each. The point of the figure is the
    contrast between the rows: horizon slack and cap tightness act on DIFFERENT halves
    of the menu, so neither alone would have shown that travel time can be moved at all.

    Proven cells only. An unproven cell pays extra arrival time for having been
    stopped, which is indistinguishable on these axes from a principle choosing to
    spend it.
    """
    import metrics_run as MR
    PANELS = [("extra_vs_floor", "extra hops vs floor"),
              ("departure_delay_total", "departure delay (ac-timesteps)"),
              ("max_count", "max aircraft per tile"),
              ("peak_added", "peak added noise (dB)")]
    ROWS = [("results/slack.jsonl", "slack", r"horizon slack above the floor",
             "Horizon slack"),
            ("results/captight.jsonl", "limit", r"noise cap $D$ (dB)",
             "Cap tightness")]

    data = []
    for path, knob, xlab, title in ROWS:
        try:
            recs = [m for m in MR.build([path]) if m.get("optimality") == "optimal"]
        except Exception:
            recs = []
        for m in recs:
            m["_x"] = (m.get("setup") or {}).get(knob)
        recs = [m for m in recs if m.get("_x") is not None]
        data.append((recs, xlab, title))
    if not any(r for r, _, _ in data):
        print("no lever rows yet"); return

    fig, axes = plt.subplots(len(ROWS), len(PANELS),
                             figsize=(7.0, 2.35 * len(ROWS)), squeeze=False)
    for ri, (recs, xlab, title) in enumerate(data):
        # One fleet size per row, so the x axis is the knob and nothing else moves.
        # Pick the size with the MOST knob settings finished, not the largest: a sweep
        # part-way through its biggest fleet would otherwise draw a row containing one
        # point, which shows nothing and looks like a flat line.
        sizes = sorted({m["N"] for m in recs},
                       key=lambda n: (len({m["_x"] for m in recs if m["N"] == n}), n))
        n = sizes[-1] if sizes else None
        for ci, (field, ylab) in enumerate(PANELS):
            ax = axes[ri][ci]
            if not recs:
                ax.axis("off")
                ax.text(.5, .5, "not run yet", ha="center", va="center", fontsize=7,
                        color="0.5", transform=ax.transAxes)
                continue
            for c in CONDITIONS:
                pts = sorted([(m["_x"], m.get(field)) for m in recs
                              if m["condition"] == c and m["N"] == n
                              and m.get(field) is not None])
                if not pts:
                    continue
                ax.plot([p[0] for p in pts], [p[1] for p in pts],
                        CMARK[c] + ("--" if c == "baseline" else "-"),
                        color=CCOLOR[c], ms=3.6, lw=1.1, alpha=.9)
            ax.set_xlabel(xlab, fontsize=7)
            ax.set_ylabel(ylab, fontsize=7)
            ax.tick_params(labelsize=6)
            if ci == 0:
                # Above the panel, not beside it: rotated at the left edge it collided
                # with the y-axis label of the same panel.
                ax.text(0.0, 1.16, f"{title}  ($N={n}$)", fontsize=8, ha="left",
                        va="bottom", transform=ax.transAxes, color="#151b24",
                        fontweight="bold")
    hs, ls = [], []
    for c in CONDITIONS:
        if any(m["condition"] == c for recs, _, _ in data for m in recs):
            hs.append(plt.Line2D([], [], color=CCOLOR[c], marker=CMARK[c], ms=3.6,
                                 ls="--" if c == "baseline" else "-", lw=1.1))
            ls.append(CLABEL[c])
    fig.legend(hs, ls, frameon=False, ncol=len(ls) or 1, loc="lower center",
               bbox_to_anchor=(0.5, -0.015), fontsize=7)
    fig.tight_layout(rect=(0.015, 0.055, 1, 0.97), h_pad=2.6)
    save(fig, stem)
    plt.close(fig)
    print(f"wrote {stem}.pdf")


def fig_floor(stem="floor"):
    """Is the difference between principles bigger than the solver's indifference?

    Units differ across these metrics -- aircraft, decibels, hops -- so plotting the
    raw spreads side by side would compare things that are not comparable. The ratio
    is dimensionless and is the quantity the question actually turns on:

        between-condition spread  /  range one condition covers on its own

    Above 1, the difference is larger than the arbitrary variation and is evidence about
    the principle. Below 1, it is not. The floor is measured two independent ways --
    widening the horizon, and permuting the aircraft list -- and both are drawn, because
    a reader should be able to see that they agree rather than take it on trust.
    """
    import metrics_run as MR
    fleet = {(m["condition"], m["N"]): m
             for m in MR.build() if m.get("optimality") == "optimal"}
    C = ("baseline", "equal", "sufficientarian", "prioritarian")
    METRICS = [("max_count", "max/tile"),
               ("shared_tile_timesteps", "shared"),
               ("peak_added", "peak dB"),
               ("total_added", "total dB"),
               ("extra_vs_floor", "extra hops")]

    def instrument(path, knob):
        try:
            rows = [m for m in MR.build([path]) if m.get("optimality") == "optimal"]
        except Exception:
            return {}
        for m in rows:
            if knob == "seed":
                try:
                    m["_x"] = int(str(m["key"]).split("|")[1])
                except (IndexError, ValueError):
                    m["_x"] = None
            else:
                m["_x"] = (m.get("setup") or {}).get(knob)
        rows = [m for m in rows if m.get("_x") is not None]
        # A floor measured over fewer knob settings is an UNDERESTIMATE, which inflates
        # the ratio and would make a difference look attributable when it is not. Only
        # fleet sizes where every condition has been solved at every setting are drawn;
        # a partially finished sweep simply contributes no bar.
        allx = sorted({m["_x"] for m in rows})
        out = {}
        for n in sorted({m["N"] for m in rows}):
            complete = all(
                any(m["condition"] == c and m["N"] == n and m["_x"] == x for m in rows)
                for c in C for x in allx)
            if not complete:
                continue
            for f, _lab in METRICS:
                w = 0.0
                for c in C:
                    v = [m.get(f) for m in rows if m["condition"] == c
                         and m["N"] == n and m.get(f) is not None]
                    if len(v) > 1:
                        w = max(w, max(v) - min(v))
                out[(n, f)] = w
        return out

    INSTR = [("horizon", instrument("results/slack.jsonl", "slack"), "#7b8a9e"),
             ("aircraft order", instrument("results/perm.jsonl", "seed"), "#b3261e")]
    INSTR = [(nm, d, col) for nm, d, col in INSTR if d]
    if not INSTR:
        print("no floor rows yet"); return

    ns = sorted({n for _nm, d, _c in INSTR for (n, _f) in d})
    ns = [n for n in ns if any((c, n) in fleet for c in C)]
    if not ns:
        print("no fleet rows matching the floor sizes"); return

    fig, axes = plt.subplots(1, len(ns), figsize=(7.0, 2.5), squeeze=False, sharey=True)
    xs = range(len(METRICS))
    width = 0.8 / max(1, len(INSTR))
    for ax, n in zip(axes[0], ns):
        for k, (nm, d, col) in enumerate(INSTR):
            xpos, vals = [], []
            for i, (f, _lab) in enumerate(METRICS):
                if (n, f) not in d:
                    # This instrument has not measured this fleet size. Drawing a bar
                    # would show "no data" as an infinite ratio, i.e. as the strongest
                    # possible evidence -- the exact opposite of what it means.
                    continue
                got = [fleet[(c, n)].get(f) for c in C if (c, n) in fleet
                       and fleet[(c, n)].get(f) is not None]
                b = (max(got) - min(got)) if len(got) > 1 else 0.0
                w = d[(n, f)]
                if w == 0 and b == 0:
                    # Invariant under both the instrument and the principle, which is a
                    # stronger statement than "below the floor". Drawn at 0.
                    xpos.append(i); vals.append(0.0)
                elif w > 0:
                    xpos.append(i); vals.append(min(b / w, 2.15))
            if not xpos:
                continue
            ax.bar([x + k * width - 0.4 + width / 2 for x in xpos], vals, width * 0.92,
                   color=col, label=nm if ax is axes[0][0] else None, alpha=.9)
        ax.axhline(1.0, color="#151b24", lw=1.0, ls="--", zorder=3)
        ax.set_xticks(list(xs))
        ax.set_xticklabels([l for _f, l in METRICS], fontsize=6.5, rotation=30,
                           ha="right")
        ax.set_title(f"$N={n}$", fontsize=8)
        ax.set_ylim(0, 2.2)
    axes[0][0].set_ylabel("between-condition spread\n÷ arbitrary range", fontsize=7.5)
    # The dashed line at 1.0 is the whole reading of the figure, so it is labelled on
    # the axis itself rather than by a floating note that collides with the titles.
    for ax in axes[0]:
        ax.set_yticks([0, 0.5, 1.0, 1.5, 2.0])
    axes[0][0].set_yticklabels(["0", "0.5", "1.0\nfloor", "1.5", "2.0"], fontsize=6.5)
    fig.legend(frameon=False, ncol=2, loc="lower center", bbox_to_anchor=(0.5, -0.04),
               fontsize=7, title="floor measured by", title_fontsize=6.5)
    fig.tight_layout(rect=(0, 0.10, 1, 0.98))
    save(fig, stem)
    plt.close(fig)
    print(f"wrote {stem}.pdf")


def fleet_figures(running=None):
    if running is None:
        running = running_cells()
    fig_routes_grid()
    fig_metric_vs_N()
    fig_route_sharing()
    fig_noise_over_time()
    fig_solve_time(running)
    fig_levers()
    fig_floor()


if __name__ == "__main__":
    if "--fleet" in sys.argv:
        fleet_figures()
    else:
        fig_routes()
        fig_capacity()
        fig_scaling()
        fig_tradeoff()
        fig_tiers()
        fleet_figures()
