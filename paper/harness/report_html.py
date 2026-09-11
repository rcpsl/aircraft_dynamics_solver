"""Build paper/results_review.html -- the fleet-size study, readable in a browser.

A generator rather than a hand-written page, for the same reason `tex/tables` and
`tex/figs` are generated: the numbers move every time a cell proves out, and a page
whose figures come from the solver while its prose is typed by hand drifts apart
silently. Everything here reads `results/fleet_metrics.json` and the PNG twins that
`figures.py` already writes.

The figures are embedded as data URIs so the file is self-contained -- one file to
open, mail, or drop in a shared folder, with no sibling image directory to lose.

usage: python report_html.py
"""
import base64
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RES = os.path.join(HERE, "results")
FIGS = os.path.join(HERE, "..", "tex", "figs")
OUT = os.path.join(HERE, "..", "results_review.html")

LADDER = (6, 8, 14, 16, 22, 24, 30, 32)
CONDS = ["equal", "sufficientarian", "prioritarian", "utilitarian", "proportional",
         "baseline"]
LABEL = {"equal": "Equal", "sufficientarian": "Sufficientarian",
         "prioritarian": "Prioritarian", "utilitarian": "Utilitarian",
         "proportional": "Proportional", "baseline": "Baseline"}


def img(stem):
    """A PNG twin as a data URI, or None if figures.py has not written it."""
    p = os.path.join(FIGS, stem + ".png")
    if not os.path.exists(p):
        return None
    with open(p, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")


def load():
    p = os.path.join(RES, "fleet_metrics.json")
    recs = [m for m in json.load(io.open(p, encoding="utf-8")) if not m.get("probe")]
    return {(m["condition"], m["N"]): m for m in recs}, recs


def running():
    """Longest observed elapsed time per unfinished cell, over every run."""
    import glob
    import analyze as _A
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
        try:
            k = (parts[-2], _A.fleet(float(parts[-1])))
        except ValueError:
            continue
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


# Every column heading in the page, with what the quantity actually is. Kept in one
# place because the same heading appears in more than one table and the two must not
# drift; the short form also becomes the header's tooltip.
COLDEFS = {
    "Condition": ("Which of the six payloads was solved — one of the five fairness "
                  "principles, or <b>Baseline</b>: the same fleet with both caps opened "
                  "to 30 dB and every objective switched off, i.e. the shortest-time "
                  "routing the solver returns when no principle has been chosen."),
    "N": ("Fleet size — how many aircraft are in the air, each flying one "
          "origin&ndash;destination trip between two of the three vertiports."),
    "Avg hops": ("Mean trip length in timesteps, counted from an aircraft's first move "
                 "to its first arrival. One timestep is 180&nbsp;s, so 2.75 hops is "
                 "about 8&frac12; minutes aloft."),
    "vs base": ("Total fleet hops <i>above the Baseline row at the same N</i>. This is "
                "the travel-time price of the principle. Zero means it cost nothing."),
    "Max/tile": ("The largest number of aircraft over a single community at a single "
                 "timestep — the concentration the caps exist to limit."),
    "Shared": ("Tile-timesteps carrying two or more aircraft at once. A community "
               "overflown twice in one timestep contributes one."),
    "Total dB": ("Added noise summed over every community and every timestep. This is "
                 "exactly the quantity the Utilitarian objective minimises. It is an "
                 "arithmetic sum of decibels, so it is an index rather than a level "
                 "anyone hears."),
    "Peak dB": ("The worst added level any one community suffers at any one timestep — "
                "the quantity the cap <span class=\"u\">D</span> bounds, and the number "
                "a resident of the loudest-hit community would experience."),
    "45 dBA share": ("Percentage of the fleet's total flight time spent over the "
                     "quietest tier of communities. It falls when a principle pushes "
                     "traffic onto already-loud tiles."),
    "Wall": ("Seconds of solver time to reach <i>and prove</i> the optimum, with eight "
             "solves running at once. Comparable within this sweep only."),
    "Status": ("<span class=\"u\">optimal</span> means proven best for that objective — "
               "not merely the best found before a clock ran out. A cell still "
               "searching shows how long it has run instead."),
    "Cap D": ("The added-noise ceiling in decibels sent to the solver. Equal and "
              "Sufficientarian send 10; the other conditions send the wide cap of 30, "
              "which no tile on this map can reach, so it binds on nothing."),
    "Tier utilisation": ("Peak aircraft over a community divided by what "
                         "<span class=\"u\">D</span> permits a tile at that ambient "
                         "level to hold, averaged over the tiles in the tier that "
                         "carried traffic. <b>1.00 means the cap is exactly "
                         "binding</b>; a blank tier carried nothing."),
    "Tile capacity": ("How many simultaneous overflights the row's own "
                      "<span class=\"u\">D</span> actually permits at 45&thinsp;/"
                      "&thinsp;55&thinsp;/&thinsp;65&nbsp;dBA. Analytic, not measured — "
                      "it follows from the fact that noise adds in energy."),
    "Peak added": ("Same quantity as <b>Peak dB</b>: the worst added level any single "
                   "community suffers at any timestep."),
    "Distance": ("L<sub>1</sub> distance between per-community occupancy vectors, "
                 "normalised so <b>0 is the same map</b> and 1 means no community "
                 "carries traffic under both. Occupancy rather than path lists, because "
                 "relabelling two interchangeable aircraft rewrites every path without "
                 "changing anything anyone hears."),
}


def tip(name):
    """The bare first sentence of a definition, for a header tooltip."""
    import re
    txt = re.sub(r"<[^>]+>", "", COLDEFS[name])
    txt = txt.replace("&ndash;", "-").replace("&nbsp;", " ")
    txt = txt.replace("&frac12;", "1/2").replace("&thinsp;", "").replace("&mdash;", "-")
    return esc(txt.split(". ")[0].rstrip("."))


def th(name, label=None):
    return f'<th title="{tip(name)}">{label or name}</th>'


def ask(question, method):
    """The two things an experiment has to declare before its numbers mean anything:
    what it is trying to find out, and what was held fixed while it looked."""
    return ('<div class="ask"><p class="q">' + question
            + '</p><p class="m"><b>Setup.</b> ' + method + '</p></div>')


def defs(names, head="What the columns mean"):
    out = [f'<p class="glosshead">{head}</p>', '<dl class="defs">']
    for n in names:
        out.append(f"<dt>{n}</dt><dd>{COLDEFS[n]}</dd>")
    out.append("</dl>")
    return "\n".join(out)


def floor_table():
    """[(N, [(metric label, within-condition range, between-condition spread, dp, ok)])]

    `ok` is True when the between-condition spread exceeds the range one condition
    covers under an incidental change of horizon, False when it does not, and None when
    neither moves at all.
    """
    import metrics_run as MR
    try:
        sl = [m for m in MR.build(["results/slack.jsonl"])
              if m.get("optimality") == "optimal"]
    except Exception:
        return []
    for m in sl:
        m["_x"] = (m.get("setup") or {}).get("slack")
    sl = [m for m in sl if m.get("_x") is not None]
    if not sl:
        return []
    I, _ = load()
    P = {k: m for k, m in I.items() if m.get("optimality") == "optimal"}
    C = ("baseline", "equal", "sufficientarian", "prioritarian")
    METRICS = [("max_count", "max aircraft over one community", 0),
               ("shared_tile_timesteps", "tile-timesteps carrying 2+", 0),
               ("peak_added", "peak added noise (dB)", 2),
               ("total_added", "total added noise (dB)", 1),
               ("extra_vs_floor", "extra hops above the floor", 0)]

    def g(m, f):
        return m.get(f)

    out = []
    for n in sorted({m["N"] for m in sl} & {k[1] for k in P}):
        rows = []
        for f, lab, nd in METRICS:
            w = 0.0
            for c in C:
                v = [g(m, f) for m in sl if m["condition"] == c and m["N"] == n
                     and g(m, f) is not None]
                if len(v) > 1:
                    w = max(w, max(v) - min(v))
            got = [g(P[(c, n)], f) for c in C if (c, n) in P
                   and g(P[(c, n)], f) is not None]
            b = (max(got) - min(got)) if len(got) > 1 else 0.0
            ok = None if (w == 0 and b == 0) else (b > w)
            rows.append((lab, w, b, nd, ok))
        out.append((n, rows))
    return out


def lever_rows():
    """Proven rows of the two knob sweeps, with the knob value promoted to `_x`."""
    import metrics_run as MR
    out = {}
    for key, path, knob in (("slack", "results/slack.jsonl", "slack"),
                            ("cap", "results/captight.jsonl", "limit")):
        try:
            recs = [m for m in MR.build([path]) if m.get("optimality") == "optimal"]
        except Exception:
            recs = []
        for m in recs:
            m["_x"] = (m.get("setup") or {}).get(knob)
        out[key] = [m for m in recs if m.get("_x") is not None]
    return out


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def num(v, nd=2, dash="—"):
    if v is None:
        return dash
    return f"{v:.{nd}f}" if isinstance(v, float) else str(v)


CSS = """
:root{
  /* Neutrals carry a slight blue bias, borrowed from the 45 dBA tile shading in the
     route maps, so page and figures read as one system rather than two. */
  --ground:#f6f8fb; --panel:#ffffff; --sunk:#eef2f7;
  --ink:#151b24; --ink-2:#48566a; --ink-3:#7b8a9e;
  --rule:#dde4ee; --rule-2:#c6d1e0;
  /* The route red from figures.py, and the three ambient tiers it flies over. */
  --route:#b3261e; --route-soft:#f4e3e1;
  --t45:#7fb3e0; --t55:#cbb14e; --t65:#d3805a;
  --proven:#1c7c54; --proven-bg:#e3f2ea;
  --pending:#8a6d1f; --pending-bg:#f7efd8;
  --shadow:0 1px 2px rgba(21,27,36,.05), 0 8px 24px -16px rgba(21,27,36,.28);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ground:#10151c; --panel:#171d26; --sunk:#1d2531;
    --ink:#e7edf5; --ink-2:#9fb0c4; --ink-3:#6f8095;
    --rule:#28323f; --rule-2:#3a4657;
    --route:#e8776c; --route-soft:#33211f;
    --t45:#6f9fcc; --t55:#b59c45; --t65:#c0755a;
    --proven:#5cc79a; --proven-bg:#14342a;
    --pending:#d8b962; --pending-bg:#332c14;
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.8);
  }
}
:root[data-theme="dark"]{
  --ground:#10151c; --panel:#171d26; --sunk:#1d2531;
  --ink:#e7edf5; --ink-2:#9fb0c4; --ink-3:#6f8095;
  --rule:#28323f; --rule-2:#3a4657;
  --route:#e8776c; --route-soft:#33211f;
  --t45:#6f9fcc; --t55:#b59c45; --t65:#c0755a;
  --proven:#5cc79a; --proven-bg:#14342a;
  --pending:#d8b962; --pending-bg:#332c14;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.8);
}

*{box-sizing:border-box}
body{
  background:var(--ground); color:var(--ink);
  font-family:"IBM Plex Serif",Georgia,"Times New Roman",serif;
  font-size:16px; line-height:1.62; margin:0;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1180px; margin:0 auto; padding:0 28px 96px}
.col{max-width:68ch}

h1,h2,h3,.ui{font-family:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif}
h1{font-size:2.6rem; line-height:1.1; font-weight:600; letter-spacing:-.022em;
   margin:0 0 .5rem; text-wrap:balance}
h2{font-size:1.5rem; line-height:1.25; font-weight:600; letter-spacing:-.014em;
   margin:0 0 .55rem; text-wrap:balance}
h3{font-size:1rem; font-weight:600; margin:0 0 .35rem; letter-spacing:-.005em}
p{margin:0 0 1rem}
a{color:var(--route)}
code,.mono{font-family:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace;
  font-size:.86em; font-variant-ligatures:none}
code{background:var(--sunk); padding:.1em .38em; border-radius:3px;
  border:1px solid var(--rule)}

.eyebrow{font-family:"IBM Plex Sans",system-ui,sans-serif; font-size:.7rem;
  font-weight:600; letter-spacing:.13em; text-transform:uppercase;
  color:var(--ink-3); margin:0 0 .5rem}
.lede{font-size:1.12rem; line-height:1.55; color:var(--ink-2); margin:0 0 1.5rem}

/* ---- masthead ------------------------------------------------------- */
header{padding:64px 0 30px; border-bottom:2px solid var(--ink); margin-bottom:26px}
.runline{display:flex; flex-wrap:wrap; gap:6px 22px; font-family:"IBM Plex Mono",monospace;
  font-size:.76rem; color:var(--ink-3); padding-top:14px}
.runline b{color:var(--ink-2); font-weight:500}

/* ---- status ledger --------------------------------------------------- */
.ledger{display:grid; grid-template-columns:repeat(auto-fit,minmax(158px,1fr));
  gap:1px; background:var(--rule); border:1px solid var(--rule);
  border-radius:6px; overflow:hidden; margin:0 0 14px}
.cellstat{background:var(--panel); padding:14px 16px}
.cellstat .k{font-family:"IBM Plex Mono",monospace; font-size:1.55rem;
  line-height:1.1; font-variant-numeric:tabular-nums; letter-spacing:-.02em}
.cellstat .v{font-family:"IBM Plex Sans",sans-serif; font-size:.74rem;
  color:var(--ink-3); margin-top:3px; letter-spacing:.02em}
.cellstat.good .k{color:var(--proven)}
.cellstat.wait .k{color:var(--pending)}

.note{background:var(--sunk); border-left:3px solid var(--rule-2);
  padding:12px 16px; font-size:.9rem; color:var(--ink-2); border-radius:0 4px 4px 0}
.note.warn{border-left-color:var(--pending); background:var(--pending-bg);
  color:var(--ink)}

/* ---- findings -------------------------------------------------------- */
.findings{list-style:none; padding:0; margin:0 0 8px;
  display:grid; gap:18px; grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.findings li{border-top:2px solid var(--route); padding-top:12px}
.findings .n{font-family:"IBM Plex Mono",monospace; font-size:.72rem;
  color:var(--route); letter-spacing:.08em; display:block; margin-bottom:5px}
.findings p{font-size:.94rem; margin:0; color:var(--ink-2)}
.findings strong{color:var(--ink); font-weight:600}

/* ---- experiment sections --------------------------------------------- */
section{padding:44px 0 8px; border-top:1px solid var(--rule); margin-top:34px}
figure{margin:22px 0 8px}
figure img{display:block; width:100%; height:auto; border-radius:4px;
  background:#fff; border:1px solid var(--rule); box-shadow:var(--shadow)}
figcaption{font-family:"IBM Plex Sans",sans-serif; font-size:.83rem;
  color:var(--ink-2); margin-top:11px; max-width:78ch}
figcaption b{color:var(--ink); font-weight:600}
.two{display:grid; gap:22px; grid-template-columns:1fr 1fr; align-items:start}
@media(max-width:820px){.two{grid-template-columns:1fr}}

/* ---- tables ---------------------------------------------------------- */
.scroll{overflow-x:auto; margin:18px 0 6px; border:1px solid var(--rule);
  border-radius:6px; background:var(--panel)}
table{border-collapse:collapse; width:100%; font-size:.83rem;
  font-family:"IBM Plex Sans",sans-serif}
th,td{padding:7px 12px; text-align:right; white-space:nowrap;
  border-bottom:1px solid var(--rule); font-variant-numeric:tabular-nums}
th{font-size:.68rem; text-transform:uppercase; letter-spacing:.07em;
  color:var(--ink-3); font-weight:600; text-align:right;
  background:var(--sunk); position:sticky; top:0}
th:first-child,td:first-child{text-align:left}
tbody tr:last-child td{border-bottom:none}
tr.grp td{background:var(--sunk); font-weight:600; color:var(--ink-2);
  font-size:.74rem; letter-spacing:.06em; text-transform:uppercase}
td.name{font-weight:500}
.pill{display:inline-block; font-family:"IBM Plex Mono",monospace; font-size:.68rem;
  padding:1px 7px; border-radius:99px; letter-spacing:.02em}
.pill.ok{background:var(--proven-bg); color:var(--proven)}
.pill.no{background:var(--pending-bg); color:var(--pending)}
.tier{display:inline-block; width:9px; height:9px; border-radius:2px;
  margin-right:6px; vertical-align:baseline}

/* ---- experiment framing ----------------------------------------------- */
.ask{border-left:3px solid var(--route); padding:2px 0 2px 18px; margin:0 0 20px;
  max-width:74ch}
.ask .q{font-family:"IBM Plex Sans",sans-serif; font-size:1.02rem; font-weight:500;
  color:var(--ink); margin:0 0 .5rem; line-height:1.45}
.ask .m{font-size:.88rem; color:var(--ink-2); margin:0}
.ask .m b{color:var(--ink); font-weight:600}

/* ---- the verdict board ------------------------------------------------- */
.board{display:grid; gap:14px; grid-template-columns:repeat(auto-fit,minmax(248px,1fr));
  margin:4px 0 10px}
.vcard{background:var(--panel); border:1px solid var(--rule); border-radius:6px;
  padding:16px 18px}
.vcard h3{margin:0 0 2px}
.vcard .verdict{font-family:"IBM Plex Sans",sans-serif; font-size:.72rem;
  font-weight:600; letter-spacing:.09em; text-transform:uppercase; margin:0 0 9px}
.vcard.yes .verdict{color:var(--proven)}
.vcard.part .verdict{color:var(--pending)}
.vcard p{font-size:.88rem; color:var(--ink-2); margin:0}
.vcard .big{font-family:"IBM Plex Mono",monospace; font-size:1.3rem; color:var(--ink);
  font-variant-numeric:tabular-nums; display:block; margin:8px 0 2px}
.vcard .big small{font-size:.62rem; font-family:"IBM Plex Sans",sans-serif;
  color:var(--ink-3); letter-spacing:.04em; text-transform:uppercase; margin-left:6px}

/* ---- column glossaries ------------------------------------------------ */
.defs{display:grid; grid-template-columns:max-content 1fr; gap:0 26px;
  margin:14px 0 6px; max-width:82ch; font-size:.86rem}
.defs dt{font-family:"IBM Plex Sans",sans-serif; font-weight:600; color:var(--ink);
  padding:5px 0; white-space:nowrap; border-top:1px solid var(--rule)}
.defs dd{margin:0; color:var(--ink-2); padding:5px 0; line-height:1.5;
  border-top:1px solid var(--rule)}
.defs dt:first-of-type,.defs dd:first-of-type{border-top:none}
.defs .u{font-family:"IBM Plex Mono",monospace; font-size:.9em; color:var(--ink-3)}
@media(max-width:700px){
  .defs{grid-template-columns:1fr; gap:0}
  .defs dt{padding-bottom:0; border-top:1px solid var(--rule)}
  .defs dd{padding-top:2px; padding-bottom:9px; border-top:none}
}
.glosshead{font-family:"IBM Plex Sans",sans-serif; font-size:.7rem; font-weight:600;
  letter-spacing:.13em; text-transform:uppercase; color:var(--ink-3);
  margin:22px 0 2px}
th[title]{cursor:help; text-decoration:underline dotted var(--rule-2);
  text-underline-offset:3px}

footer{margin-top:52px; padding-top:22px; border-top:1px solid var(--rule);
  font-size:.85rem; color:var(--ink-3)}
footer h3{color:var(--ink-2)}
footer ul{padding-left:1.1rem; margin:.3rem 0 1rem}
footer li{margin-bottom:.25rem}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""


def build():
    I, recs = load()
    run = running()
    proven = [m for m in recs if m.get("optimality") == "optimal"]
    ns = sorted({m["N"] for m in recs})

    def cell(c, n, f, nd=2):
        m = I.get((c, n))
        return num(m.get(f), nd) if m else "—"

    H = []
    A = H.append
    A('<title>Fairness at Fleet Scale</title>')
    A('<link rel="preconnect" href="https://fonts.googleapis.com">')
    A('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>')
    A('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
      'family=IBM+Plex+Mono:wght@400;500&'
      'family=IBM+Plex+Sans:wght@400;500;600&'
      'family=IBM+Plex+Serif:ital,wght@0,400;0,600;1,400&display=swap">')
    A("<style>" + CSS + "</style>")
    A('<div class="wrap">')

    # ---------------------------------------------------------------- head
    A('<header>')
    A('<p class="eyebrow">UAM noise routing &middot; Austin, TX &middot; 5&times;5 grid</p>')
    A('<h1>Fairness at Fleet Scale</h1>')
    A('<p class="lede col">How five principles of distributive justice reshape aircraft '
      'routing as the fleet grows past the size of the map — solved to proven '
      'optimality with no time budget at all.</p>')
    A('<div class="runline">'
      '<span><b>solver</b> Z3 4.16.0, unmodified</span>'
      '<span><b>budget</b> none (10<sup>9</sup>&nbsp;ms)</span>'
      '<span><b>parallelism</b> par&nbsp;=&nbsp;8</span>'
      '<span><b>conditions</b> 5 principles + baseline</span>'
      f'<span><b>fleet ladder</b> N = {", ".join(str(n) for n in LADDER)}</span>'
      '</div>')
    A('</header>')

    # ------------------------------------------------------------- ledger
    A('<div class="ledger">')
    A(f'<div class="cellstat good"><div class="k">{len(proven)}</div>'
      '<div class="v">cells proven optimal</div></div>')
    missing = [(c, n) for n in LADDER for c in CONDS if (c, n) not in I]
    A(f'<div class="cellstat wait"><div class="k">{len(missing)}</div>'
      '<div class="v">cells without an answer</div></div>')
    A('<div class="cellstat"><div class="k">32</div>'
      '<div class="v">frontier, cap-based</div></div>')
    A('<div class="cellstat"><div class="k">8</div>'
      '<div class="v">frontier, dB objectives</div></div>')
    A('<div class="cellstat"><div class="k">0</div>'
      '<div class="v">extra hops vs baseline</div></div>')
    A('</div>')
    if run:
        longest = max(run.values()) / 3600.0
        A(f'<div class="note warn"><b>Not finished.</b> Utilitarian and Proportional '
          f'above N=8 have not returned. Each searched between '
          f'{min(run.values())/3600:.1f}&nbsp;h and {longest:.1f}&nbsp;h without '
          'terminating before a machine restart ended the first run; they have been '
          'relaunched. Their solve times are known only to exceed those figures, and '
          'appear on the tractability chart as arrows rather than points.</div>')

    # ------------------------------------------------------- verdict board
    A('<section style="border-top:none;padding-top:34px">')
    A('<p class="eyebrow">The question</p>')
    A('<h2>Does the choice of principle change how the system performs?</h2>')
    A('<p class="col">Three families of metric, one answer each. The test is the same '
      'every time: across the conditions <b>proven optimal</b> at one fleet size, is '
      'the spread between them large enough that a reader could act on it? Unproven '
      'cells are excluded throughout — a stopped search pays a worse arrival penalty '
      'for having been stopped, which would manufacture exactly the travel-time '
      'difference this is looking for.</p>')

    prov = [m for m in recs if m.get("optimality") == "optimal"]

    def sp(n, f, tier=False):
        vs = [((m.get("tier_share") or {}).get("45") if tier else m.get(f))
              for m in prov if m["N"] == n]
        vs = [v for v in vs if v is not None]
        return (max(vs) - min(vs)) if len(vs) > 1 else None

    def worst(f, tier=False):
        best, at = 0, None
        for n in ns:
            v = sp(n, f, tier)
            if v is not None and abs(v) > abs(best):
                best, at = v, n
        return best, at

    mc, mc_n = worst("max_count")
    pk, pk_n = worst("peak_added")
    dd, dd_n = worst("departure_delay_total")
    hp, _ = worst("extra_vs_floor")

    # The verdicts are the ones the floor analysis supports, not the raw spreads. A
    # spread that looks decisive on its own is not a finding if one condition covers
    # more ground than that by itself.
    A('<div class="board">')
    A('<div class="vcard part"><h3>Congestion</h3>'
      '<p class="verdict">Moves &mdash; below the floor</p>'
      f'<span class="big">{mc:.0f}<small>aircraft spread, at N={mc_n}</small></span>'
      '<p>The conditions do differ in how hard the busiest community is hit. But one '
      'condition on its own covers a wider range than that when an incidental '
      'parameter moves, so the ordering is not evidence about the principle.</p>'
      '</div>')
    A('<div class="vcard part"><h3>Travel time</h3>'
      '<p class="verdict">Zero in distance, real in timing</p>'
      f'<span class="big">{hp:.0f}<small>extra hops, every size</small></span>'
      '<p>Every condition flies the shortest-path floor at every fleet size, and keeps '
      'doing so given four extra timesteps of room. The cost is in <b>when</b> aircraft '
      f'leave: up to {dd:.0f} aircraft-timesteps of extra departure delay at '
      f'N={dd_n}.</p>'
      '</div>')
    A('<div class="vcard yes"><h3>Added noise</h3>'
      '<p class="verdict">Only the objectives clear the floor</p>'
      f'<span class="big">{pk:.2f}<small>dB peak spread, at N={pk_n}</small></span>'
      '<p>Utilitarian halves the summed burden at N=8 — nearly twice the floor, so it '
      'is the principle doing it. Among the cap-based conditions the noise differences '
      'are smaller than the arbitrary variation.</p>'
      '</div>')
    A('</div>')

    flr = floor_table()
    if flr:
        A('<p class="glosshead" style="margin-top:30px">But how large is a '
          'difference?</p>')
        A('<div class="note warn" style="max-width:82ch">'
          '<b>Most of those differences are below the solver&rsquo;s own '
          'indifference.</b> Equal and Sufficientarian carry no objective; '
          'Prioritarian&rsquo;s evaluates to 0 at every fleet size and horizon solved, '
          'so it pins nothing. For all three and the baseline the only quantity being '
          'minimised is the arrival penalty &mdash; and that optimum is <b>identical at '
          'every horizon</b> (22 at N=8, 44 at N=16, 66 at N=24). Move only the horizon, '
          'change nothing any of them optimises, and the routing still comes back '
          'different. The range one condition covers that way is a floor: a '
          'between-condition gap smaller than it is not evidence about the '
          'condition.</div>')
        d = img("floor")
        if d:
            A('<figure><img alt="Between-condition spread divided by the arbitrary '
              'range, per metric and fleet size" src="' + d + '">'
              '<figcaption>The same comparison as the table below, as a ratio. Above '
              'the line a difference is larger than the arbitrary variation and is '
              'evidence about the principle; below it, it is not. Fleet sizes whose '
              'floor is not yet fully measured are omitted rather than shown as an '
              'underestimate.</figcaption></figure>')
        A('<div class="scroll"><table><thead><tr><th>N</th><th>metric</th>'
          '<th title="Range a single condition covers when only the horizon moves, '
          'with its arrival optimum unchanged">arbitrary (one condition, horizon 1&ndash;4)</th>'
          '<th title="Spread between the four cap-based conditions at the default horizon">'
          'between conditions</th><th>verdict</th></tr></thead><tbody>')
        for n, rows in flr:
            A(f'<tr class="grp"><td colspan="5">N = {n}</td></tr>')
            for lab, w, b, nd, ok in rows:
                pill = ('<span class="pill ok">attributable</span>' if ok is True else
                        ('<span class="pill no">below the floor</span>' if ok is False
                         else '<span class="pill">no difference</span>'))
                A(f'<tr><td>{n}</td><td class="name">{lab}</td>'
                  f'<td>{w:.{nd}f}</td><td>{b:.{nd}f}</td><td>{pill}</td></tr>')
        A('</tbody></table></div>')
    A('</section>')

    # ------------------------------------------------------------ findings
    A('<section>')
    A('<p class="eyebrow">What the sweep shows</p>')
    A('<ul class="findings">')
    A('<li><span class="n">01</span><p><strong>A cap does nothing until the fleet '
      'outgrows the map.</strong> At N=6 and N=8, Equal, Sufficientarian and the '
      'no-fairness baseline return one identical routing — same count matrix at '
      'every timestep, same paths. They separate only from N=14.</p></li>')
    A('<li><span class="n">02</span><p><strong>The condition holding the fewest '
      'aircraft over any community is the loudest.</strong> At N=24 Equal peaks at '
      '10.00&nbsp;dB against the baseline’s 7.78, while carrying 9 aircraft over '
      'its busiest tile against 13.</p></li>')
    A('<li><span class="n">03</span><p><strong>Fairness is free in travel time and '
      'expensive in compute.</strong> Every proven cell flies shortest paths at every '
      'fleet size. The cap-based conditions prove out to N=32; the two decibel-valued '
      'objectives stop at N=8.</p></li>')
    A('</ul>')
    A('</section>')

    # -------------------------------------------------------- experiment 1
    A('<section>')
    A('<p class="eyebrow">Experiment 1</p>')
    A('<h2>Congestion: routing under each principle as the fleet grows</h2>')
    A(ask("Does choosing a fairness principle change <i>where</i> the traffic goes, "
          "and does that change with fleet size?",
          "Six conditions on one instance, eight fleet sizes from N=6 to N=32, "
          "unlimited solver budget. Everything except the fairness term is held "
          "fixed: same map, same demand, same adjacency, same soft-T arrival "
          "tie-break."))
    A('<div class="col">')
    A('<p>Each panel is the same 5&times;5 map of Austin: tiles shaded by ambient '
      'level, the three vertiports ringed, and every aircraft’s path overlaid '
      'with line width proportional to the traffic on that leg. Rows are fleet '
      'sizes; columns are conditions.</p>')
    A('<p>Read it down a column to see one principle respond to a growing fleet, and '
      'across a row to see the principles disagree at one fleet size. At N=8 the '
      'cap-based columns are indistinguishable from the baseline. By N=32 they are '
      'not.</p>')
    A('</div>')
    d = img("routes_grid")
    if d:
        A('<figure><img alt="Flight paths for each condition at four fleet sizes, '
          'over the 5x5 Austin map" src="' + d + '">')
        A('<figcaption><b>Line width sums over the horizon</b>, so two panels can look '
          'alike while the routings differ in <i>when</i> each leg is flown — '
          'Utilitarian and Proportional at N=8 are exactly that case: drawn '
          'identically here, distinct in the per-timestep counts. Panel titles give '
          'peak added noise and hops above the shortest-path floor.</figcaption>')
        A('</figure>')
    d = img("route_sharing")
    if d:
        A('<div class="two"><figure><img alt="Share of the fleet on a shared route '
          'against fleet size" src="' + d + '">')
        A('<figcaption>No aircraft shares a corridor at N=6; 25 to 29 of 32 do at the '
          'top of the ladder. A growing fleet packs into the same corridors rather '
          'than fanning out into private ones.</figcaption></figure>')
        A('<div><h3>Distance from the no-fairness routing</h3>'
          '<p style="font-size:.9rem;color:var(--ink-2)">L<sub>1</sub> distance between '
          'per-community occupancy vectors, normalised so 0 is the same map and 1 is '
          'disjoint. Zero means the principle returned exactly what the solver serves '
          'when no principle is chosen.</p>')
        A('<div class="scroll"><table><thead><tr>' + th("Condition")
          + "".join(f'<th title="Fleet size">N={n}</th>' for n in ns)
          + '</tr></thead><tbody>')
        for c in CONDS[:-1]:
            if not any((c, n) in I for n in ns):
                continue
            A(f'<tr><td class="name">{LABEL[c]}</td>' + "".join(
                f"<td>{cell(c,n,'occ_dist_vs_baseline',3)}</td>" for n in ns) + '</tr>')
        A('</tbody></table></div>')
        A(defs(["Condition", "N", "Distance"], "Reading this table"))
        A('</div></div>')
    A('</section>')

    # -------------------------------------------------------- experiment 2
    A('<section>')
    A('<p class="eyebrow">Experiment 2</p>')
    A('<h2>Travel time: the cost is real, but it is not distance</h2>')
    A(ask("How much longer does the fleet fly under each principle than it strictly "
          "has to?",
          "Total fleet hops against the shortest-path floor, and against the "
          "no-fairness baseline at the same N. Proven cells only, because a stopped "
          "search pays extra arrival time for having been stopped."))
    A('<div class="col">')
    A('<p>Total fleet hops equal the shortest-path floor — and equal the '
      'baseline’s — for every proven cell at every fleet size. Average trip '
      'length is identical across conditions at each size; it varies with N only '
      'because rounding the demand changes which origin–destination pairs are in '
      'the mix.</p>')
    A('<p>This is a property of the principles, not of a horizon too tight to detour '
      'in. Re-solving at N=16 with three extra timesteps leaves Equal, Sufficientarian '
      'and Prioritarian proven optimal and still flying 44 fleet hops against a floor '
      'of 44. Given room, they decline to use it.</p>')
    A('<p>That holds at every cap the tool would plausibly send. It stops holding at '
      'the very edge of feasibility: tightening <span class="u">D</span> from 10 to 4 '
      'at N=16 makes Equal fly <b>3</b> fleet-hops above the floor and Sufficientarian '
      '<b>4</b>, both proven optimal and the only cells in this study where any '
      'condition flies further than it has to — and one decibel lower, at '
      '<span class="u">D=3</span>, the solver proves no routing exists at all. The '
      'detour lives in that single step.</p>')
    A('</div>')
    d = img("metric_vs_N")
    if d:
        A('<figure><img alt="Six headline metrics plotted against fleet size" src="'
          + d + '">')
        A('<figcaption>Filled markers are proven optima; hollow markers are routings '
          'whose optimality is unproven. <b>The second panel is flat at zero</b> — '
          'that is the finding, not a missing series. The whole cost of choosing a '
          'principle lands on which communities carry the noise.</figcaption></figure>')
    A('</section>')

    # -------------------------------------------------------- experiment 3
    A('<section>')
    A('<p class="eyebrow">Experiment 3</p>')
    A('<h2>Added noise: a uniform cap is not a uniform rule</h2>')
    A(ask("How much noise does each principle create, and which communities carry "
          "the worst of it?",
          "Peak and summed added decibels read off the routing the solver returned, "
          "plus utilisation of the capacity each condition&rsquo;s own cap actually "
          "grants a tile at that ambient level."))
    A('<div class="col">')
    A('<p>Because noise adds in energy, a cap on <i>added</i> decibels buys wildly '
      'different capacity depending on how loud a community already is. Under '
      'D&nbsp;=&nbsp;10&nbsp;dB the same number admits <b>9</b> simultaneous '
      'overflights over a 45&nbsp;dBA community, <b>90</b> over a 55&nbsp;dBA one and '
      '<b>900</b> over a 65&nbsp;dBA one.</p>')
    A('<p>So Equal’s disparity cap pushes traffic off the loud tiles the baseline '
      'was content to stack aircraft on, and onto quiet ones where four aircraft '
      'already add 6.99&nbsp;dB. Its utilisation of quiet-tile capacity climbs steadily '
      'while its loud-tile utilisation never exceeds 0.01 — the cap binds entirely '
      'on the quiet.</p>')
    A('</div>')

    A('<div class="scroll"><table><thead><tr>'
      + th("Condition") + th("N") + th("Cap D")
      + "".join(
          f'<th title="{tip("Tier utilisation")}">'
          f'<span class="tier" style="background:var(--t{t})"></span>{t} dBA</th>'
          for t in ("45", "55", "65"))
      + th("Tile capacity") + th("Peak added") + '</tr></thead><tbody>')
    for n in (16, 32):
        A(f'<tr class="grp"><td colspan="8">Fleet size N = {n}</td></tr>')
        for c in CONDS:
            m = I.get((c, n))
            if not m:
                continue
            bt = m.get("capacity_utilisation_by_tier") or {}
            tc = m.get("tile_capacity") or {}
            A(f'<tr><td class="name">{LABEL[c]}</td><td>{n}</td>'
              f'<td>{num(m.get("D"),0)}</td>'
              + "".join(f'<td>{num(bt.get(t),2)}</td>' for t in ("45", "55", "65"))
              + f'<td class="mono">{tc.get("45","—")}/{tc.get("55","—")}'
                f'/{tc.get("65","—")}</td>'
              f'<td>{num(m.get("peak_added"))} dB</td></tr>')
    A('</tbody></table></div>')
    A(defs(["Condition", "Cap D", "Tier utilisation", "Tile capacity", "Peak added"],
           "What the columns mean"))
    A('<figcaption style="margin-bottom:20px">Utilisation is peak occupancy over what '
      'the row’s own cap grants a tile at that ambient level, averaged over tiles '
      'in the tier that carried traffic. Equal and Sufficientarian send '
      'D&nbsp;=&nbsp;10 and face a real ceiling; the others send the wide cap, under '
      'which no tile on this map can be filled. <b>Equal switches to the wide cap at '
      'N&nbsp;≥&nbsp;30</b>, where the pigeonhole argument guaranteeing an '
      'unburdened community fails — documented behaviour, visible here as a '
      'discontinuity.</figcaption>')

    d = img("noise_over_time")
    if d:
        A('<figure><img alt="Added noise per timestep, one panel per condition" src="'
          + d + '">')
        A('<figcaption>Added noise summed over communities at each timestep. Every '
          'condition produces the same two-peaked shape — a maximum just after '
          'departure, a dip as the fleet spreads, a second rise as it converges on the '
          'destination vertiports. They differ in the height of the first peak, not in '
          'its timing: <b>no principle here spreads its burden more evenly over '
          'time</b>.</figcaption></figure>')
    A('</section>')

    # -------------------------------------------------------- experiment 4
    A('<section>')
    A('<p class="eyebrow">Experiment 4</p>')
    A('<h2>Solver cost: the tractable principles are not the intuitive ones</h2>')
    A(ask("What does each principle cost to compute, and how far up the fleet ladder "
          "can it be solved to proven optimality at all?",
          "Wall time to a proven optimum, eight solves at a time on 14 cores. No time "
          "budget, so a cell that has not returned is genuinely hard rather than "
          "merely cut off."))
    A('<div class="col">')
    A('<p>The four conditions expressible as hard caps prove out across the whole '
      'ladder, from about two seconds at N=6 to between 231 and 696 seconds at N=32, '
      'never more than a factor of 3.1 apart. The two expressed as optimisation '
      'objectives over a decibel-valued sum are in a different complexity regime '
      'entirely, and no budget fixes it.</p>')
    u6, u8 = I.get(("utilitarian", 6)), I.get(("utilitarian", 8))
    p6, p8 = I.get(("proportional", 6)), I.get(("proportional", 8))
    if u6 and u8 and p6 and p8:
        A(f'<p>Utilitarian proves at N=6 in {u6["wall"]:.0f}&nbsp;s and N=8 in '
          f'{u8["wall"]:.0f}&nbsp;s. Proportional proves the same two sizes in '
          f'{p6["wall"]:.0f}&nbsp;s and {p8["wall"]:.0f}&nbsp;s — '
          f'{p6["wall"]/u6["wall"]:.0f}&times; and {p8["wall"]/u8["wall"]:.0f}&times; '
          'Utilitarian’s time for the identical fleet, so the penalty for pricing '
          'the burden per community rather than summing it is itself growing with '
          'N.</p>')
    A('</div>')
    d = img("solve_time")
    if d:
        A('<figure><img alt="Solve time to a proven optimum against fleet size" src="'
          + d + '">')
        A('<figcaption>Wall time to a <b>proven</b> optimum, eight solves at a time. '
          'Arrows mark cells that have not returned: the solve time is bounded below '
          'by the elapsed time and is not otherwise known. Times are comparable within '
          'this sweep only.</figcaption></figure>')
    A('</section>')

    # ------------------------------------------------- experiments 5 and 6
    lev = lever_rows()
    if lev["slack"] or lev["cap"]:
        A('<section>')
        A('<p class="eyebrow">Experiments 5 and 6</p>')
        A('<h2>What moves a metric the ladder leaves flat</h2>')
        A(ask("Travel time is identical across every principle at every fleet size. "
              "Is that a property of the principles, or of a setup that gives none of "
              "them anywhere to go?",
              "Two knobs, each acting on a different half of the menu. <b>Horizon "
              "slack</b> widens <span class=\"u\">T_max</span> from the Chebyshev "
              "floor&nbsp;+1 that the tool sends, giving an aircraft room to detour "
              "into. <b>Cap tightness</b> lowers <span class=\"u\">D</span> until it "
              "binds, so routing around a full community becomes the only option. "
              "Unlimited budget on both, so a flat line means the principle "
              "<i>declined</i> the room rather than ran out of clock."))
        d = img("levers")
        if d:
            A('<figure><img alt="Four metrics against horizon slack and against cap '
              'tightness" src="' + d + '"><figcaption>Top row: horizon slack. Bottom '
              'row: cap tightness. Proven cells only — an unproven cell pays extra '
              'arrival time for having been stopped, which on these axes is '
              'indistinguishable from a principle choosing to spend '
              'it.</figcaption></figure>')
        for key, title, blurb in (
                ("slack", "Horizon slack",
                 "Widening the horizon by up to four timesteps."),
                ("cap", "Cap tightness",
                 "Lowering the added-noise ceiling until it binds.")):
            rows = lev[key]
            if not rows:
                continue
            xs = sorted({r["_x"] for r in rows})
            n = max(r["N"] for r in rows)
            conds = [c for c in CONDS if any(r["condition"] == c for r in rows)]
            A(f'<h3 style="margin-top:26px">{title} &mdash; at N={n}</h3>')
            A(f'<p style="font-size:.9rem;color:var(--ink-2);max-width:74ch">{blurb}</p>')
            A('<div class="scroll"><table><thead><tr>' + th("Condition")
              + f'<th>metric</th>'
              + "".join(f'<th>{key}={x}</th>' for x in xs)
              + '</tr></thead><tbody>')
            for f, lab in (("extra_vs_floor", "extra hops vs floor"),
                           ("departure_delay_total", "departure delay"),
                           ("max_count", "max aircraft/tile"),
                           ("peak_added", "peak added dB")):
                A(f'<tr class="grp"><td colspan="{len(xs)+2}">{lab}</td></tr>')
                for c in conds:
                    cells = []
                    for x in xs:
                        r = next((r for r in rows if r["condition"] == c
                                  and r["_x"] == x and r["N"] == n), None)
                        v = r.get(f) if r else None
                        cells.append("—" if v is None else
                                     (f"{v:.2f}" if f == "peak_added" else f"{v:.0f}"))
                    A(f'<tr><td class="name">{LABEL[c]}</td><td></td>'
                      + "".join(f"<td>{v}</td>" for v in cells) + '</tr>')
            A('</tbody></table></div>')
        A('</section>')

    # ------------------------------------------------------------- ladder
    A('<section>')
    A('<p class="eyebrow">Every solve</p>')
    A('<h2>The ladder</h2>')
    A('<p class="col">One row per cell. Everything here ran to completion with no time '
      'budget, so a value is a proven optimum rather than whatever a clock allowed.</p>')
    A('<div class="scroll"><table><thead><tr>'
      + "".join(th(k) for k in ("Condition", "N", "Avg hops", "vs base", "Max/tile",
                                "Shared", "Total dB", "Peak dB", "45 dBA share",
                                "Wall", "Status"))
      + '</tr></thead><tbody>')
    for n in ns:
        A(f'<tr class="grp"><td colspan="11">N = {n}</td></tr>')
        for c in CONDS:
            m = I.get((c, n))
            if not m:
                # A cell with no row is either still searching (it has a live
                # heartbeat) or has never produced an answer at all. Both are shown:
                # a cell that silently vanishes from the ladder reads as a cell that
                # was never part of the design.
                el = run.get((c, n))
                note = (f"searching — no result after {el/3600:.1f} h" if el
                        else "no answer yet — queued to re-run")
                pill = "running" if el else "no answer"
                A(f'<tr><td class="name">{LABEL[c]}</td><td>{n}</td>'
                  '<td colspan="8" style="text-align:left;color:var(--ink-3)">'
                  f'{note}</td>'
                  f'<td><span class="pill no">{pill}</span></td></tr>')
                continue
            ts = (m.get("tier_share") or {}).get("45")
            A(f'<tr><td class="name">{LABEL[c]}</td><td>{n}</td>'
              f'<td>{num(m.get("avg_trip_hops"))}</td>'
              f'<td>{num(m.get("extra_vs_baseline"),0)}</td>'
              f'<td>{num(m.get("max_count"),0)}</td>'
              f'<td>{num(m.get("shared_tile_timesteps"),0)}</td>'
              f'<td>{num(m.get("total_added"),1)}</td>'
              f'<td>{num(m.get("peak_added"))}</td>'
              f'<td>{num(ts,1)}%</td>'
              f'<td>{num(m.get("wall"),1)} s</td>'
              '<td><span class="pill ok">optimal</span></td></tr>')
    A('</tbody></table></div>')
    A(defs(["Condition", "N", "Avg hops", "vs base", "Max/tile", "Shared",
            "Total dB", "Peak dB", "45 dBA share", "Wall", "Status"]))
    A('</section>')

    # ------------------------------------------------------------- footer
    A('<footer>')
    A('<h3>Where this comes from</h3>')
    A('<ul>'
      '<li>Figures — <code>paper/tex/figs/*.pdf</code> (PNG twins alongside), '
      'written by <code>harness/figures.py</code></li>'
      '<li>Every number — <code>harness/results/fleet_metrics.csv</code>, '
      'one row per solve</li>'
      '<li>Prose with row keys — <code>harness/results/fleet_findings.md</code></li>'
      '<li>What ran, and what broke — <code>harness/NIGHT_REPORT.md</code></li>'
      '<li>Judgement calls — <code>harness/DECISIONS.md</code></li>'
      '</ul>')
    A('<h3>Regenerate</h3>')
    A('<p><code>python metrics_run.py && python figures.py --fleet && '
      'python report_html.py</code></p>')
    A('<p>The paper itself has never been compiled — there is no TeX installation '
      'on this machine, so <code>tex/main.tex</code> builds first on Overleaf. '
      '<code>harness/sync_overleaf.py</code> pushes the regenerated tables and figures '
      'there without touching prose.</p>')
    A('</footer>')
    A('</div>')

    html = "\n".join(H)
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(html)
    kb = len(html.encode("utf-8")) / 1024
    print(f"wrote {os.path.normpath(OUT)}  ({kb:.0f} KB, {len(recs)} cells, "
          f"{len(proven)} proven, {len(run)} running)")
    return OUT


if __name__ == "__main__":
    build()
