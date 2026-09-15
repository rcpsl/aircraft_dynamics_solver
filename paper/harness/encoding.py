"""Experiment 5: the exact (decibel) encoding against the abstraction that scales (count).

Utilitarian and Proportional each run in two forms. The decibel form prices what the
principle is about, the added noise delta_m(c_{m,t}); the count form prices c_{m,t}, which
drops the concave, ambient-dependent curve. This module measures what the abstraction
costs and what it buys, per principle, per N, per aircraft ordering:

  quality   the DECIBEL objective evaluated on both forms' routings. The optimum J* is a
            property of the problem, not of the ordering, so it is known as soon as ANY
            ordering of the decibel form proves (and every ordering that proves must agree
            -- checked). The count-form routing is feasible for the decibel problem (same
            caps, same horizon -- checked per pair), so
                loss_k = (J_dB(count routing k) - J*) / J*   >= 0,
            and a negative value would mean the evaluator is wrong. Where no decibel
            ordering proved, J* is unknown but lies at or below the best decibel value any
            routing reached, so the loss measured against that is a LOWER bound on the
            true loss. (Not an upper bound: that needs a lower bound on J*, which Z3
            reports as -oo -- DECISIONS D31.)
  metrics   summed and peak added noise, occupied tile-timesteps, footprint, extra hops,
            departure delay: decibel cell against count cell, attributability as in IV-A.
  speed     mean wall time to proof, decibel over count; a harvested cell gives a lower
            bound, "> mean elapsed / count".

The decibel objective is re-derived from countMatrix with the solver's own table,
round(100 * delta) per tile and timestep, and for Proportional the weight rounded to
hundredths. Every decibel-form row's reported objective must be reproduced, or the run
fails.

usage: python encoding.py
  -> results/fleet_db_metrics.{csv,json}  decibel-form cells, joined to the ladder baseline
  -> results/encoding.json                 every number Experiment 5 reports
  -> results/encoding.md                   the same, readable
  -> tex/tables/encoding.tex               Table IV
"""
import io
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import metrics as MX
import metrics_run as MR

RES = os.path.join(HERE, "results")
TEX_TABLE = os.path.join(HERE, "..", "tex", "tables", "encoding.tex")
MAIN = "results/fleet_main.jsonl"
DB = "results/fleet_db.jsonl"
LADDER = (6, 8, 14, 16, 22, 24)
FORMS = {"utilitarian": "utilitarian_db", "proportional": "proportional_db"}
COMPARE = [("total_added", "summed added noise (dB)"),
           ("peak_added", "peak added noise (dB)"),
           ("occupied_tile_timesteps", "occupied tile-timesteps"),
           ("stations_touched", "tiles overflown"),
           ("extra_vs_baseline", "extra fleet-hops"),
           ("departure_delay_total", "departure delay")]


def delta(b, n, alpha):
    if n == 0:
        return 0.0
    return 10 * math.log10(10 ** (b / 10) + n * 10 ** (alpha / 10)) - b


def db_objective(principle, row, req):
    """The decibel objective of `principle` on any routing, in the solver's own units:
    Utilitarian in dB summed over tiles and timesteps, Proportional in price-weighted dB."""
    cm = row["countMatrix"]
    b, alpha = req["baseline"], req["aircraftDB"]
    w = [round(x * 100) for x in (req.get("proximityWeights") or [])]
    tot = 0
    for m in range(len(cm)):
        for c in cm[m]:
            v = round(delta(b[m], c, alpha) * 100)
            tot += v * (w[m] if principle == "proportional" else 1)
    return tot / (10000.0 if principle == "proportional" else 100.0)


def _rows(path):
    p = os.path.join(HERE, path)
    if not os.path.exists(p):
        return []
    out = []
    for l in io.open(p, encoding="utf-8"):
        try:
            out.append(json.loads(l))
        except ValueError:          # a line the runner is still writing
            continue
    return out


PRINCIPLE_OF = {"utilitarian": "utilitarian", "proportional": "proportional",
                "utilitarian_db": "utilitarian", "proportional_db": "proportional"}


def runs():
    """Every answered run of both forms, with its decibel objective."""
    out = []
    for path in (MAIN, DB):
        for r in _rows(path):
            k = str(r.get("key", ""))
            if r.get("status") != "sat" or r.get("N") not in LADDER or not r.get("paths"):
                continue
            c = k.split("|")[2]
            princ = PRINCIPLE_OF.get(c)
            if princ is None:
                continue
            db = c.endswith("_db")
            out.append({"key": k, "principle": princ, "form": "db" if db else "count",
                        "N": r["N"], "perm": r.get("perm"), "T": r.get("T_used") or r.get("T"),
                        "optimality": r.get("optimality"), "wall": r.get("wall"),
                        "stoppedEarly": r.get("stoppedEarly"),
                        "J_db": db_objective(princ, r, MX._req_for(r)),
                        "reported": ((r.get("totalUtilNoise") if princ == "utilitarian"
                                      else r.get("proximityCost")) if db else None),
                        "tier1_lower": r.get("tier1_lower"),
                        "tier1_lower_raw": r.get("tier1_lower_raw"),
                        "tier1_incumbent": r.get("tier1_incumbent")})
    return out


def selftest(rs):
    """Every decibel-form row's reported objective must be reproduced."""
    bad = [(x["key"], x["reported"], x["J_db"]) for x in rs
           if x["form"] == "db" and x["reported"] is not None
           and abs(x["reported"] - x["J_db"]) > 1e-6]
    n = sum(1 for x in rs if x["form"] == "db" and x["reported"] is not None)
    return n, bad


def gap(x):
    lo, inc = x.get("tier1_lower"), x.get("tier1_incumbent")
    if lo is None or inc is None or inc <= 0 or not math.isfinite(lo):
        return None
    return (inc - lo) / inc


def _stats(v):
    return {"mean": sum(v) / len(v), "min": min(v), "max": max(v), "n": len(v)} if v else None


def cells(rs):
    """Per (principle, N): the paired comparison over the four orderings."""
    by = {}
    for x in rs:
        by.setdefault((x["principle"], x["N"]), {}).setdefault(x["form"], {})[x["perm"]] = x
    out = []
    for p in FORMS:
        for n in LADDER:
            f = by.get((p, n), {})
            cnt, db = f.get("count", {}), f.get("db", {})
            proven = sorted(k for k in db if db[k]["optimality"] == "optimal")
            harvested = sorted(k for k in db if db[k]["optimality"] != "optimal")
            c = {"principle": p, "N": n, "db_proven": proven, "db_harvested": harvested,
                 "db_absent": sorted(set(range(4)) - set(db)),
                 "count_proven": len(cnt) == 4 and all(v["optimality"] == "optimal"
                                                        for v in cnt.values())}
            jc = [cnt[k]["J_db"] for k in sorted(cnt)]
            c["J_count"] = _stats(jc)
            c["J_count_by_perm"] = {k: cnt[k]["J_db"] for k in sorted(cnt)}
            c["wall_count"] = _stats([cnt[k]["wall"] for k in sorted(cnt)])
            c["T_match"] = all(cnt[k]["T"] == db[k]["T"] for k in db if k in cnt)
            c["J_db_by_perm"] = {k: db[k]["J_db"] for k in sorted(db)}
            c["db_wall"] = {k: db[k]["wall"] for k in sorted(db)}
            c["wall_db"] = _stats([db[k]["wall"] for k in proven])
            c["elapsed_harvested"] = _stats([db[k]["wall"] for k in harvested])
            c["gap"] = {k: gap(db[k]) for k in harvested}
            c["lower_raw"] = {k: db[k]["tier1_lower_raw"] for k in harvested}
            if c["wall_db"] and len(proven) == 4:
                c["speedup"] = c["wall_db"]["mean"] / c["wall_count"]["mean"]
            elif c["elapsed_harvested"] and not proven:
                # No ordering proved: each harvested run's elapsed time is a lower bound on
                # its time to proof, so their mean over the count mean bounds the speed-up.
                c["speedup_lower"] = c["elapsed_harvested"]["mean"] / c["wall_count"]["mean"]
            if proven:
                vals = sorted(set(round(db[k]["J_db"], 6) for k in proven))
                c["J_star"] = vals[0]
                c["J_star_consistent"] = len(vals) == 1
                c["count_beats_star"] = any(j < c["J_star"] - 1e-9 for j in jc)
                loss = [(j - c["J_star"]) / c["J_star"] for j in jc]
                c["loss"] = _stats(loss)
                c["loss_abs"] = _stats([j - c["J_star"] for j in jc])
                # Attributable as in IV-A: J* has no band (one optimum), so the count
                # routings' mean must clear their own band and their range must lie above.
                c["loss_attributable"] = bool(c["loss_abs"]["mean"] > max(jc) - min(jc)
                                              and min(jc) > c["J_star"])
            elif db:
                best = min(list(c["J_db_by_perm"].values()) + jc)
                c["J_best_known"] = best
                lb = [max(0.0, (j - best) / best) for j in jc]
                c["loss_lower_bound"] = _stats(lb)
                c["loss_abs_lower_bound"] = _stats([max(0.0, j - best) for j in jc])
                c["count_beats_incumbent"] = {k: cnt[k]["J_db"] < db[k]["J_db"]
                                              for k in harvested if k in cnt}
            out.append(c)
    return out


def db_metrics():
    """Decibel-form cells through the ladder's metrics pipeline, joined to its baseline."""
    recs = MR.build([MAIN, DB])
    db = [m for m in recs if m["condition"] in FORMS.values()]
    if not db:
        return {}
    agg = MR.aggregate(db)
    MR.write(db, stem="fleet_db_metrics", cells_recs=agg)
    return {(m["condition"], m["N"]): m for m in agg}


def form_compare(dbm):
    """Per metric: decibel cell against count cell, attributability as in Sec. IV-A."""
    lad = {(m["condition"], m["N"]): m
           for m in json.load(io.open(os.path.join(RES, "fleet_main_metrics.json"),
                                      encoding="utf-8")) if not m.get("probe")}
    out = []
    for p, pd in FORMS.items():
        for n in LADDER:
            a, b = dbm.get((pd, n)), lad.get((p, n))
            if a is None or b is None:
                continue
            # A band needs all four orderings: aggregate() calls a one-run cell
            # all_proven with a zero-width band, which would let a single draw read as
            # attributable. Fewer than four decibel runs -> not testable (None).
            full = bool(a.get("all_proven")) and a.get("runs") == 4
            row = {"principle": p, "N": n, "db_all_proven": full, "db_runs": a.get("runs")}
            for f, _lab in COMPARE:
                row[f] = {"db": a.get(f), "db_lo": a.get(f + "_min"), "db_hi": a.get(f + "_max"),
                          "count": b.get(f), "count_lo": b.get(f + "_min"),
                          "count_hi": b.get(f + "_max"),
                          "attributable": MR.attributable(a, b, f) if full else None}
            out.append(row)
    return out


def fmt(v, nd=2):
    return "--" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))


def status(c):
    return (f"{len(c['db_proven'])}/4 proven, {len(c['db_harvested'])} harvested, "
            f"{len(c['db_absent'])} absent")


def report(cs, fc, n_self, bad):
    L = ["# Experiment 5: decibel form against count form", "",
         "Generated by `harness/encoding.py`. Row keys: `fleet_db|D6_protA|<p>_db|<f>|p<k>` "
         "(decibel) and `fleet|D6_protA|<p>|<f>|p<k>` (count); f = 0.25 ... 1.5 for "
         "N = 6 ... 24.", "",
         f"Objective reconstruction: {n_self - len(bad)}/{n_self} decibel-form rows reproduce "
         "the solver's reported objective." + (f" MISMATCHES: {bad[:3]}" if bad else ""), "",
         "## Quality and speed", "",
         "| principle | N | decibel status | J* | J_dB(count) mean [range] | loss mean "
         "[range] | attributable | wall dB | wall count | speed-up |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for c in cs:
        jc = c["J_count"]
        if "J_star" in c:
            js = fmt(c["J_star"]) + ("" if c["J_star_consistent"] else " (INCONSISTENT)")
            loss = (f"{100*c['loss']['mean']:.1f}% [{100*c['loss']['min']:.1f}, "
                    f"{100*c['loss']['max']:.1f}]; {fmt(c['loss_abs']['mean'])} abs")
            att = str(c["loss_attributable"])
        elif "J_best_known" in c:
            js = f"<= {fmt(c['J_best_known'])}"
            loss = (f">= {100*c['loss_lower_bound']['mean']:.1f}% mean (lower bound)")
            att = "n/a"
        else:
            js, loss, att = "--", "--", "--"
        sp = (f"{c['speedup']:.1f}x" if "speedup" in c else
              f"> {c['speedup_lower']:.0f}x" if "speedup_lower" in c else "--")
        wd = c["wall_db"]
        L.append(f"| {c['principle']} | {c['N']} | {status(c)} | {js} | "
                 f"{fmt(jc['mean']) if jc else '--'} "
                 f"[{fmt(jc['min']) if jc else ''}, {fmt(jc['max']) if jc else ''}] | {loss} | "
                 f"{att} | {fmt(wd['mean'], 1) if wd else '--'} | "
                 f"{fmt(c['wall_count']['mean'], 1) if c['wall_count'] else '--'} | {sp} |")
    L += ["", "## Harvested decibel cells", "",
          "| principle | N | ordering | elapsed (s) | incumbent J_dB | Z3 lower bound | gap |",
          "|---|---|---|---|---|---|---|"]
    for c in cs:
        for k in c["db_harvested"]:
            g = c["gap"].get(k)
            L.append(f"| {c['principle']} | {c['N']} | p{k} | {fmt(c['db_wall'][k], 0)} | "
                     f"{fmt(c['J_db_by_perm'][k])} | {c['lower_raw'].get(k)} | "
                     f"{'unavailable' if g is None else f'{100*g:.1f}%'} |")
    L += ["", "## Metrics, decibel cell vs count cell", "",
          "| principle | N | " + " | ".join(lab for _f, lab in COMPARE) + " |",
          "|---|---|" + "---|" * len(COMPARE)]
    for r in fc:
        cells_ = []
        for f, _lab in COMPARE:
            v = r[f]
            mark = {True: " *", False: "", None: " ?"}[v["attributable"]]
            cells_.append(f"{fmt(v['db'])} vs {fmt(v['count'])}{mark}")
        L.append(f"| {r['principle']} | {r['N']}{'' if r['db_all_proven'] else ' (dagger)'} | "
                 + " | ".join(cells_) + " |")
    L += ["", "`*` attributable (means apart by more than the larger band, ranges disjoint); "
          "`?` not testable (a cell without a full set of proven orderings); (dagger) decibel "
          "cell not proven in all four orderings."]
    io.open(os.path.join(RES, "encoding.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    return "\n".join(L)


def tex_table(cs):
    """Table IV: per principle and N, the decibel objective on both routings, the loss,
    both wall times and the speed-up."""
    nd = {"utilitarian": 2, "proportional": 1}
    T = [r"\begin{table}[t]", r"\centering", r"\footnotesize",
         r"\caption{Experiment 5. $J_{\mathrm{dB}}$ is the decibel objective: summed added "
         r"noise in dB for Utilitarian, price-weighted dB for Proportional. $J^*$ is its "
         r"optimum, proven by the decibel form; \emph{Count} is its value on the count-form "
         r"routings (mean over four orderings), \emph{Loss} the difference. Times are mean "
         r"wall seconds to a proven optimum. A dagger marks a decibel cell not proven by the "
         r"harvest: $J^*$ is then the best value reached (an upper bound on the optimum), "
         r"the loss a lower bound, and the time and speed-up lower bounds. A cell where "
         r"no decibel run reached a routing better than the count form's carries no "
         r"positive bound and is left out: Proportional at $N=22$ and 24. A time "
         r"marked ($k$/4) is the mean over the $k$ orderings that proved.}",
         r"\label{tab:encoding}", r"\setlength{\tabcolsep}{3pt}",
         r"\begin{tabular}{@{}r rrr rrr@{}}", r"\toprule",
         r"$N$ & $J^*$ & Count & Loss & $t_{\mathrm{dB}}$ & $t_{\mathrm{count}}$ & "
         r"Speed-up \\", r"\midrule"]
    for p in FORMS:
        T.append(r"\multicolumn{7}{@{}l}{\emph{" + p.capitalize() + r"}} \\")
        for c in [c for c in cs if c["principle"] == p]:
            d = nd[p]
            jc = c["J_count"]["mean"] if c["J_count"] else None
            tc = f"{c['wall_count']['mean']:.1f}" if c["wall_count"] else "--"
            if "J_star" in c and len(c["db_proven"]) == 4:
                row = [f"{c['J_star']:.{d}f}", f"{jc:.{d}f}",
                       f"{c['loss_abs']['mean']:.{d}f} ({100*c['loss']['mean']:.0f}\\%)",
                       f"{c['wall_db']['mean']:.0f}", tc, f"{c['speedup']:.0f}$\\times$"]
            elif "J_star" in c:
                # an optimum from the orderings that proved; time is not a full mean
                row = [f"{c['J_star']:.{d}f}", f"{jc:.{d}f}",
                       f"{c['loss_abs']['mean']:.{d}f} ({100*c['loss']['mean']:.0f}\\%)",
                       f"{c['wall_db']['mean']:.0f} ({len(c['db_proven'])}/4)", tc, "--"]
            elif "J_best_known" in c:
                sp = (f"$>${c['speedup_lower']:.0f}$\\times$" if "speedup_lower" in c else "--")
                el = c["elapsed_harvested"]
                # No decibel run reached a routing better than the count form's: the bound
                # is 0 and says nothing, so the row is left out and the caption says so.
                lb = c["loss_abs_lower_bound"]["mean"]
                if round(lb, d) <= 0:
                    continue
                loss_cell = (f"$\\ge${lb:.{d}f} "
                             f"($\\ge${100*c['loss_lower_bound']['mean']:.1f}\\%)")
                row = [f"{c['J_best_known']:.{d}f}$^\\dagger$", f"{jc:.{d}f}", loss_cell,
                       f"$>${el['mean']:.0f}" if el else "--", tc, sp]
            else:
                row = ["--", f"{jc:.{d}f}" if jc is not None else "--", "--", "--", tc, "--"]
            T.append(f"{c['N']} & " + " & ".join(row) + r" \\")
        if p == "utilitarian":
            T.append(r"\midrule")
    T += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    io.open(TEX_TABLE, "w", encoding="utf-8", newline="\n").write("\n".join(T) + "\n")


def harvest_horizon():
    """H in seconds: from the sweep's launch (harvest.py starts with the runner and logs
    first) to the horizon it waits for. Read from the record, not typed."""
    import datetime as dt
    import re
    try:
        first = io.open(os.path.join(RES, "fleet_db_harvest.log"), encoding="utf-8").readline()
    except OSError:
        return None
    m = re.match(r"(\S+)Z\s+harvest horizon (\S+)Z", first)
    if not m:
        return None
    return (dt.datetime.fromisoformat(m.group(2))
            - dt.datetime.fromisoformat(m.group(1))).total_seconds()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # the Windows console is GBK
    except Exception:
        pass
    rs = runs()
    n_self, bad = selftest(rs)
    dbm = db_metrics()
    cs = cells(rs)
    fc = form_compare(dbm)
    json.dump({"runs": rs, "cells": cs, "form_compare": fc, "H_s": harvest_horizon(),
               "selftest": {"checked": n_self, "mismatches": bad}},
              io.open(os.path.join(RES, "encoding.json"), "w", encoding="utf-8"), indent=1)
    tex_table(cs)
    print(report(cs, fc, n_self, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
