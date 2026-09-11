"""Is a principle ACTIVE at a setup? The session-3 replacement for the divergence check.

Session 1 chose the study's operating point by asking whether the five principles
returned distinct routings. They did, and it meant nothing: distinct routings are what
the arrival tie-break produces for free among equally-optimal answers. Session 2 measured
how much -- one condition moves 5.64 dB of peak added noise and 5 aircraft per tile on
its own when an incidental parameter changes -- and most between-principle differences at
the default setup sit under that.

So the criterion here is not "does the routing differ" but "does the principle CONSTRAIN
the routing", judged per principle against what the principle is:

  Equal / Sufficientarian   a cap. Active if it changes the routing away from the
                            wide-cap baseline by an attributable margin on max aircraft
                            per tile, peak added dB or extra hops -- or if it is sitting
                            at capacity utilisation 1.00, which is the cap binding
                            exactly, visible without any margin at all.

  Prioritarian              an objective over a protected set. Active if the set would
                            be overflown without it -- `protectedNoise > 0` in the
                            ablation control -- and switching it on reduces that by an
                            attributable margin. A protected set nobody wants to fly
                            over is satisfied for free and constrains nothing, which is
                            what PROT_BURDEN turned out to be.

  Utilitarian / Proportional an objective over all communities. Active if its own
                            objective value beats what the BASELINE routing scores on
                            that same objective, by more than the cap-based floor at the
                            same setup. Scoring the baseline on the principle's own
                            metric is the only fair comparison; `analyze.principle_metric`
                            recomputes it from the returned paths.

"Attributable" throughout is `metrics_run.attributable`: the means differ by more than
the larger floor AND the permutation ranges do not overlap.

usage: python activity.py [screen3.jsonl]
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import metrics_run as MR

RES = os.path.join(HERE, "results")
HEADLINE = ("max_count", "shared_tile_timesteps", "extra_vs_floor",
            "departure_delay_total", "total_added", "peak_added")


def raw_rows(path):
    out = []
    p = path if os.path.isabs(path) else os.path.join(HERE, path)
    if not os.path.exists(p):
        return out
    for line in io.open(p, encoding="utf-8"):
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def cap_active(cell, base):
    """Equal / Sufficientarian: does the cap move the routing, or is it binding?"""
    if cell is None or base is None:
        return None, "no cell"
    if (cell.get("capacity_utilisation_max") or 0) >= 0.999:
        return True, f"cap binding exactly (utilisation {cell['capacity_utilisation_max']:.2f})"
    hits = []
    for f in ("max_count", "peak_added", "extra_vs_floor"):
        if MR.attributable(cell, base, f):
            hits.append(f"{f} {cell[f]:.2f} vs {base[f]:.2f}")
    if hits:
        return True, "; ".join(hits)
    return False, (f"utilisation {cell.get('capacity_utilisation_max', 0):.2f}, "
                   "no attributable difference from the wide-cap baseline")


def prior_active(cell, off):
    """Prioritarian: would the set be overflown without the objective?"""
    if cell is None or off is None:
        return None, "no cell"
    # protectedNoise is reported by the solver only when the objective is ON, so the
    # control's exposure is recomputed from its routing over the same stations.
    prot = cell.get("protected_stations") or []
    if not prot:
        return None, "no protected set on the row"
    off_exp = off.get("protected_peak")
    on_exp = cell.get("protected_peak")
    if off_exp is None or on_exp is None:
        return None, "protected_peak missing"
    if off_exp <= 0:
        return False, (f"the protected set carries nothing even with the objective off "
                       f"(peak {off_exp:.2f} dB) -- satisfied for free")
    att = MR.attributable(cell, off, "protected_peak")
    return (bool(att),
            f"control peak {off_exp:.2f} dB -> {on_exp:.2f} dB with the objective on"
            + ("" if att else "; within the band"))


def obj_active(probe_rows, base_cell, principle, floor):
    """Utilitarian / Proportional: does the objective beat the baseline's own score?"""
    import analyze as A
    if not probe_rows or base_cell is None:
        return None, "no probe"
    r = probe_rows[0]
    own, unit = A.principle_metric(r, principle)
    base_raw = base_cell.get("_raw")
    if own is None or base_raw is None:
        return None, "objective not recomputable"
    base_own, _ = A.principle_metric(base_raw, principle)
    if base_own is None:
        return None, "baseline not scorable on this objective"
    gain = base_own - own
    return (gain > floor,
            f"{unit}: baseline {base_own:.1f} -> {own:.1f} "
            f"(gain {gain:.1f} vs floor {floor:.1f})")


def report(path="results/screen3.jsonl"):
    raw = raw_rows(path)
    if not raw:
        return "_No screen rows on disk yet._\n"
    cells = {(m["setup_name"], m["condition"], m["N"]): m
             for m in MR.build([path], agg=True) if not m.get("probe")}
    # Keep one raw row per cell so a principle's own objective can be recomputed.
    for m in cells.values():
        m["_raw"] = next((r for r in raw if str(r.get("key")) in m.get("perm_keys", [])
                          and r.get("paths")), None)
    # Keyed by fleet size as well as condition: a probe run at N=16 scored against the
    # N=8 baseline compares two different problems and reported a negative "gain".
    probes = {}
    import divergence as _DV
    for r in raw:
        if r.get("probe") and r.get("paths"):
            probes.setdefault(((r.get("setup") or {}).get("name"),
                               _DV.principle_of(r), r.get("N")), []).append(r)

    setups = sorted({k[0] for k in cells})
    ns = sorted({k[2] for k in cells})
    L = ["# Setup screen (session 3): which setups make every principle active?", "",
         "Criterion per principle in `activity.py`. \"Attributable\" means the means "
         "differ by more than the larger permutation floor **and** the ranges do not "
         "overlap. Every cell below is K permutations, unlimited budget, proven.", ""]

    for n in ns:
        L.append(f"\n## N = {n}\n")
        L.append("| setup | Equal | Sufficientarian | Prioritarian | "
                 "Utilitarian | Proportional | active | attributable diffs |")
        L.append("|---|---|---|---|---|---|---|---|")
        for s in setups:
            base = cells.get((s, "baseline", n))
            verdicts, notes = {}, []
            for c in ("equal", "sufficientarian"):
                v, why = cap_active(cells.get((s, c, n)), base)
                verdicts[c] = v
                notes.append(f"{c}: {why}")
            v, why = prior_active(cells.get((s, "prioritarian", n)),
                                  cells.get((s, "prioritarian_off", n)))
            verdicts["prioritarian"] = v
            notes.append(f"prioritarian: {why}")

            floor = max([cells[(s, c, n)].get("floor_total_added") or 0
                         for c in ("equal", "sufficientarian", "prioritarian")
                         if (s, c, n) in cells] or [0])
            for c in ("utilitarian", "proportional"):
                v, why = obj_active(probes.get((s, c, n)), base, c, floor)
                verdicts[c] = v
                notes.append(f"{c}: {why}")

            # How many of the six headline metrics separate ANY pair of principles here.
            diffs = 0
            P5 = ("equal", "sufficientarian", "prioritarian")
            for f in HEADLINE:
                pairs = [(a, b) for i, a in enumerate(P5) for b in P5[i + 1:]]
                pairs += [(a, "baseline") for a in P5]
                if any(MR.attributable(cells.get((s, a, n)), cells.get((s, b, n)), f)
                       for a, b in pairs):
                    diffs += 1

            mark = {True: "yes", False: "no", None: "--"}
            n_act = sum(1 for v in verdicts.values() if v)
            L.append(f"| `{s}` | " + " | ".join(
                mark[verdicts[c]] for c in ("equal", "sufficientarian", "prioritarian",
                                            "utilitarian", "proportional"))
                + f" | **{n_act}/5** | {diffs}/6 |")
            L.append("")
            for nt in notes:
                L.append(f"  - {nt}")
            L.append("")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    txt = report(sys.argv[1] if len(sys.argv) > 1 else "results/screen3.jsonl")
    io.open(os.path.join(RES, "setup_choice.md"), "w", encoding="utf-8",
            newline="\n").write(txt)
    print(txt)
    print("wrote results/setup_choice.md")
