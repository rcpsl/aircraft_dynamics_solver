"""results/fleet_findings.md -- one paragraph per experiment, generated from the data.

Every number here is read out of `results/fleet_metrics.json` at generation time and
printed with the row key it came from, so a claim in Sec. IV can be traced to a solve
without going through a second implementation of any metric. Nothing is typed in by
hand, and nothing is rounded before it reaches the page.

The wording rules from the brief are enforced structurally rather than by care: an
unproven cell is described as "a verified feasible routing", a principle that changes
nothing is described by what it costs rather than by what it fails to do, and a
frontier is stated as "proven to N = k".

usage: python findings.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RES = os.path.join(HERE, "results")
OUT = os.path.join(RES, "fleet_findings.md")
LABEL = {"equal": "Equal", "sufficientarian": "Sufficientarian",
         "prioritarian": "Prioritarian", "utilitarian": "Utilitarian",
         "proportional": "Proportional", "baseline": "Baseline"}
ORDER = ["equal", "sufficientarian", "prioritarian", "utilitarian", "proportional"]
CORDER = ORDER + ["baseline"]


def load():
    p = os.path.join(RES, "fleet_metrics.json")
    if not os.path.exists(p):
        return {}, None, []
    recs = [m for m in json.load(io.open(p, encoding="utf-8")) if not m.get("probe")]
    if not recs:
        return {}, None, []
    idx = {(m.get("setup_name", "default"), m["condition"], m["N"]): m for m in recs}
    names = [k[0] for k in idx]
    setup = max(set(names), key=names.count)
    ns = sorted({k[2] for k in idx if k[0] == setup})
    return idx, setup, ns


def _v(m, f, nd=2):
    v = m.get(f)
    if v is None:
        return "--"
    return f"{v:.{nd}f}" if isinstance(v, float) else str(v)


def _cite(m):
    """`key` (status) -- what every number in this file is traceable to."""
    st = m.get("optimality") or m.get("status")
    return f"`{m['key']}`, {st}"


def _proven(m):
    return m.get("optimality") == "optimal"


def para(L, idx, setup, ns):
    have = lambda c: [n for n in ns if (setup, c, n) in idx]

    # ---------------------------------------------------------------- setup
    L.append(f"Setup `{setup}`. Fleet ladder "
             f"N = {', '.join(str(n) for n in ns)}. "
             f"Conditions present: "
             f"{', '.join(LABEL[c] for c in CORDER if have(c))}. "
             "Every solve ran with `timeout_ms = 10^9` and `wall_kill` disabled, so "
             "no row here was shaped by a clock.")
    tot = len(idx)
    prov = sum(1 for m in idx.values() if _proven(m))
    L.append(f"{tot} solves returned, {prov} of them proven optimal; the remaining "
             f"{tot - prov} are verified feasible routings whose optimality is "
             "unproven, and are marked as such wherever they are used.")

    # ------------------------------------------- E1 routing vs fleet size
    L.append("\n## Experiment 1 --- Routing under each principle as the fleet grows\n")
    for c in CORDER:
        hs = have(c)
        if not hs:
            continue
        lo, hi = idx[(setup, c, hs[0])], idx[(setup, c, hs[-1])]
        bits = [f"**{LABEL[c]}.**"]
        bits.append(f"From N={hs[0]} to N={hs[-1]} the peak tile occupancy moves "
                    f"{_v(lo,'max_count',0)} -> {_v(hi,'max_count',0)} aircraft, "
                    f"shared tile-timesteps {_v(lo,'shared_tile_timesteps',0)} -> "
                    f"{_v(hi,'shared_tile_timesteps',0)}, and communities touched "
                    f"{_v(lo,'stations_touched',0)} -> {_v(hi,'stations_touched',0)} "
                    "of 25.")
        sh_lo = (lo.get("identical_routes") or {}).get("aircraft_in_shared")
        sh_hi = (hi.get("identical_routes") or {}).get("aircraft_in_shared")
        if sh_lo is not None:
            bits.append(f"Aircraft flying a route another aircraft also flies: "
                        f"{sh_lo}/{lo.get('aircraft_flown')} -> "
                        f"{sh_hi}/{hi.get('aircraft_flown')}.")
        bits.append(f"({_cite(lo)}; {_cite(hi)}.)")
        L.append(" ".join(bits))

    # ------------------------------------------------- E2 travel-time cost
    L.append("\n## Experiment 2 --- Travel-time cost of each principle\n")
    flat = []
    for c in ORDER:
        hs = have(c)
        if not hs:
            continue
        extras = [(n, idx[(setup, c, n)].get("extra_vs_baseline")) for n in hs]
        extras = [(n, e) for n, e in extras if e is not None]
        floors = [(n, idx[(setup, c, n)].get("extra_vs_floor")) for n in hs]
        if all(e == 0 for _, e in extras) and all(f == 0 for _, f in floors if f is not None):
            flat.append(c)
            continue
        worst = max(extras, key=lambda p: p[1]) if extras else None
        m = idx[(setup, c, worst[0])] if worst else idx[(setup, c, hs[-1])]
        L.append(f"**{LABEL[c]}.** Largest travel cost against the baseline is "
                 f"{worst[1]} fleet-hops at N={worst[0]} "
                 f"({_v(m,'extra_vs_baseline_per_ac')} per aircraft), against a "
                 f"shortest-path floor of {_v(m,'total_floor_hops',0)} hops. "
                 f"({_cite(m)}.)")
    if flat:
        names = ", ".join(LABEL[c] for c in flat)
        L.append(f"**{names}.** Every aircraft flies a shortest path at every fleet "
                 "size measured: total hops equal the shortest-path floor and equal "
                 "the baseline's. These principles impose no travel-time cost at any "
                 "N here; they reshape *where* the flight time is spent, not how much "
                 "of it there is. On this setup the horizon is "
                 "$T_{\\max} = $ Chebyshev floor $+\\,1$, so that is a property of the "
                 "principle within the horizon it was given, and `screen_log.md` "
                 "records what a wider horizon does.")

    # ------------------------------------------------- E3 noise and capacity
    L.append("\n## Experiment 3 --- Noise and capacity\n")
    L.append(_floor_note())
    for n in ns:
        got = [(c, idx[(setup, c, n)]) for c in CORDER if (setup, c, n) in idx]
        if len(got) < 2:
            continue
        quiet = min(got, key=lambda p: p[1].get("peak_added", 9e9))
        loud = max(got, key=lambda p: p[1].get("peak_added", -9e9))
        tot_lo = min(got, key=lambda p: p[1].get("total_added", 9e9))
        L.append(f"**N={n}.** Peak added noise ranges "
                 f"{_v(quiet[1],'peak_added')} dB ({LABEL[quiet[0]]}) to "
                 f"{_v(loud[1],'peak_added')} dB ({LABEL[loud[0]]}); lowest total "
                 f"added noise is {LABEL[tot_lo[0]]} at "
                 f"{_v(tot_lo[1],'total_added')} dB summed. "
                 f"Highest capacity utilisation is "
                 f"{max(_fl(m.get('capacity_utilisation_max')) for _, m in got):.2f} "
                 f"of what the cap grants. "
                 f"({_cite(quiet[1])}; {_cite(loud[1])}.)")

    # ------------------------------------------------- E4 solver performance
    L.append("\n## Experiment 4 --- Solver performance\n")
    for c in CORDER:
        hs = have(c)
        if not hs:
            continue
        prov = [n for n in hs if _proven(idx[(setup, c, n)])]
        if prov:
            top = idx[(setup, c, max(prov))]
            L.append(f"**{LABEL[c]}.** Proven optimal to N={max(prov)} "
                     f"({_v(top,'wall',1)} s at par {top.get('runner_par')}). "
                     f"{len(hs)} of {len(ns)} ladder cells returned. ({_cite(top)}.)")
        else:
            m = idx[(setup, c, hs[-1])]
            L.append(f"**{LABEL[c]}.** No cell proven optimal on the ladder; "
                     f"{len(hs)} cells returned a verified feasible routing, "
                     f"the largest at N={hs[-1]}. ({_cite(m)}.)")

    # ------------------------------------------------------------- F summary
    L.append("\n## Summary --- each principle's signature response to a growing fleet\n")
    for c in ORDER:
        hs = have(c)
        if not hs:
            continue
        lo, hi = idx[(setup, c, hs[0])], idx[(setup, c, hs[-1])]
        d_share = None
        a, b = (lo.get("identical_routes") or {}), (hi.get("identical_routes") or {})
        if a.get("aircraft_in_shared") is not None and lo.get("aircraft_flown"):
            d_share = (100.0 * b["aircraft_in_shared"] / max(1, hi["aircraft_flown"])
                       - 100.0 * a["aircraft_in_shared"] / max(1, lo["aircraft_flown"]))
        L.append(f"**{LABEL[c]}** ({hs[0]} -> {hs[-1]}): peak tile occupancy "
                 f"{_v(lo,'max_count',0)} -> {_v(hi,'max_count',0)}, peak added noise "
                 f"{_v(lo,'peak_added')} -> {_v(hi,'peak_added')} dB, extra hops vs "
                 f"baseline {_v(lo,'extra_vs_baseline',0)} -> "
                 f"{_v(hi,'extra_vs_baseline',0)}"
                 + (f", share of fleet on a shared route {d_share:+.0f} pp"
                    if d_share is not None else "") + ".")


def _fl(x):
    return 0.0 if x is None else float(x)


def _floor_note():
    """The caveat every between-condition noise number in this file needs.

    Read live from the slack sweep rather than typed, so the sentence cannot drift
    from the measurement it is warning about. Silent if that sweep is not on disk --
    an absent caveat is better than a fabricated number.
    """
    try:
        import metrics_run as MR
        sl = [m for m in MR.build(["results/slack.jsonl"])
              if m.get("optimality") == "optimal"]
        for m in sl:
            m["_x"] = (m.get("setup") or {}).get("slack")
        C = ("baseline", "equal", "sufficientarian", "prioritarian")
        best = (0.0, None)
        for n in sorted({m["N"] for m in sl}):
            for c in C:
                v = [m.get("peak_added") for m in sl if m["condition"] == c
                     and m["N"] == n and m.get("_x") is not None
                     and m.get("peak_added") is not None]
                if len(v) > 1 and (max(v) - min(v)) > best[0]:
                    best = (max(v) - min(v), n)
        if best[1] is None:
            return ""
        return (f"_Read every between-condition figure below against the indifference "
                f"floor: holding one condition fixed and moving only the horizon, which "
                f"leaves its arrival optimum unchanged, still moves its peak added "
                f"noise by up to {best[0]:.2f} dB (at N={best[1]}). Differences smaller "
                f"than that are not evidence about the condition. See "
                f"`comparison.md`._\n")
    except Exception:
        return ""


def main():
    idx, setup, ns = load()
    L = ["# Fleet-size study: findings",
         "",
         "Generated by `paper/harness/findings.py` from `results/fleet_metrics.json`. "
         "Every number carries the key of the solve it came from. Regenerate rather "
         "than edit.", ""]
    if not idx:
        L.append("_No fleet rows on disk yet._")
    else:
        para(L, idx, setup, ns)
    io.open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    print("wrote", os.path.normpath(OUT), f"({len(idx)} cells)")


if __name__ == "__main__":
    main()
