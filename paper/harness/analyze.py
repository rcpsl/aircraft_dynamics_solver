"""Turn the raw jsonl sweeps into the paper's tables.

Writes LaTeX into ../tex/tables/ (never hand-edit those) and a human-readable
summary into ../results/summary.md. Re-runnable at any time: partial sweeps
produce partial tables rather than an error, so this can be run while a sweep is
still going.

usage: python analyze.py
"""
import io
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
TEXDIR = os.path.join(HERE, "..", "tex", "tables")
OUTMD = os.path.join(HERE, "..", "results", "summary.md")
os.makedirs(TEXDIR, exist_ok=True)

LABEL = {"equal": "Equal", "sufficientarian": "Sufficientarian",
         "prioritarian": "Prioritarian", "utilitarian": "Utilitarian",
         "proportional": "Proportional"}
ORDER = ["equal", "sufficientarian", "prioritarian", "utilitarian", "proportional"]


# Sweeps that must NEVER be merged with a longer-budget run of the same configuration.
#
# `reps` measures run-to-run variance at a FIXED budget. Its three repetitions share a
# configuration by construction, so merging collapses them onto one row and the table
# then reports "three identical routings" as a discovery rather than as an artefact of
# its own loader. The whole point of those rows is the budget they were run under.
# The fleet-size study (2026-09-09) is exempt for a different reason. Every one of its
# rows was run to completion with no budget at all, so there is nothing a prior sweep
# could upgrade -- but several of its configurations are byte-identical to a 600 s
# `scaling` cfg, and _bycfg_index matches on exactly that. Left in, the merge would
# quietly seat a 600 s incumbent in an unlimited-budget table, which is the error the
# whole redirection exists to avoid. The exemption blocks it in both directions: these
# files are neither upgraded from, nor used to upgrade.
MERGE_EXEMPT = {"reps", "pilot", "fleet", "fleet_default", "screen", "screen3",
                "fleet_main", "slack",
                "captight", "perm"}


def load(name, raw=False):
    """Rows for a sweep, with stronger re-runs of the same experiment merged in.

    `raw=True` returns exactly what was measured. Use it wherever the BUDGET is the
    subject -- a wall-clock comparison across a row is meaningless if some cells were
    given 600 s and others four hours.
    """
    p = os.path.join(RES, name + ".jsonl")
    if not os.path.exists(p):
        return []
    rows = []
    for line in io.open(p, encoding="utf-8"):
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    if raw or name in MERGE_EXEMPT:
        return rows
    return _upgrade(rows)


# --------------------------------------------------------------------------
# Long-budget merge.
#
# Several configurations were run twice: once at the deployed 600 s budget, and again
# with up to four hours. The long run is strictly better evidence -- same payload, same
# solver, more time -- so every table must use it where it exists. Comparing a 600 s
# incumbent against a four-hour optimum is exactly the error cap_audit.py exists to
# catch, and merging here removes the chance of making it by accident.
#
# The mapping is explicit rather than inferred from `cfg`, because a row does not record
# the free-form `req` overrides that distinguish, say, an ablation control from its
# treatment. Only keys known to name the same experiment are merged.
# --------------------------------------------------------------------------
_RANK = {"optimal": 3, "partial": 2, "fallback": 1}


def _alias(key):
    """Canonical name of the experiment a result key refers to, or None."""
    k = str(key)
    if k.startswith("rescue|"):
        return k[len("rescue|"):]
    for pre, fmt in (("long|", "scale|{1}|communities|{2}"),
                     ("settle|", "scale|{1}|communities|{2}"),
                     ("longfb|", "scale|{1}|{2}|{3}")):
        if k.startswith(pre):
            parts = k.split("|")
            try:
                return fmt.format(*parts)
            except IndexError:
                return None
    return None


_LONG = None
_PLANS = None
_BYCFG = None


def _plans():
    """Every job definition, indexed by key, so a result row can be told whether it
    carried `req` overrides -- which results rows do not record."""
    global _PLANS
    if _PLANS is not None:
        return _PLANS
    import glob
    _PLANS = {}
    for p in glob.glob(os.path.join(HERE, "plans", "*.json")):
        try:
            for j in json.load(open(p, encoding="utf-8"))["jobs"]:
                _PLANS[j["key"]] = j
        except Exception:
            pass
    return _PLANS


def _cfgkey(r):
    """Identity of the EXPERIMENT a row represents, or None if it cannot be pinned
    down. Two rows sharing this key are the same solve run twice.

    Only rows whose plan entry has no `req` overrides qualify: an override changes
    the payload in ways `cfg` does not record (an ablation control and its treatment
    share a cfg but are different experiments), so merging on cfg alone would
    silently conflate them.
    """
    job = _plans().get(str(r.get("key")))
    if job is None or job.get("req"):
        return None
    c = r.get("cfg")
    if not c:
        return None
    return json.dumps({k: c[k] for k in sorted(c)}, sort_keys=True)


def _long_index():
    """Best available row per canonical experiment name, from the long-budget sweeps."""
    global _LONG
    if _LONG is not None:
        return _LONG
    _LONG = {}
    for name in ("longbudget", "settle", "rescue"):
        p = os.path.join(RES, name + ".jsonl")
        if not os.path.exists(p):
            continue
        for line in io.open(p, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            canon = _alias(r.get("key"))
            if canon is None:
                continue
            cur = _LONG.get(canon)
            if cur is None or _better(r, cur):
                _LONG[canon] = r
    return _LONG


def _bycfg_index():
    """Best row across EVERY sweep, keyed by experiment identity.

    Catches the case the alias map cannot: the same configuration queued under two
    different plan names (`bind|equal|10|2.0` and `scale|equal|communities|2.0` are
    one experiment), where one run proved out and the other timed out.
    """
    global _BYCFG
    if _BYCFG is not None:
        return _BYCFG
    import glob
    _BYCFG = {}
    for p in sorted(glob.glob(os.path.join(RES, "*.jsonl"))):
        if os.path.basename(p)[:-6] in MERGE_EXEMPT:
            continue
        for line in io.open(p, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            ck = _cfgkey(r)
            if ck is None:
                continue
            cur = _BYCFG.get(ck)
            if cur is None or _better(r, cur):
                _BYCFG[ck] = r
    return _BYCFG


def _better(a, b):
    """Is row a stronger evidence than row b?

    Status first. Among rows of equal status, prefer the LARGER BUDGET -- not the lower
    arrival penalty.

    Ranking by arrival is wrong for any run carrying a principle objective, because the
    objective is lexicographic: the principle is tier 1 and arrival only tier 2, so a
    search that got further on the principle legitimately pays more arrival. Ranking by
    arrival therefore discards the better answer. It did: at N=24 the four-hour
    Utilitarian run reached 0.58x of control on its own objective against the 600 s run's
    0.84x, but had arrival 96 against 95, so the merge kept the 600 s row and the paper
    under-reported the effect.

    Budget is the safe proxy. Within a run Z3's incumbent improves monotonically, so more
    budget means the search got at least as far on tier 1. Arrival remains the tiebreak
    for rows given the same budget, which is the case where it is the only thing that can
    distinguish them.
    """
    ra = _RANK.get(status_mark(a), 0)
    rb = _RANK.get(status_mark(b), 0)
    if ra != rb:
        return ra > rb
    ba, bb = (a.get("budget_s") or 600), (b.get("budget_s") or 600)
    if ba != bb:
        return ba > bb
    pa, pb = a.get("arrivalPenalty"), b.get("arrivalPenalty")
    if pa is not None and pb is not None and pa != pb:
        return pa < pb
    return False


def _upgrade(rows):
    """Replace any row for which a stronger run of the same experiment exists.

    Two independent matches, because neither alone is sufficient: the alias map
    catches deliberate re-runs (`rescue|X` supersedes `X`), and the cfg index catches
    the same configuration queued under unrelated plan names.
    """
    alias_idx = _long_index()
    cfg_idx = _bycfg_index()
    out = []
    for r in rows:
        best, why = r, None
        alt = alias_idx.get(str(r.get("key")))
        if alt is not None and _better(alt, best):
            best, why = alt, "long-budget re-run"
        ck = _cfgkey(r)
        if ck is not None:
            alt2 = cfg_idx.get(ck)
            if alt2 is not None and _better(alt2, best):
                best, why = alt2, f"same config solved as {alt2.get('key')}"
        if best is r:
            out.append(r)
            continue
        merged = dict(best)
        merged["key"] = r["key"]              # keep the caller's addressing
        merged["upgraded_from"] = status_mark(r)
        merged["upgraded_why"] = why
        out.append(merged)
    return out


def fleet(f):
    """Fleet size for a demand factor, matching payload.build_streams."""
    import math
    d = [max(1, math.floor(c * f + 0.5)) for c in (4, 2, 2)]
    return 2 * sum(d)


def fmt(v, nd=2, dash="--"):
    if v is None:
        return dash
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def tier_share(r):
    """Share of aircraft-timesteps aloft spent over each ambient tier.

    Recomputed from the returned paths using the same active-noise window the
    solver constrained, so it measures where the traffic actually went. This is the
    empirical counterpart to the capacity table: if a tightening cap herds traffic
    toward already-loud communities, it shows up here.
    """
    sys.path.insert(0, HERE)
    import payload as P
    paths = r.get("paths")
    if not paths:
        return None
    cfg = r.get("cfg", {})
    starts, ends, mult = P.build_streams(cfg.get("demand_factor", 1.0),
                                         cfg.get("stream_mode", "individual"))
    tiers = defaultdict(int)
    total = 0
    for i, p in enumerate(paths):
        s0, e0 = starts[i], ends[i]
        if s0 == e0:
            continue
        t_fm = next((t for t in range(len(p)) if p[t] != s0), None)
        if t_fm is None:
            continue
        t_arr = next((t for t in range(len(p)) if p[t] == e0), len(p) - 1)
        for t in range(t_fm, t_arr + 1):
            tiers[P.BASELINE[p[t] - 1]] += mult[i]
            total += mult[i]
    if not total:
        return None
    return {b: 100.0 * tiers[b] / total for b in (45, 55, 65)}, total


def _counts(r):
    """Per-community, per-timestep weighted active-aircraft counts, from stored paths.

    Rebuilds exactly the active-noise window the solver constrained, so anything
    derived from this is a property of the routing the solver actually returned.
    """
    sys.path.insert(0, HERE)
    import payload as P
    paths = r.get("paths")
    if not paths:
        return None, 0
    cfg = r.get("cfg", {})
    starts, ends, mult = P.build_streams(cfg.get("demand_factor", 1.0),
                                         cfg.get("stream_mode", "individual"))
    T = len(paths[0])
    counts = [[0] * T for _ in range(P.M)]
    for i, p in enumerate(paths):
        s0, e0 = starts[i], ends[i]
        if s0 == e0:
            continue
        t_fm = next((t for t in range(T) if p[t] != s0), None)
        if t_fm is None:
            continue
        t_arr = next((t for t in range(T) if p[t] == e0), T - 1)
        for t in range(t_fm, t_arr + 1):
            counts[p[t] - 1][t] += mult[i]
    return counts, T


def principle_metric(r, principle):
    """The quantity THIS principle exists to reduce, recomputed from the routing.

    Previously the ablation reported summed added dB for every principle except
    Prioritarian. That is not what three of the five optimise, and for Proportional it
    was actively misleading: the control payload omits `proximityWeights` entirely (the
    dashboard emits them only when optimizeProximity is set), so the priced objective is
    uncomputable from the solver's own reply and total added dB was substituted. Total
    added dB is not what Proportional minimises, and it is what produced a sign flip
    (-53.5% at N=16 against +45.3% at N=24) that the table then read as evidence of
    binding.

    The price vector is deterministic given the ranking, so it can be rebuilt offline
    and applied to BOTH runs' stored paths. No new solves are needed.

    Returns (value, unit) or (None, None).
    """
    sys.path.insert(0, HERE)
    import math
    import payload as P
    counts, T = _counts(r)
    if counts is None:
        return None, None
    cfg = r.get("cfg", {})

    def dB(m, n):
        return 0.0 if n <= 0 else 10 * math.log10(
            1 + n * 10 ** ((P.AIRCRAFT_DB - P.BASELINE[m]) / 10))

    if principle == "equal":
        # The spread it caps: worst inter-community gap at any one timestep.
        return max(max(dB(m, counts[m][t]) for m in range(P.M))
                   - min(dB(m, counts[m][t]) for m in range(P.M))
                   for t in range(T)), "dB spread"
    if principle == "sufficientarian":
        # The level it caps: worst single community.
        return max(dB(m, counts[m][t]) for m in range(P.M) for t in range(T)), "dB peak"
    if principle == "prioritarian":
        import plans as PL
        prot = cfg.get("protected") or list(PL.PROT_BURDEN)
        return sum(dB(i, counts[i][t]) for i in prot for t in range(T)), "dB protected"
    if principle == "utilitarian":
        return sum(dB(m, counts[m][t]) for m in range(P.M) for t in range(T)), "dB total"
    if principle == "proportional":
        pw = P.proportional_weights(cfg.get("prop_order", P.DEFAULT_PROP_ORDER),
                                    cfg.get("prop_population", True))
        return sum(pw[m] * dB(m, counts[m][t])
                   for m in range(P.M) for t in range(T)), "priced dB"
    return None, None


def recompute_noise(r, subset=None):
    """Summed added dB over a subset of communities, recomputed from the paths.

    Needed because the solver only reports an objective's value when that objective
    was switched ON, so an ablation control has no `protectedNoise` field to compare
    against. Rebuilds the occupancy matrix over the active-noise window exactly as
    _active_output_matrices does, then applies the same dB curve.
    """
    sys.path.insert(0, HERE)
    import math
    import payload as P
    paths = r.get("paths")
    if not paths:
        return None
    cfg = r.get("cfg", {})
    starts, ends, mult = P.build_streams(cfg.get("demand_factor", 1.0),
                                         cfg.get("stream_mode", "individual"))
    T = len(paths[0])
    counts = [[0] * T for _ in range(P.M)]
    for i, p in enumerate(paths):
        s0, e0 = starts[i], ends[i]
        if s0 == e0:
            continue
        t_fm = next((t for t in range(T) if p[t] != s0), None)
        if t_fm is None:
            continue
        t_arr = next((t for t in range(T) if p[t] == e0), T - 1)
        for t in range(t_fm, t_arr + 1):
            counts[p[t] - 1][t] += mult[i]
    ms = range(P.M) if subset is None else [s - 1 for s in subset]
    tot = 0.0
    for m in ms:
        b = P.BASELINE[m]
        for t in range(T):
            n = counts[m][t]
            if n:
                tot += 10 * math.log10(1 + n * 10 ** ((P.AIRCRAFT_DB - b) / 10))
    return round(tot, 4)


def status_mark(r):
    """How the answer should be read. Every distinction here is load-bearing.

    Note especially that phase-1 can fail two very different ways. `noise_cap`,
    `unreachable` and `structural` are PROOFS that no routing exists -- the solver
    derived them without search. `timeout` is the absence of an answer, and calling it
    "infeasible" would assert exactly what was not established.
    """
    s = str(r.get("status", "?"))
    if s in ("phase1_noise_cap", "phase1_unreachable", "phase1_structural"):
        return "infeasible"
    if s.startswith("phase1_"):
        return "unsettled"                # phase1_timeout: feasibility never decided
    if s.startswith("phase2_failed"):
        return "fallback"
    if s == "NO_OUTPUT":
        return "killed"
    return r.get("optimality", "?")       # "optimal" | "partial"


MD = []


def md(*a):
    MD.append(" ".join(str(x) for x in a))


# ---------------------------------------------------------------- scaling
def table_scaling():
    # Raw: this table compares WALL TIME across a row, so every cell must have had
    # the same budget. Merged rows would mix 600 s and four-hour runs.
    rows = [r for r in load("scaling", raw=True) if r["cfg"].get("who", "communities") == "communities"]
    by = {(r["cfg"]["principle"], r["cfg"]["demand_factor"]): r for r in rows}
    factors = sorted({r["cfg"]["demand_factor"] for r in rows})
    if not factors:
        return

    md("\n## Scaling: solve time and outcome vs fleet size (who = Communities)\n")
    md("| principle | " + " | ".join(f"N={fleet(f)}" for f in factors) + " |")
    md("|---" * (len(factors) + 1) + "|")

    tex = [r"\begin{table}[t]", r"\centering",
           r"\caption{Wall-clock solve time in seconds against fleet size $N$, "
           r"with the outcome of each solve. \emph{opt} = proven optimal; "
           r"\emph{par} = objective applied but optimality unproven when the "
           r"\SI{600}{\second} budget expired; \emph{fb} = phase~2 produced nothing "
           r"and the route shown ignores the principle.}",
           r"\label{tab:scaling}",
           r"\begin{tabular}{l" + "r" * len(factors) + r"}", r"\toprule",
           "Principle & " + " & ".join(f"$N{{=}}{fleet(f)}$" for f in factors) + r" \\",
           r"\midrule"]

    for p in ORDER:
        cells_md, cells_tex = [], []
        for f in factors:
            r = by.get((p, f))
            if r is None:
                cells_md.append("--"); cells_tex.append("--"); continue
            w = r.get("wall", r.get("runner_wall"))
            st = status_mark(r)
            short = {"optimal": "opt", "partial": "par", "fallback": "fb",
                     "infeasible": "unsat", "killed": "kill", "unsettled": "??"}.get(st, st)
            cells_md.append(f"{w:.0f}s {short}")
            cells_tex.append(f"{w:.0f}\\,{{\\scriptsize {short}}}")
        md(f"| {LABEL[p]} | " + " | ".join(cells_md) + " |")
        tex.append(f"{LABEL[p]} & " + " & ".join(cells_tex) + r" \\")

    tex += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    io.open(os.path.join(TEXDIR, "scaling.tex"), "w", encoding="utf-8", newline="\n").write("\n".join(tex) + "\n")


# ---------------------------------------------------------------- fairness metrics
def table_metrics():
    rows = [r for r in load("scaling") if r["cfg"].get("who", "communities") == "communities"]
    by = {(r["cfg"]["principle"], r["cfg"]["demand_factor"]): r for r in rows}
    factors = sorted({r["cfg"]["demand_factor"] for r in rows})
    if not factors:
        return

    md("\n## What each principle actually delivers\n")
    md("Peak = worst single community's added noise. Spread = largest gap between "
       "communities at one timestep (what Equal caps). Total = summed added dB over "
       "all communities and timesteps (what Utilitarian minimises). Hops = total "
       "aircraft-timesteps aloft, against the shortest-path floor.\n")
    md("| principle | N | peak dB | spread dB | total dB | hops/floor | tiles used | outcome |")
    md("|---|---|---|---|---|---|---|---|")
    for f in factors:
        for p in ORDER:
            r = by.get((p, f))
            if r is None or "peakAddedDB" not in r:
                continue
            md(f"| {LABEL[p]} | {r['N']} | {fmt(r['peakAddedDB'])} | "
               f"{fmt(r['peakSpreadDB'])} | {fmt(r['totalAddedDB'],1)} | "
               f"{r['totalTripHops']}/{r['totalFloorHops']} | "
               f"{r['stationsTouched']} | {status_mark(r)} |")

    # LaTeX: the headline comparison at the workshop's default demand.
    f0 = 1.0 if 1.0 in factors else factors[len(factors) // 2]
    tex = [r"\begin{table}[t]", r"\centering",
           r"\caption{The five principles at the default demand ($N{=}%d$). "
           r"Peak is the worst-affected community's added noise; spread is the "
           r"largest inter-community gap at one timestep; total is summed added "
           r"decibels over all communities and timesteps. Hops counts "
           r"aircraft-timesteps aloft against the shortest-path floor.}"
           % fleet(f0),
           r"\label{tab:principles}",
           r"\begin{tabular}{lrrrrr}", r"\toprule",
           r"Principle & Peak & Spread & Total & Hops & Outcome \\",
           r" & (dB) & (dB) & (dB) & (floor) & \\",
           r"\midrule"]
    for p in ORDER:
        r = by.get((p, f0))
        if r is None or "peakAddedDB" not in r:
            continue
        tex.append(f"{LABEL[p]} & {r['peakAddedDB']:.2f} & {r['peakSpreadDB']:.2f} & "
                   f"{r['totalAddedDB']:.1f} & {r['totalTripHops']} ({r['totalFloorHops']}) & "
                   f"{status_mark(r)} \\\\")
    tex += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    io.open(os.path.join(TEXDIR, "principles.tex"), "w", encoding="utf-8", newline="\n").write("\n".join(tex) + "\n")


# ---------------------------------------------------------------- collapse
def table_collapse():
    rows = load("scaling")
    by = {(r["cfg"]["principle"], r["cfg"]["demand_factor"]): r
          for r in rows if r["cfg"].get("who", "communities") == "communities"}
    factors = sorted({f for (p, f) in by if p in ("equal", "sufficientarian")})
    if not factors:
        return
    md("\n## Equal vs Sufficientarian: identical constraint sets below N=25\n")
    md("| N | Equal D/U | Suff D/U | same paths? | Equal peak | Suff peak | "
       "Equal arrival | Suff arrival |")
    md("|---|---|---|---|---|---|---|---|")
    for f in factors:
        e, s = by.get(("equal", f)), by.get(("sufficientarian", f))
        if not e or not s or "paths" not in e or "paths" not in s:
            continue
        md(f"| {e['N']} | {e['D']}/{e['U']} | {s['D']}/{s['U']} | "
           f"{'YES' if e['paths']==s['paths'] else 'no'} | "
           f"{fmt(e['peakAddedDB'])} | {fmt(s['peakAddedDB'])} | "
           f"{e.get('arrivalPenalty')} | {s.get('arrivalPenalty')} |")


# ---------------------------------------------------------------- ablation
def table_ablation():
    rows = load("ablation")
    if not rows:
        return
    by = {r["key"]: r for r in rows}
    md("\n## Objective ablation: does the principle move the routing?\n")
    md("Control is the identical payload with the principle's objective term "
       "removed. Soft T and the arrival tie-break are unchanged, so any difference "
       "is attributable to the principle alone.\n")
    md("The 'own metric' columns are each principle's OWN objective, recomputed from "
       "the returned paths (the solver reports no value for an objective that is "
       "switched off). Equal: worst inter-community spread. Sufficientarian: worst "
       "single community. Prioritarian: summed dB over its protected set. "
       "Utilitarian: summed dB over all communities. Proportional: the priced sum "
       "with its own weight vector, rebuilt offline because the control payload "
       "omits it.\n")
    md("`arrival` is the only quantity BOTH runs optimise. Equal arrival with a "
       "differing path means the two answers are interchangeable and the difference "
       "is a tie-break, not a response to the principle.\n")
    md("| principle | N | paths differ? | arrival on/off | peak on | peak off | "
       "own metric on | own metric off | change |")
    md("|---|---|---|---|---|---|---|---|---|")
    import plans as PL
    TEXROWS = []
    for f in (0.5, 1.0, 1.5):
        for p in ORDER:
            on, off = by.get(f"abl|{p}|on|{f}"), by.get(f"abl|{p}|off|{f}")
            if not on or not off or "peakAddedDB" not in on or "peakAddedDB" not in off:
                continue
            same = on.get("paths") == off.get("paths")
            von, _unit = principle_metric(on, p)
            voff, _unit = principle_metric(off, p)
            if von is None or voff is None:
                chg = "--"
            elif voff == 0:
                chg = "0 -> 0" if von == 0 else "n/a"
            else:
                chg = f"{100.0*(von-voff)/voff:+.1f}%"
            ap = f"{on.get('arrivalPenalty','--')}/{off.get('arrivalPenalty','--')}"
            md(f"| {LABEL[p]} | {on['N']} | {'no' if same else 'YES'} | {ap} | "
               f"{fmt(on['peakAddedDB'])} | {fmt(off['peakAddedDB'])} | "
               f"{fmt(von,2)} | {fmt(voff,2)} | {chg} |")
            TEXROWS.append((p, on["N"], on.get("arrivalPenalty"),
                            off.get("arrivalPenalty"), von, voff, chg, on, off))

    # LaTeX across ALL THREE demands. Reporting one demand made the paper's central
    # claim an n=1 result when n=3 was already computed, and it happened to show the
    # demand most favourable to the two principles that bind. Nine paired proven
    # comparisons carry the "three of five bind on nothing" claim; the two that do bind
    # are shown decaying (Utilitarian) and failing (Proportional) as demand rises.
    tex = [r"\begin{table}[t]", r"\centering",
           r"\caption{Objective ablation at three demands: each principle against the "
           r"identical payload with its own term removed. \emph{Arrival} is the "
           r"lexicographic tie-break, the only quantity every run optimises. "
           r"\emph{Metric} is that principle's \emph{own} objective, recomputed from "
           r"the returned paths --- spread for Equal, peak for Sufficientarian, "
           r"protected-set noise for Prioritarian, summed noise for Utilitarian, priced "
           r"noise for Proportional --- so the columns are not commensurable across "
           r"rows and are given as the on/off ratio. Equal, Sufficientarian and "
           r"Prioritarian leave arrival unchanged at every demand: nine paired "
           r"comparisons, all proven, in which the principle bought nothing the solver "
           r"was optimising. Utilitarian and Proportional bind at every demand, and "
           r"pay for it in arrival time. All treatment cells were given a four-hour "
           r"budget and all controls are proven optima, so the columns are comparable: "
           r"Utilitarian's effect weakens mildly with demand while Proportional's "
           r"strengthens. Treatment rows are unproven incumbents, so each ratio is an "
           r"upper bound on the true effect.}",
           r"\label{tab:ablation}",
           r"\begin{tabular}{l rr rr rr}", r"\toprule",
           r"\multirow{2}{*}{Principle} & \multicolumn{2}{c}{$N{=}8$} & "
           r"\multicolumn{2}{c}{$N{=}16$} & \multicolumn{2}{c}{$N{=}24$} \\",
           r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}",
           r" & arr. & metric & arr. & metric & arr. & metric \\",
           r"\midrule"]

    def _cell(rec):
        """(arrival on/off, metric ratio) for one principle at one demand."""
        if rec is None:
            return "--", "--"
        p, n, apon, apoff, von, voff, chg, on, off = rec
        arr = f"{apon}/{apoff}" if apon == apoff else f"\\textbf{{{apon}}}/{apoff}"
        if von is None or voff is None:
            return arr, "--"
        if abs(voff) < 1e-9:
            met = "0/0" if abs(von) < 1e-9 else "n/a"
        else:
            met = f"${von/voff:.2f}\\times$"
        return arr, met

    idx = {(r[0], r[1]): r for r in TEXROWS}
    NS = sorted({r[1] for r in TEXROWS})[:3]
    for p in ORDER:
        cells = []
        for n in NS:
            cells.extend(_cell(idx.get((p, n))))
        tex.append(f"{LABEL[p]} & " + " & ".join(cells) + r" \\")
    tex += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    io.open(os.path.join(TEXDIR, "ablation.tex"), "w", encoding="utf-8",
            newline="\n").write("\n".join(tex) + "\n")


# ---------------------------------------------------------------- caps
def table_caps():
    rows = load("caps")
    if not rows:
        return
    by = defaultdict(dict)
    for r in rows:
        by[r["cfg"]["principle"]][r["cfg"]["limit"]] = r
    md("\n## Cap tightening: where does a tightening cap send the traffic?\n")
    md("Tier shares are the percentage of aircraft-timesteps aloft spent over "
       "communities of each ambient level, recomputed from the returned paths. "
       "The map has 8 tiles at 45 dBA, 12 at 55 dBA (four of them unclaimed "
       "create-your-own slots at the default level) and 5 at 65 dBA.\n")
    md("| principle | limit dB | outcome | T_min | peak dB | 45 dBA % | 55 dBA % "
       "| 65 dBA % | hops | wall |")
    md("|---|---|---|---|---|---|---|---|---|---|")
    tex = [r"\begin{table}[t]", r"\centering",
           r"\caption{Tightening the Sufficientarian cap $D$ at $N{=}16$. Tier shares "
           r"are the percentage of aircraft-timesteps aloft spent over communities of "
           r"each ambient level. The cap does \emph{not} redistribute traffic between "
           r"tiers --- the shares do not trend with $D$ --- but it does lengthen the "
           r"schedule: at $D{=}4$ the minimum horizon rises from 5 to 7 and flight time "
           r"from 44 to 48 aircraft-timesteps. At $D{=}3$ a \SI{45}{\dBA} vertiport can "
           r"hold no aircraft at all and no routing exists.}",
           r"\label{tab:caps}", r"\begin{tabular}{rlrrrr}", r"\toprule",
           r"$D$ (dB) & Outcome & \SI{45}{\dBA} & \SI{55}{\dBA} & \SI{65}{\dBA} & Hops \\",
           r"\midrule"]
    for p in ("sufficientarian", "equal"):
        for lim in sorted(by[p]):
            r = by[p][lim]
            ts = tier_share(r)
            sh = ts[0] if ts else {}
            md(f"| {LABEL[p]} | {lim} | {status_mark(r)} | {r.get('T_min','--')} | "
               f"{fmt(r.get('peakAddedDB'))} | "
               f"{fmt(sh.get(45),1)} | {fmt(sh.get(55),1)} | {fmt(sh.get(65),1)} | "
               f"{r.get('totalTripHops','--')} | {fmt(r.get('wall'),0)}s |")
            if r.get("detail"):
                md(f"|  |  | _{r['detail'][:200]}_ |  |  |  |  |  |  |")
            if p == "sufficientarian":
                if ts:
                    tex.append(f"{lim} & {status_mark(r)} & {sh[45]:.1f} & {sh[55]:.1f} & "
                               f"{sh[65]:.1f} & {r['totalTripHops']} \\\\")
                else:
                    tex.append(f"{lim} & {status_mark(r)} & \\multicolumn{{4}}{{c}}{{"
                               f"\\emph{{no feasible routing}}}} \\\\")
    tex += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    io.open(os.path.join(TEXDIR, "caps.tex"), "w", encoding="utf-8", newline="\n").write("\n".join(tex) + "\n")


# ---------------------------------------------------------------- protected sets
def table_prior():
    rows = load("prior_sets")
    if not rows:
        return
    md("\n## Prioritarian: does the protected set matter?\n")
    md("| set | N | protectedNoise | peak dB | outcome | wall |")
    md("|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda r: (r["key"].split("|")[1], r["cfg"]["demand_factor"])):
        md(f"| {r['key'].split('|')[1]} | {r.get('N','--')} | "
           f"{fmt(r.get('protectedNoise'))} | {fmt(r.get('peakAddedDB'))} | "
           f"{status_mark(r)} | {fmt(r.get('wall'),0)}s |")


# ---------------------------------------------------------------- reps
def table_reps():
    rows = load("reps")
    if not rows:
        return
    by = defaultdict(list)
    for r in rows:
        by[r["cfg"]["principle"]].append(r)
    md("\n## Run-to-run variance (identical payload)\n")
    md("| principle | walls | identical routings? |")
    md("|---|---|---|")
    for p, rs in by.items():
        walls = [r.get("wall") for r in rs]
        paths = [json.dumps(r.get("paths")) for r in rs if "paths" in r]
        same = len(set(paths)) <= 1 if paths else None
        md(f"| {LABEL.get(p,p)} | {', '.join(f'{w:.0f}s' for w in walls if w)} | "
           f"{'yes' if same else 'NO'} |")


def table_tiers():
    """Where each PRINCIPLE flies. This, not the cap sweep, is where the decibel
    metric's pull toward already-loud communities actually shows up."""
    rows = [r for r in load("scaling")
            if r["cfg"].get("who", "communities") == "communities" and r.get("paths")]
    if not rows:
        return
    by = {(r["cfg"]["principle"], r["cfg"]["demand_factor"]): r for r in rows}
    factors = sorted({r["cfg"]["demand_factor"] for r in rows})

    md("\n## Where each principle flies (share of flight time by ambient tier)\n")
    md("| principle | N | 45 dBA % | 55 dBA % | 65 dBA % | total dB | outcome |")
    md("|---|---|---|---|---|---|---|")
    for f in factors:
        for p in ORDER:
            r = by.get((p, f))
            if not r:
                continue
            ts = tier_share(r)
            if not ts:
                continue
            s = ts[0]
            md(f"| {LABEL[p]} | {r['N']} | {s[45]:.1f} | {s[55]:.1f} | {s[65]:.1f} | "
               f"{r['totalAddedDB']:.1f} | {status_mark(r)} |")

    # LaTeX at N=16 only -- the one demand where all five reach a PROVEN optimum, so
    # the ordering is a property of the objectives rather than of where Z3 stopped.
    f0 = 1.0 if 1.0 in factors else factors[0]
    tex = [r"\begin{table}[t]", r"\centering",
           r"\caption{Share of flight time spent over communities of each ambient "
           r"level, at $N{=}16$. The \SI{65}{\dBA} share is $27.3\%$ for every "
           r"principle: it is pinned by where the vertiports sit, not chosen. What the "
           r"objectives move is the quiet/mid split --- Utilitarian flies least over "
           r"the \SI{45}{\dBA} communities and correspondingly most over the "
           r"\SI{55}{\dBA} ones. Utilitarian and Proportional are best-found rather "
           r"than proven optima; the other three are proven.}",
           r"\label{tab:tiers}", r"\begin{tabular}{lrrrr}", r"\toprule",
           r"Principle & \SI{45}{\dBA} & \SI{55}{\dBA} & \SI{65}{\dBA} & Total \\",
           r" & (\%) & (\%) & (\%) & (dB) \\", r"\midrule"]
    for p in ORDER:
        r = by.get((p, f0))
        if not r:
            continue
        ts = tier_share(r)
        if not ts:
            continue
        s = ts[0]
        tex.append(f"{LABEL[p]} & {s[45]:.1f} & {s[55]:.1f} & {s[65]:.1f} & "
                   f"{r['totalAddedDB']:.1f} \\\\")
    tex += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    io.open(os.path.join(TEXDIR, "tiers.tex"), "w", encoding="utf-8", newline="\n").write("\n".join(tex) + "\n")


def table_grid4():
    """Second instance (no diagonal flight): do the Sec. IV findings replicate?"""
    rows = load("grid4")
    if not rows:
        return
    by = {r["key"]: r for r in rows}
    g8 = {(r["cfg"]["principle"], r["cfg"]["demand_factor"]): r
          for r in load("scaling")
          if r["cfg"].get("who", "communities") == "communities"}

    md("\n## Second instance: grid4 (von Neumann adjacency, no diagonal flight)\n")
    md("Mean out-degree falls 6.8 -> 4.2 and the minimum horizon rises 5 -> 7. "
       "Same city, same demand, same principles.\n")
    md("| principle | N | peak | spread | total dB | hops | 45 dBA % | 65 dBA % | "
       "arrival | wall | outcome |")
    md("|---|---|---|---|---|---|---|---|---|---|---|")
    for f in (0.5, 1.0, 1.5):
        for p in ORDER:
            r = by.get(f"g4|{p}|{f}")
            if not r or "peakAddedDB" not in r:
                continue
            ts = tier_share(r)
            s = ts[0] if ts else {}
            md(f"| {LABEL[p]} | {r['N']} | {fmt(r['peakAddedDB'])} | "
               f"{fmt(r['peakSpreadDB'])} | {fmt(r['totalAddedDB'],1)} | "
               f"{r['totalTripHops']} | {fmt(s.get(45),1)} | {fmt(s.get(65),1)} | "
               f"{r.get('arrivalPenalty','--')} | {fmt(r.get('wall'),0)}s | "
               f"{status_mark(r)} |")

    md("\n### Replication checks\n")
    # 1. collapse
    ok = []
    for f in (0.5, 1.0, 1.5):
        e, s = by.get(f"g4|equal|{f}"), by.get(f"g4|sufficientarian|{f}")
        if e and s:
            ok.append((e["N"], e.get("arrivalPenalty"), s.get("arrivalPenalty"),
                       e.get("paths") == s.get("paths")))
    md("**Collapse (Equal vs Sufficientarian).** " + "; ".join(
        f"N={n}: arrival {a}/{b}, same paths {sp}" for n, a, b, sp in ok) or "no data")
    # 2. peak == spread
    n = sum(1 for r in rows if "peakAddedDB" in r)
    eq = sum(1 for r in rows if "peakAddedDB" in r
             and abs(r["peakAddedDB"] - r["peakSpreadDB"]) < 1e-9)
    md(f"\n**Zero-noise community.** peak == spread in {eq}/{n} grid4 solves.")
    # 3. prioritarian inertness
    lines = []
    for k in sorted(by):
        if "prioritarian" in k or "prot" in k:
            lines.append(f"{k}={by[k].get('protectedNoise')}")
    md(f"\n**Prioritarian protected noise.** " + ", ".join(lines))
    on, off = by.get("g4|prioritarian|1.0"), by.get("g4abl|prioritarian|off|1.0")
    if on and off:
        md(f"\nAblation at N=16: arrival {on.get('arrivalPenalty')}/"
           f"{off.get('arrivalPenalty')}, protected noise "
           f"{on.get('protectedNoise')} vs recomputed "
           f"{recompute_noise(off, [i+1 for i in __import__('plans').PROT_BURDEN])}.")
    # 4. decibel gradient
    md("\n**Decibel gradient (share of flight time over 45 dBA communities).**\n")
    md("| N | " + " | ".join(LABEL[p] for p in ORDER) + " |")
    md("|---" * 6 + "|")
    for f in (0.5, 1.0, 1.5):
        cells = []
        n_ = None
        for p in ORDER:
            r = by.get(f"g4|{p}|{f}")
            ts = tier_share(r) if r else None
            n_ = r["N"] if r else n_
            cells.append(f"{ts[0][45]:.1f}" if ts else "--")
        md(f"| {n_} | " + " | ".join(cells) + " |")


def table_detour():
    """How far from the shortest path do these routings actually go?

    Every solve stores per-aircraft flight length (tripHops) and the BFS shortest-path
    floor for that origin-destination pair (tripFloorHops). The gap between them is
    the detour the fairness objective bought. If most aircraft fly the shortest path
    or one hop off it, then whatever the principles are doing they are doing it in a
    narrow band around the direct route -- which bounds how much any of this can
    matter.
    """
    rows = [r for r in load("scaling")
            if r["cfg"].get("who", "communities") == "communities"
            and r.get("tripHops") and r.get("tripFloorHops")]
    if not rows:
        return
    md("\n## How far from the shortest path?\n")
    md("Per-aircraft detour = flight length minus that aircraft's BFS shortest-path "
       "floor, in hops. Aggregated over every aircraft in every run of a principle "
       "(all fleet sizes, who = Communities).\n")
    md("| principle | aircraft | on shortest path | +1 hop | +2 | +3 or more | "
       "mean detour | fleet detour |")
    md("|---|---|---|---|---|---|---|---|")
    tex = [r"\begin{table}[t]", r"\centering",
           r"\caption{Distance from the shortest path. Each aircraft's detour is its "
           r"flight length minus the breadth-first shortest-path floor for its own "
           r"origin--destination pair, pooled over all fleet sizes. The three "
           r"principles that bind on nothing fly every aircraft on a shortest path; "
           r"the two that bind buy their fairness with detours of one to three hops "
           r"on a minority of aircraft.}",
           r"\label{tab:detour}", r"\begin{tabular}{lrrrrr}", r"\toprule",
           r"Principle & Aircraft & Shortest & $+1$ & $+2$ & $\ge{+}3$ \\",
           r" & & (\%) & (\%) & (\%) & (\%) \\", r"\midrule"]
    for p in ORDER:
        det = []
        for r in rows:
            if r["cfg"]["principle"] != p:
                continue
            for h, fl in zip(r["tripHops"], r["tripFloorHops"]):
                if isinstance(fl, (int, float)) and fl > 0:
                    det.append(h - fl)
        if not det:
            continue
        n = len(det)
        b = [sum(1 for d in det if d <= 0), sum(1 for d in det if d == 1),
             sum(1 for d in det if d == 2), sum(1 for d in det if d >= 3)]
        pc = [100.0 * x / n for x in b]
        md(f"| {LABEL[p]} | {n} | {pc[0]:.1f}% | {pc[1]:.1f}% | {pc[2]:.1f}% | "
           f"{pc[3]:.1f}% | {sum(det)/n:.2f} | {sum(det)} hops |")
        tex.append(f"{LABEL[p]} & {n} & {pc[0]:.1f} & {pc[1]:.1f} & {pc[2]:.1f} & "
                   f"{pc[3]:.1f} \\\\")
    tex += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    io.open(os.path.join(TEXDIR, "detour.tex"), "w", encoding="utf-8",
            newline="\n").write("\n".join(tex) + "\n")


def _min_at_peak(r):
    """Added dB at the QUIETEST community, at the timestep of worst noise, plus how
    many communities are occupied then.

    This is the quantity Proposition 1 turns on: while it is zero the disparity cap
    and the absolute cap are the same constraint. Recomputed from paths so it can be
    applied to runs recorded before the field existed.
    """
    sys.path.insert(0, HERE)
    import math
    import payload as P
    paths = r.get("paths")
    if not paths:
        return None
    cfg = r.get("cfg", {})
    starts, ends, mult = P.build_streams(cfg.get("demand_factor", 1.0),
                                         cfg.get("stream_mode", "individual"))
    T = len(paths[0])
    counts = [[0] * T for _ in range(P.M)]
    for i, p in enumerate(paths):
        s0, e0 = starts[i], ends[i]
        if s0 == e0:
            continue
        t_fm = next((t for t in range(T) if p[t] != s0), None)
        if t_fm is None:
            continue
        t_arr = next((t for t in range(T) if p[t] == e0), T - 1)
        for t in range(t_fm, t_arr + 1):
            counts[p[t] - 1][t] += mult[i]
    db = [[10 * math.log10(1 + counts[m][t] * 10 ** ((P.AIRCRAFT_DB - P.BASELINE[m]) / 10))
           for t in range(T)] for m in range(P.M)]
    tpk = max(range(T), key=lambda t: max(db[m][t] for m in range(P.M)))
    col = [db[m][tpk] for m in range(P.M)]
    return {"t": tpk, "max": max(col), "min": min(col),
            "occupied": sum(1 for v in col if v > 0)}


def table_binding():
    """Do Equal and Sufficientarian ever bind, and do they ever differ?"""
    rows = load("binding")
    if not rows:
        return
    by = {r["key"]: r for r in rows}

    md("\n## Do the Equal / Sufficientarian caps ever bind?\n")
    md("Control is the identical payload with both caps opened to 30 dB. Both runs "
       "carry the soft-T arrival objective, so a HIGHER arrival penalty under the cap "
       "proves the cap excluded the unconstrained optimum.\n")
    md("| principle | N | limit | outcome | arrival (cap/open) | binds? | peak | "
       "hops | T_min |")
    md("|---|---|---|---|---|---|---|---|---|")
    for f in (1.0, 2.0):
        for p in ("equal", "sufficientarian"):
            ctl = by.get(f"bind|{p}|wide|{f}")
            base = ctl.get("arrivalPenalty") if ctl else None
            for lim in (3, 4, 5, 6, 8, 10):
                r = by.get(f"bind|{p}|{lim}|{f}")
                if not r:
                    continue
                ap = r.get("arrivalPenalty")
                sm = status_mark(r)
                if sm == "infeasible":
                    verdict = "**no routing exists**"
                elif sm in ("unsettled", "killed", "fallback"):
                    verdict = "_unsettled_"
                elif ap is None or base is None:
                    verdict = "--"
                elif ap > base:
                    verdict = f"**YES (+{ap-base})**"
                else:
                    verdict = "no"
                md(f"| {LABEL[p]} | {r.get('N','--')} | {lim} | {status_mark(r)} | "
                   f"{ap}/{base} | {verdict} | {fmt(r.get('peakAddedDB'))} | "
                   f"{r.get('totalTripHops','--')} | {r.get('T_min','--')} |")

    md("\n### Can Equal and Sufficientarian be made to differ?\n")
    md("They coincide exactly while some community sits at zero added noise "
       "(Proposition 1). `min@peak` is the quietest community's added noise at the "
       "worst timestep; `occupied` counts communities with any noise then.\n")
    md("| N | limit | principle | D/U sent | min@peak | occupied/25 | max@peak | "
       "arrival | outcome |")
    md("|---|---|---|---|---|---|---|---|---|")
    for f in (3.0, 4.0):
        for lim in (5, 8):
            for p in ("equal", "sufficientarian"):
                r = by.get(f"sat|{p}|{lim}|{f}")
                if not r:
                    continue
                mp = _min_at_peak(r)
                md(f"| {r.get('N','--')} | {lim} | {LABEL[p]} | {r.get('D')}/{r.get('U')} | "
                   f"{fmt(mp['min'],3) if mp else '--'} | "
                   f"{mp['occupied'] if mp else '--'}/25 | "
                   f"{fmt(mp['max'],2) if mp else '--'} | "
                   f"{r.get('arrivalPenalty','--')} | {status_mark(r)} |")


def _occupancy(r):
    """Aircraft-timesteps each community carries, as a 25-vector.

    Comparing principles by their PATH LISTS is misleading: relabelling two
    interchangeable aircraft changes every path without changing the map anyone sees.
    Occupancy is invariant to that relabelling and is what the noise, and therefore
    the fairness, actually depends on.
    """
    sys.path.insert(0, HERE)
    import payload as P
    paths = r.get("paths")
    if not paths:
        return None
    cfg = r.get("cfg", {})
    starts, ends, mult = P.build_streams(cfg.get("demand_factor", 1.0),
                                         cfg.get("stream_mode", "individual"))
    occ = [0] * P.M
    for i, p in enumerate(paths):
        s0, e0 = starts[i], ends[i]
        if s0 == e0:
            continue
        t_fm = next((t for t in range(len(p)) if p[t] != s0), None)
        if t_fm is None:
            continue
        t_arr = next((t for t in range(len(p)) if p[t] == e0), len(p) - 1)
        for t in range(t_fm, t_arr + 1):
            occ[p[t] - 1] += mult[i]
    return occ


def table_distinct():
    """Do different principles produce different routings, and by how much?

    Reported as the L1 distance between occupancy vectors, normalised by total flight
    time, so 0 means 'the same map' and 1 means 'no community carries traffic in both'.
    """
    # Keying by principle alone is WRONG on any sweep that contains more than one run
    # per principle. grid4.jsonl holds treatments (`g4|...`), ablation controls
    # (`g4abl|...|off|...`) and protected-set variants (`g4prot|...`); with a
    # principle-only key the controls silently overwrite the treatments, and the table
    # then reports the controls' distances under the treatments' names. That produced a
    # false claim in the paper -- Equal and Sufficientarian read as identical at N=16 on
    # grid4 when their real L1 distance is 18. Restrict to the treatment rows explicitly.
    TREATMENT = {"scaling": "scale|", "grid4": "g4|"}
    for src, tag, factors in (("scaling", "grid8", (0.5, 1.0, 1.5)),
                              ("grid4", "grid4", (0.5, 1.0, 1.5))):
        pre = TREATMENT[src]
        rows = [r for r in load(src)
                if str(r.get("key", "")).startswith(pre)
                and r["cfg"].get("who", "communities") == "communities"
                and r.get("paths")]
        if not rows:
            continue
        key = lambda r: r["cfg"]["principle"]
        # Guard: one row per principle per demand, or the table is meaningless.
        from collections import Counter as _C
        for f in factors:
            dup = [p for p, n in _C(key(r) for r in rows
                                    if r["cfg"].get("demand_factor") == f).items() if n > 1]
            if dup:
                md(f"\n_[{tag} f={f}: {len(dup)} principle(s) have multiple rows "
                   f"({', '.join(dup)}); table suppressed rather than pick arbitrarily]_\n")
                return
        md(f"\n## Are the five routings actually different? ({tag})\n")
        md("Pairwise L1 distance between per-community occupancy vectors, as a "
           "fraction of total flight time. 0 = identical map; 1 = disjoint. "
           "Occupancy rather than path lists, so relabelling interchangeable "
           "aircraft does not register as a difference.\n")
        for f in factors:
            by = {key(r): r for r in rows if r["cfg"].get("demand_factor") == f}
            present = [p for p in ORDER if p in by]
            if len(present) < 2:
                continue
            occ = {p: _occupancy(by[p]) for p in present}
            tot = {p: sum(occ[p]) for p in present}
            n = by[present[0]]["N"]
            md(f"\n**N = {n}**\n")
            md("| | " + " | ".join(LABEL[p][:6] for p in present) + " |")
            md("|---" * (len(present) + 1) + "|")
            for a in present:
                cells = []
                for b in present:
                    if a == b:
                        cells.append("--")
                        continue
                    denom = max(tot[a], tot[b]) or 1
                    d = sum(abs(x - y) for x, y in zip(occ[a], occ[b])) / (2 * denom)
                    cells.append(f"{d:.2f}")
                md(f"| {LABEL[a]} | " + " | ".join(cells) + " |")
            md("")
            md("Status: " + ", ".join(f"{LABEL[p]}={status_mark(by[p])}"
                                     for p in present))

            if tag == "grid8" and f == 1.0:
                tex = [r"\begin{table}[t]", r"\centering",
                       r"\caption{Do the principles produce different maps? Pairwise "
                       r"$L_1$ distance between per-community occupancy vectors at "
                       r"$N{=}16$, as a fraction of total flight time: $0$ means the "
                       r"same map, $1$ means no community carries traffic under both. "
                       r"Occupancy rather than path lists, so relabelling "
                       r"interchangeable aircraft does not register as a difference. "
                       r"Equal and Sufficientarian are the closest pair at every fleet "
                       r"size, and identical at $N{=}8$.}",
                       r"\label{tab:distinct}",
                       r"\begin{tabular}{l" + "r" * len(present) + r"}", r"\toprule",
                       " & " + " & ".join(LABEL[p][:5] for p in present) + r" \\",
                       r"\midrule"]
                for a in present:
                    cells = []
                    for b in present:
                        if a == b:
                            cells.append("--")
                            continue
                        denom = max(tot[a], tot[b]) or 1
                        d = sum(abs(x - y) for x, y in zip(occ[a], occ[b])) / (2 * denom)
                        cells.append(f"{d:.2f}")
                    tex.append(f"{LABEL[a]} & " + " & ".join(cells) + r" \\")
                tex += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
                io.open(os.path.join(TEXDIR, "distinct.tex"), "w", encoding="utf-8",
                        newline="\n").write("\n".join(tex) + "\n")


# =========================================================================
# FLEET-SIZE STUDY (2026-09-09) tables.
#
# These read results/fleet_metrics.json, which metrics_run.py builds from the
# unlimited-budget sweep, rather than load() -- the study is exempt from the
# long-budget merge on purpose (see MERGE_EXEMPT above), so it must not go
# through the merging loader at all.
#
# Every cell says whether it is proven. An unproven cell is a real routing and
# so a real UPPER bound on any minimised metric, but it is not the optimum, and
# a table that hides the difference is the exact mistake claims_audit.md records
# five times over. Unproven cells carry a dagger.
# =========================================================================
FLEET_LADDER = (8, 16, 24, 32)
CLABEL = dict(LABEL, baseline="Baseline")
CORDER = ORDER + ["baseline"]


def _fleet_metrics():
    p = os.path.join(RES, "fleet_metrics.json")
    if not os.path.exists(p):
        return {}, None
    recs = json.load(io.open(p, encoding="utf-8"))
    idx = {(m.get("setup_name", "default"), m.get("condition"), m.get("N")): m
           for m in recs if not m.get("probe")}
    if not idx:
        return {}, None
    names = [k[0] for k in idx]
    return idx, max(set(names), key=names.count)


def _dag(m):
    """Mark a cell whose optimality is unproven."""
    return "" if m.get("optimality") == "optimal" else r"$^\dagger$"


def _cell(m, field, nd=2, scale=1.0):
    if m is None:
        return "--"
    v = m.get(field)
    if v is None:
        return "--"
    v = v * scale
    s = f"{v:.{nd}f}" if isinstance(v, float) else str(v)
    return s + _dag(m)


def table_fleet():
    """Six metrics per principle across the fleet ladder. The paper's main table."""
    idx, setup = _main_cells()
    if not idx:
        return
    sizes = [n for n in FLEET_LADDER if any(k[0] == setup and k[2] == n for k in idx)]
    if not sizes:
        return
    conds = [c for c in CORDER if any(k[0] == setup and k[1] == c for k in idx)]

    md("\n## Fleet-size study: what each principle does as N grows\n")
    md(f"Setup `{setup}`, unlimited budget. A dagger marks a cell whose optimality "
       "is unproven: the routing is verified feasible and every number read off it "
       "is real, but it is an upper bound on a minimised metric, not the optimum.\n")
    md("| N | condition | avg hops | +vs base | max/tile | shared t-steps | "
       "total dB | peak dB | status |")
    md("|---|---|---|---|---|---|---|---|---|")
    for n in sizes:
        for c in conds:
            m = idx.get((setup, c, n))
            if m is None:
                continue
            md(f"| {n} | {CLABEL[c]} | {_cell(m,'avg_trip_hops')} | "
               f"{_cell(m,'extra_vs_baseline',0)} | {_cell(m,'max_count',0)} | "
               f"{_cell(m,'shared_tile_timesteps',0)} | {_cell(m,'total_added')} | "
               f"{_cell(m,'peak_added')} | {m.get('optimality')} |")

    unproven = sum(1 for c in conds for n in sizes
                   if (idx.get((setup, c, n)) or {}).get("optimality") not in (None, "optimal"))
    tex = [r"\begin{table}[t]", r"\centering",
           r"\caption{Routing under each principle as the fleet grows, on setup "
           r"\texttt{" + setup.replace("_", r"\_") + r"} at an unlimited solver "
           r"budget. \emph{+vs base} is total fleet hops above the no-fairness "
           r"baseline at the same $N$; \emph{max/tile} the largest number of "
           r"aircraft over one community at one timestep; \emph{shared} the "
           r"tile-timesteps carrying two or more. Total added noise is the "
           r"arithmetic dB sum the Utilitarian term minimises. "
           + (r"A dagger marks a verified feasible routing whose optimality is "
              r"unproven; every such number bounds the optimum rather than "
              r"stating it." if unproven else
              r"Every cell is a proven optimum.") + r"}",
           r"\label{tab:fleet-main}",
           r"\begin{tabular}{r l rr rr rr}", r"\toprule",
           r"$N$ & Condition & avg hops & +vs base & max/tile & shared & "
           r"total dB & peak dB \\", r"\midrule"]
    for i, n in enumerate(sizes):
        if i:
            tex.append(r"\midrule")
        for c in conds:
            m = idx.get((setup, c, n))
            if m is None:
                continue
            tex.append(f"{n} & {CLABEL[c]} & {_cell(m,'avg_trip_hops')} & "
                       f"{_cell(m,'extra_vs_baseline',0)} & {_cell(m,'max_count',0)} & "
                       f"{_cell(m,'shared_tile_timesteps',0)} & "
                       f"{_cell(m,'total_added',1)} & {_cell(m,'peak_added')} " + r"\\")
    tex += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    io.open(os.path.join(TEXDIR, "fleet_main.tex"), "w", encoding="utf-8",
            newline="\n").write("\n".join(tex) + "\n")


def table_capacity():
    """Capacity utilisation per ambient tier, at the two anchor fleet sizes.

    Utilisation is peak occupancy over what the cap D actually grants a tile at that
    ambient level. It is the number that says a uniform cap is not a uniform rule: the
    same D buys a 65 dBA tile many times the capacity it buys a 45 dBA one.
    """
    idx, setup = _main_cells()
    if not idx:
        return
    # One size below the cap's activation and one above it, both proven in every
    # ordering for every condition (N = 32 has harvested cells and no Equal row).
    sizes = [n for n in (8, 24) if any(k[0] == setup and k[2] == n for k in idx)]
    if not sizes:
        return
    conds = [c for c in CORDER if any(k[0] == setup and k[1] == c for k in idx)]
    tiers = ("45", "55", "65")

    md("\n## Capacity utilisation by ambient tier\n")
    md("Peak aircraft over a community, divided by what its cap $D$ allows a tile at "
       "that ambient level to hold. Mean over touched tiles in the tier; a blank tier "
       "carried no traffic.\n")
    md("| N | condition | D | tile capacity 45/55/65 | " +
       " | ".join(f"{t} dBA" for t in tiers) + " | fleet max |")
    md("|---|---|---|---|---|---|---|---|")
    for n in sizes:
        for c in conds:
            m = idx.get((setup, c, n))
            if m is None:
                continue
            bt = m.get("capacity_utilisation_by_tier") or {}
            tc = m.get("tile_capacity") or {}
            cells = [("--" if bt.get(t) is None else f"{bt[t]:.2f}") for t in tiers]
            md(f"| {n} | {CLABEL[c]} | {fmt(m.get('D'),0)} | "
               f"{'/'.join(str(tc.get(t,'--')) for t in tiers)} | "
               + " | ".join(cells) + f" | {_cell(m,'capacity_utilisation_max')} |")

    tex = [r"\begin{table}[t]", r"\centering",
           r"\caption{Capacity utilisation by ambient tier: peak aircraft over a "
           r"community as a fraction of the capacity \eqref{eq:capclosed} grants a "
           r"tile at that ambient level, averaged over the tier's tiles that carried "
           r"traffic, for the first aircraft ordering. \emph{max} is the largest "
           r"utilisation on any tile, averaged over the four orderings. \emph{cap.} is "
           r"the capacity in aircraft at 45/55/65\,dBA under the row's $D$. Every "
           r"principle sends $D{=}6$; the baseline sends the wide cap $D{=}30$.}",
           r"\label{tab:capacity}",
           # footnotesize: the baseline's 999/9990/99900 column overruns one IEEE
           # column at normal size.
           r"\footnotesize", r"\setlength{\tabcolsep}{2.5pt}",
           r"\begin{tabular}{r l r l rrr r}", r"\toprule",
           r"$N$ & Condition & $D$ & cap. & 45\,dBA & 55\,dBA & 65\,dBA & max \\",
           r"\midrule"]
    for i, n in enumerate(sizes):
        if i:
            tex.append(r"\midrule")
        for c in conds:
            m = idx.get((setup, c, n))
            if m is None:
                continue
            bt = m.get("capacity_utilisation_by_tier") or {}
            tc = m.get("tile_capacity") or {}
            cells = [("--" if bt.get(t) is None else f"{bt[t]:.2f}") for t in tiers]
            cap = "/".join(str(tc.get(t, "--")) for t in tiers)
            tex.append(f"{n} & {CLABEL[c]} & {fmt(m.get('D'),0)} & {cap} & " +
                       " & ".join(cells) + f" & {_cell(m,'capacity_utilisation_max')} " + r"\\")
    tex += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    io.open(os.path.join(TEXDIR, "capacity.tex"), "w", encoding="utf-8",
            newline="\n").write("\n".join(tex) + "\n")


KNOB_LABEL = {"slack": "Horizon slack above the Chebyshev floor",
              "limit": "Cap value $D$/$U$ sent by Equal and Sufficientarian",
              "hard_cap": "Hard cap $D$ applied to every principle",
              "aircraft_db": "Aircraft source level (dBA)",
              "demand": "Demand per origin--destination pair",
              "protected": "Prioritarian protected set",
              "ambient_kind": "Ambient map"}


def table_setup():
    """SETUP_MAIN against the dashboard's default, one row per knob."""
    sys.path.insert(0, HERE)
    import plans as PL
    main_s, dflt = PL.SETUP_MAIN, PL.SETUP_DEFAULT

    md("\n## The setup the fleet study runs on\n")
    md(f"`SETUP_MAIN` = `{main_s['name']}`. Knobs not listed are the dashboard's own "
       "defaults, unchanged.\n")
    md("| knob | default | SETUP_MAIN |")
    md("|---|---|---|")
    tex = [r"\begin{table}[t]", r"\centering",
           r"\caption{The instance the fleet-size study runs on, against the "
           r"dashboard's own defaults. Only the rows in bold differ. The horizon "
           r"slack is the knob that matters most: the dashboard sends $T_{\max}$ one "
           r"step above the Chebyshev lower bound (zero when the Utilitarian term is "
           r"live), which leaves a principle almost nowhere to detour into, so it can "
           r"express itself only by reordering aircraft.}",
           r"\label{tab:setup}",
           r"\begin{tabular}{l l l}", r"\toprule",
           r"Knob & Default & Study \\", r"\midrule"]

    # `None` means different things per knob: the dashboard's own per-principle slack
    # for one, "no such cap is sent" for the other.
    NONE_AS = {"slack": "per principle (0 or 1)", "hard_cap": "none"}

    def show(v, knob=None):
        if v is None:
            return NONE_AS.get(knob, "none")
        if isinstance(v, (tuple, list)):
            return "(" + ", ".join(str(x) for x in v) + ")"
        if isinstance(v, float) and v == int(v):
            return str(int(v))
        return str(v)

    for k in ("slack", "limit", "hard_cap", "aircraft_db", "demand", "protected",
              "ambient_kind"):
        a, b = dflt.get(k), main_s.get(k)
        same = (tuple(a) if isinstance(a, (tuple, list)) else a) == \
               (tuple(b) if isinstance(b, (tuple, list)) else b)
        md(f"| {KNOB_LABEL[k]} | {show(a,k)} | {show(b,k)}{'' if same else ' **(moved)**'} |")
        lab, va, vb = KNOB_LABEL[k], show(a, k), show(b, k)
        if not same:
            lab, va, vb = rf"\textbf{{{lab}}}", rf"\textbf{{{va}}}", rf"\textbf{{{vb}}}"
        tex.append(f"{lab} & {va} & {vb} " + r"\\")
    tex += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    io.open(os.path.join(TEXDIR, "setup.tex"), "w", encoding="utf-8",
            newline="\n").write("\n".join(tex) + "\n")


def table_frontier():
    """How far each principle proved out, and what is still running."""
    idx, setup = _main_cells()
    if not idx:
        return
    ns = sorted({k[2] for k in idx if k[0] == setup})
    md("\n## Tractability frontier at an unlimited budget\n")
    md("The largest fleet at which each condition is PROVEN optimal, and the wall "
       "time it took. Cells beyond the frontier are still searching; their elapsed "
       "time is a lower bound, recorded in `results/checkpoints/`.\n")
    md("| condition | proven to N | wall at that N (s) | cells returned | par |")
    md("|---|---|---|---|---|")
    for c in CORDER:
        got = [(n, idx[(setup, c, n)]) for n in ns if (setup, c, n) in idx]
        if not got:
            continue
        prov = [(n, m) for n, m in got if m.get("optimality") == "optimal"]
        top = max(prov, key=lambda p: p[0]) if prov else None
        md(f"| {CLABEL[c]} | {top[0] if top else '--'} | "
           f"{fmt(top[1].get('wall'), 1) if top else '--'} | {len(got)} | "
           f"{got[0][1].get('runner_par')} |")


# ---------------------------------------------------------------- session 3
MAIN_STEM = "fleet_main_metrics"
FAMILIES3 = [("congestion", "max_count", 0),
             ("travel time", "extra_vs_baseline", 0),
             ("departure delay", "departure_delay_total", 0),
             ("added noise", "peak_added", 2)]


def _main_cells(stem=MAIN_STEM):
    p = os.path.join(RES, stem + ".json")
    if not os.path.exists(p):
        return {}, None
    recs = json.load(io.open(p, encoding="utf-8"))
    idx = {(m.get("setup_name"), m.get("condition"), m.get("N")): m for m in recs}
    names = [k[0] for k in idx]
    return idx, (max(set(names), key=names.count) if names else None)


def table_response():
    """One row per principle, one column per metric family: what it does as N grows.

    Two things per cell, and they answer different questions. **Active from** is the
    smallest fleet size at which this principle's value differs attributably from the
    no-fairness baseline -- the principle does nothing below it. The arrow is what
    happens to that difference above it: growing with N, shrinking, or present but not
    moving. A principle that is never attributable gets a dash, which is a finding
    about the principle at this setup, not a gap in the data.

    Attributability is `metrics_run.attributable`: means apart by more than the larger
    permutation floor AND ranges that do not overlap.
    """
    sys.path.insert(0, HERE)
    import metrics_run as MR
    idx, setup = _main_cells()
    if not idx:
        return
    ns = sorted({k[2] for k in idx if k[0] == setup})
    conds = [c for c in ORDER if any(k[0] == setup and k[1] == c for k in idx)]
    if not conds:
        return

    md("\n## What each principle does as the fleet grows\n")
    md(f"Setup `{setup}`. **Active from** is the smallest N at which the principle "
       "differs attributably from the baseline on that metric; the arrow is what the "
       "difference does above it. A dash means the principle never separates from the "
       "baseline on that metric at this setup.\n")
    md("| principle | " + " | ".join(f for f, _m, _d in FAMILIES3) + " |")
    md("|---" * (len(FAMILIES3) + 1) + "|")

    rows_tex = []
    for c in conds:
        cells, tex = [], []
        for _fam, metric, nd in FAMILIES3:
            att = [n for n in ns
                   if MR.attributable(idx.get((setup, c, n)),
                                      idx.get((setup, "baseline", n)), metric)]
            if not att:
                cells.append("--"); tex.append("--"); continue
            lo, hi = att[0], att[-1]
            d_lo = idx[(setup, c, lo)][metric] - idx[(setup, "baseline", lo)][metric]
            d_hi = idx[(setup, c, hi)][metric] - idx[(setup, "baseline", hi)][metric]
            if abs(d_hi) > abs(d_lo) * 1.15:
                arrow, atex = "grows", r"$\uparrow$"
            elif abs(d_hi) < abs(d_lo) * 0.85:
                arrow, atex = "shrinks", r"$\downarrow$"
            else:
                arrow, atex = "flat", r"$-$"
            cells.append(f"from N={lo}, {arrow} ({d_lo:+.{nd}f} to {d_hi:+.{nd}f})")
            tex.append(f"{atex} from $N{{=}}{lo}$")
        md(f"| {LABEL[c]} | " + " | ".join(cells) + " |")
        rows_tex.append((LABEL[c], tex))

    tex = [r"\begin{table}[t]", r"\centering",
           r"\caption{How each principle responds to fleet size. \emph{From} is the "
           r"smallest fleet at which the principle's routing differs from the "
           r"no-fairness baseline by more than the permutation band at that cell; the "
           r"arrow is whether that difference grows or shrinks above it. A dash means "
           r"the principle never separates from the baseline on that metric, which is "
           r"a property of the principle on this instance rather than a missing "
           r"measurement.}",
           r"\label{tab:response}",
           r"\begin{tabular}{l" + "l" * len(FAMILIES3) + "}", r"\toprule",
           "Principle & " + " & ".join(f.title() for f, _m, _d in FAMILIES3) + r" \\",
           r"\midrule"]
    for lab, cells in rows_tex:
        tex.append(f"{lab} & " + " & ".join(cells) + r" \\")
    tex += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    io.open(os.path.join(TEXDIR, "response.tex"), "w", encoding="utf-8",
            newline="\n").write("\n".join(tex) + "\n")


def table_reference():
    """The tool's default setup in three lines: the paragraph §IV-A points at."""
    idx, _ = _main_cells("fleet_metrics")
    if not idx:
        return
    rows = [(c, n) for c in ORDER for n in (8, 16, 24) if ("default", c, n) in idx]
    if not rows:
        return
    md("\n## Reference: the tool's own default setup\n")
    md("$D=10$, protected set off the corridor. Three fleet sizes, for the one "
       "paragraph in §IV-A that says what the default does.\n")
    md("| N | condition | max/tile | peak dB | extra hops |")
    md("|---|---|---|---|---|")
    tex = [r"\begin{table}[t]", r"\centering",
           r"\caption{The tool's own default setup, for reference: cap $D{=}10$ and a "
           r"protected set that carries no traffic. At $N{=}8$ Equal and "
           r"Sufficientarian return the baseline's routing exactly; above it their "
           r"differences from the baseline and from each other are smaller than the "
           r"range one condition covers under a relabelling of the aircraft. This is "
           r"the regime the study moves away from.}",
           r"\label{tab:reference}", r"\begin{tabular}{r l rrr}", r"\toprule",
           r"$N$ & Condition & max/tile & peak dB & extra hops \\", r"\midrule"]
    for n in (8, 16, 24):
        for c in ORDER + ["baseline"]:
            m = idx.get(("default", c, n))
            if not m:
                continue
            md(f"| {n} | {LABEL.get(c, c)} | {fmt(m.get('max_count'),0)} | "
               f"{fmt(m.get('peak_added'))} | {fmt(m.get('extra_vs_floor'),0)} |")
            tex.append(f"{n} & {LABEL.get(c, c)} & {fmt(m.get('max_count'),0)} & "
                       f"{fmt(m.get('peak_added'))} & {fmt(m.get('extra_vs_floor'),0)} "
                       + r"\\")
    tex += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    io.open(os.path.join(TEXDIR, "reference.tex"), "w", encoding="utf-8",
            newline="\n").write("\n".join(tex) + "\n")


def main():
    md("# Experiment summary")
    md("\nGenerated by `paper/harness/analyze.py` from the raw sweeps in "
       "`paper/harness/results/`. Every number traces to one jsonl row.")
    for fn in (table_response, table_reference, table_fleet, table_capacity, table_frontier,
               table_scaling, table_metrics, table_collapse, table_tiers,
               table_ablation, table_caps, table_prior, table_reps, table_grid4, table_detour, table_binding, table_distinct):
        try:
            fn()
        except Exception as e:
            md(f"\n_[{fn.__name__} failed: {type(e).__name__}: {e}]_")
    io.open(OUTMD, "w", encoding="utf-8", newline="\n").write("\n".join(MD) + "\n")
    print("\n".join(MD))
    print("\nwrote", os.path.normpath(OUTMD))


if __name__ == "__main__":
    main()
