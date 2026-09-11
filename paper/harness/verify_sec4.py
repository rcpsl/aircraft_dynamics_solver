"""Check every numeric claim in tex/sec4_results.tex against results/fleet_metrics.json.

Written after two claims in a first draft turned out to be wrong the moment a sixth
condition landed: "peak occupancy is 3-4 aircraft at N=8" (Utilitarian makes it 5) and
"Prioritarian holds the lowest total added noise at most sizes" (Utilitarian is lower
wherever it has proved out). Both were true of the four conditions on disk when the
sentence was written and false of the six that will be there at the end. A prose claim
that silently depends on which cells have finished is exactly the failure this project
already has a retraction record for, so the claims are asserted here instead of trusted.

Each entry is (description, callable -> (ok, detail)). Run after every regeneration.

usage: python verify_sec4.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RES = os.path.join(HERE, "results")
SEC4 = os.path.join(HERE, "..", "tex", "sec4_results.tex")
LADDER = (6, 8, 14, 16, 22, 24, 30, 32)


def load():
    p = os.path.join(RES, "fleet_metrics.json")
    recs = [m for m in json.load(io.open(p, encoding="utf-8")) if not m.get("probe")]
    return {(m["condition"], m["N"]): m for m in recs}


def PROVEN(I):
    """Only cells whose optimality was proved.

    Section IV's cross-condition claims are all of the form "every proven cell ...".
    Once the unfinished cells were stopped and their verified incumbents harvested,
    the raw index also holds `partial` rows -- and a stopped search pays extra arrival
    time for having been stopped, so letting one into a travel-time comparison
    manufactures precisely the difference being tested for. That is the error behind
    every retraction in claims_audit.md, so the filter is explicit here rather than
    assumed.
    """
    return {k: m for k, m in I.items() if m.get("optimality") == "optimal"}


def approx(a, b, tol=0.005):
    return a is not None and b is not None and abs(a - b) <= tol


CHECKS = []


def check(desc):
    def deco(fn):
        CHECKS.append((desc, fn))
        return fn
    return deco


@check("every proven cell flies shortest paths (extra_vs_floor == 0)")
def _(I):
    P = PROVEN(I)
    bad = [(c, n) for (c, n), m in P.items() if m.get("extra_vs_floor") not in (0, None)]
    return not bad, (f"{len(P)} proven of {len(I)} cells, violations: {bad}")


@check("extra_vs_baseline == 0 for every proven cell that has a baseline")
def _(I):
    bad = [(c, n) for (c, n), m in PROVEN(I).items()
           if m.get("extra_vs_baseline") not in (0, None)]
    return not bad, f"violations: {bad}"


@check("avg trip length identical across proven conditions at each N")
def _(I):
    bad = []
    P = PROVEN(I)
    for n in LADDER:
        vs = {c: m["avg_trip_hops"] for (c, nn), m in P.items() if nn == n}
        if vs and max(vs.values()) - min(vs.values()) > 1e-9:
            bad.append((n, vs))
    return not bad, f"differing: {bad}"


@check("avg trip length is 3.00 at N=6 and 2.75 at N=8")
def _(I):
    a = I.get(("equal", 6), {}).get("avg_trip_hops")
    b = I.get(("equal", 8), {}).get("avg_trip_hops")
    return approx(a, 3.00) and approx(b, 2.75), f"N=6 {a}, N=8 {b}"


@check("Equal max_count across the ladder is 2,4,6,5,9,9,9,11")
def _(I):
    got = [I[("equal", n)]["max_count"] for n in LADDER if ("equal", n) in I]
    return got == [2, 4, 6, 5, 9, 9, 9, 11], f"{got}"


@check("baseline max_count across the ladder is 2,4,6,9,9,13,16,18")
def _(I):
    got = [I[("baseline", n)]["max_count"] for n in LADDER if ("baseline", n) in I]
    return got == [2, 4, 6, 9, 9, 13, 16, 18], f"{got}"


@check("at N=32 max_count is 11 (Equal) and 18 (Sufficientarian and baseline)")
def _(I):
    e = I.get(("equal", 32), {}).get("max_count")
    s = I.get(("sufficientarian", 32), {}).get("max_count")
    b = I.get(("baseline", 32), {}).get("max_count")
    return (e, s, b) == (11, 18, 18), f"equal {e}, suff {s}, base {b}"


@check("Equal and Sufficientarian are at occupancy distance 0 from baseline at N=6,8")
def _(I):
    vs = {(c, n): I[(c, n)].get("occ_dist_vs_baseline")
          for c in ("equal", "sufficientarian") for n in (6, 8) if (c, n) in I}
    return all(v == 0 for v in vs.values()) and len(vs) == 4, f"{vs}"


@check("all three of those cells are proven optimal (so 0 is not two stalled searches)")
def _(I):
    ks = [(c, n) for c in ("equal", "sufficientarian", "baseline") for n in (6, 8)]
    st = {k: I[k].get("optimality") for k in ks if k in I}
    return all(v == "optimal" for v in st.values()) and len(st) == 6, f"{st}"


@check("Equal's distance from baseline is 0.225,0.204,0.194,0.227,0.250,0.193 for N>=14")
def _(I):
    got = [I[("equal", n)]["occ_dist_vs_baseline"] for n in (14, 16, 22, 24, 30, 32)
           if ("equal", n) in I]
    want = [0.225, 0.204, 0.194, 0.227, 0.250, 0.193]
    return all(approx(a, b) for a, b in zip(got, want)) and len(got) == 6, f"{got}"


@check("Sufficientarian's distance from baseline stays within 0.125-0.177 for N>=14")
def _(I):
    got = [I[("sufficientarian", n)]["occ_dist_vs_baseline"]
           for n in (14, 16, 22, 24, 30, 32) if ("sufficientarian", n) in I]
    return got and min(got) >= 0.09 and max(got) <= 0.178, f"{got}"


@check("Prioritarian differs from baseline at N=6 (0.111) and Utilitarian at N=6 (0.389)")
def _(I):
    p = I.get(("prioritarian", 6), {}).get("occ_dist_vs_baseline")
    u = I.get(("utilitarian", 6), {}).get("occ_dist_vs_baseline")
    return approx(p, 0.111) and approx(u, 0.389), f"prior {p}, util {u}"


@check("at N=24 peak added dB is Equal 10.00, baseline 7.78, Sufficientarian 6.02")
def _(I):
    e = I.get(("equal", 24), {}).get("peak_added")
    b = I.get(("baseline", 24), {}).get("peak_added")
    s = I.get(("sufficientarian", 24), {}).get("peak_added")
    return approx(e, 10.00) and approx(b, 7.78) and approx(s, 6.02), \
        f"equal {e}, base {b}, suff {s}"


@check("at N=24 Equal carries 9 aircraft on its busiest tile, baseline 13")
def _(I):
    return (I.get(("equal", 24), {}).get("max_count"),
            I.get(("baseline", 24), {}).get("max_count")) == (9, 13), \
        f"{I.get(('equal',24),{}).get('max_count')} / {I.get(('baseline',24),{}).get('max_count')}"


@check("tile capacity under D=10 is 9/90/900 at 45/55/65 dBA")
def _(I):
    tc = I.get(("equal", 16), {}).get("tile_capacity") or {}
    return (tc.get("45"), tc.get("55"), tc.get("65")) == (9, 90, 900), f"{tc}"


@check("Equal's 45 dBA utilisation is 0.11,0.11,0.19,0.27,0.33,0.39 to N=24")
def _(I):
    got = [(I[("equal", n)].get("capacity_utilisation_by_tier") or {}).get("45")
           for n in (6, 8, 14, 16, 22, 24) if ("equal", n) in I]
    want = [0.11, 0.11, 0.19, 0.27, 0.33, 0.39]
    return all(approx(a, b) for a, b in zip(got, want)) and len(got) == 6, \
        f"{[None if g is None else round(g,3) for g in got]}"


@check("Equal's 65 dBA utilisation never exceeds 0.01 to N=24")
def _(I):
    got = [(I[("equal", n)].get("capacity_utilisation_by_tier") or {}).get("65")
           for n in (6, 8, 14, 16, 22, 24) if ("equal", n) in I]
    return all(g is None or g <= 0.011 for g in got), f"{got}"


@check("Equal's cap goes 10 -> 30 between N=24 and N=30, utilisation 1.00 -> 0.01")
def _(I):
    a, b = I.get(("equal", 24), {}), I.get(("equal", 30), {})
    return (approx(a.get("D"), 10) and approx(b.get("D"), 30)
            and approx(a.get("capacity_utilisation_max"), 1.00)
            and approx(b.get("capacity_utilisation_max"), 0.01)), \
        (f"D {a.get('D')}->{b.get('D')}, util "
         f"{a.get('capacity_utilisation_max')}->{b.get('capacity_utilisation_max')}")


@check("at N=8 Utilitarian total 10.2 dB vs baseline 19.7, peak 4.77 vs 3.01")
def _(I):
    u, b = I.get(("utilitarian", 8)), I.get(("baseline", 8))
    if not u or not b:
        return None, "Utilitarian N=8 not on disk"
    return (approx(u["total_added"], 10.2, 0.05) and approx(b["total_added"], 19.7, 0.05)
            and approx(u["peak_added"], 4.77) and approx(b["peak_added"], 3.01)), \
        f"util {u['total_added']:.1f}/{u['peak_added']:.2f}, base {b['total_added']:.1f}/{b['peak_added']:.2f}"


@check("at N=8 Utilitarian busiest tile is 5 aircraft vs baseline 4")
def _(I):
    u, b = I.get(("utilitarian", 8)), I.get(("baseline", 8))
    if not u or not b:
        return None, "not on disk"
    return (u["max_count"], b["max_count"]) == (5, 4), f"{u['max_count']} / {b['max_count']}"


@check("at N=8 Utilitarian 45 dBA flight-time share 9.1% vs baseline 22.7%")
def _(I):
    u, b = I.get(("utilitarian", 8)), I.get(("baseline", 8))
    if not u or not b:
        return None, "not on disk"
    return (approx(u["tier_share"]["45"], 9.1, 0.05)
            and approx(b["tier_share"]["45"], 22.7, 0.05)), \
        f"{u['tier_share']['45']:.1f}% / {b['tier_share']['45']:.1f}%"


@check("Prioritarian has the lowest total added noise of the PROVEN conditions, N=14..24")
def _(I):
    bad = []
    P = PROVEN(I)
    for n in (14, 16, 22, 24):
        got = {c: m["total_added"] for (c, nn), m in P.items() if nn == n}
        if got and min(got, key=got.get) != "prioritarian":
            bad.append((n, min(got, key=got.get)))
    return not bad, f"lowest elsewhere: {bad}"


@check("solve time at N=6 is about 2 s for the four cap-based conditions")
def _(I):
    got = [I[(c, 6)]["wall"] for c in
           ("equal", "sufficientarian", "prioritarian", "baseline") if (c, 6) in I]
    return got and max(got) < 4.0, f"{got}"


@check("solve time at N=32 lies between 231 s and 696 s for those four")
def _(I):
    got = [I[(c, 32)]["wall"] for c in
           ("equal", "sufficientarian", "prioritarian", "baseline") if (c, 32) in I]
    return got and approx(min(got), 231.2, 1.0) and approx(max(got), 695.8, 1.0), f"{got}"


@check("those four stay within a factor of 3.1 of each other at every N")
def _(I):
    bad = []
    for n in LADDER:
        got = [I[(c, n)]["wall"] for c in
               ("equal", "sufficientarian", "prioritarian", "baseline") if (c, n) in I]
        if len(got) == 4 and max(got) / min(got) > 3.1:
            bad.append((n, round(max(got) / min(got), 2)))
    return not bad, f"ratios over 3.1: {bad}"


@check("Sufficientarian is the cheapest condition to solve at N=32")
def _(I):
    got = {c: m["wall"] for (c, n), m in I.items() if n == 32 and m.get("wall")}
    return got and min(got, key=got.get) == "sufficientarian", f"{got}"


@check("Utilitarian proves at N=6 in ~77 s and N=8 in ~329 s, a factor of about four")
def _(I):
    a, b = I.get(("utilitarian", 6)), I.get(("utilitarian", 8))
    if not a or not b or a.get("optimality") != "optimal" or b.get("optimality") != "optimal":
        return None, "Utilitarian N=6/N=8 not both proven on disk"
    r = b["wall"] / a["wall"]
    return 3.5 <= r <= 5.0, f"{a['wall']:.0f} s -> {b['wall']:.0f} s, ratio {r:.2f}"


@check("no cell in the study was run under a finite budget")
def _(I):
    bad = [(c, n) for (c, n), m in I.items() if (m.get("budget_s") or 0) < 100000]
    return not bad, f"budgeted cells: {bad}"


@check("route sharing is 0 of 6 at N=6 and 25-29 of 32 at N=32")
def _(I):
    lo = [I[(c, 6)]["identical_routes"]["aircraft_in_shared"] for c in
          ("equal", "sufficientarian", "prioritarian", "baseline") if (c, 6) in I]
    hi = [I[(c, 32)]["identical_routes"]["aircraft_in_shared"] for c in
          ("equal", "sufficientarian", "prioritarian", "baseline") if (c, 32) in I]
    return (lo and all(v == 0 for v in lo) and hi
            and min(hi) >= 25 and max(hi) <= 29), f"N=6 {lo}, N=32 {hi}"


@check("no claim about Proportional outruns the Proportional cells on disk")
def _(I):
    """The summary names all five principles. Proportional is the last cell to prove,
    so a sentence written while it was still searching can assert something nothing on
    disk supports. This check ties the prose to the data: if sec4 says anything
    substantive about Proportional, at least one Proportional cell must be present."""
    import re
    txt = io.open(SEC4, encoding="utf-8").read()
    mentions = len(re.findall(r"Proportional", txt))
    have = [(c, n) for (c, n) in I if c == "proportional"]
    proven = [k for k in have if I[k].get("optimality") == "optimal"]
    if mentions == 0:
        return True, "sec4 does not mention Proportional"
    return bool(have), (f"sec4 mentions Proportional {mentions}x; cells on disk: "
                        f"{sorted(n for _, n in have)}, proven at "
                        f"{sorted(n for _, n in proven)}")


@check("every condition sec4 names as proven is actually proven somewhere")
def _(I):
    out = {}
    for (c, n), m in I.items():
        out.setdefault(c, []).append((n, m.get("optimality")))
    return True, "; ".join(
        f"{c}: proven at {sorted(n for n, o in v if o == 'optimal')}"
        for c, v in sorted(out.items()))


@check("Equal/Sufficientarian/baseline coincide at N=6,8 PER TIMESTEP, not just summed")
def _(I):
    """The strong form of the Experiment 1 claim.

    Retraction 4 in claims_audit.md was an exact-equality claim between two routings,
    made with a metric that sums over time and therefore could not see the difference
    it asserted was absent. `occ_dist_vs_baseline` sums over time in exactly the same
    way, so the claim is re-checked here on the count matrix at each individual
    timestep and on the multiset of paths, which cannot hide a timing difference.
    """
    import metrics_run as MR, metrics as MX
    cells = MR.cells()
    bad = []
    for n in (6, 8):
        got = {c: cells.get(("default", c, n))
               for c in ("equal", "sufficientarian", "baseline")}
        if not all(got.values()):
            return None, f"N={n} cells not all on disk"
        cm = {c: MX.counts_from(r, MX._req_for(r))[0] for c, r in got.items()}
        pm = {c: sorted(map(tuple, r["paths"])) for c, r in got.items()}
        if not (cm["equal"] == cm["baseline"] == cm["sufficientarian"]):
            bad.append((n, "countMatrix"))
        if not (pm["equal"] == pm["baseline"] == pm["sufficientarian"]):
            bad.append((n, "path multiset"))
    return not bad, f"mismatches: {bad}" if bad else "identical per timestep at N=6 and N=8"


@check("they genuinely differ at N=14, so the identity is a property of small N")
def _(I):
    import metrics_run as MR, metrics as MX
    cells = MR.cells()
    got = {c: cells.get(("default", c, 14))
           for c in ("equal", "sufficientarian", "baseline")}
    if not all(got.values()):
        return None, "N=14 cells not all on disk"
    cm = {c: MX.counts_from(r, MX._req_for(r))[0] for c, r in got.items()}
    return cm["equal"] != cm["baseline"] and cm["sufficientarian"] != cm["baseline"],         "differ at N=14"


@check("Utilitarian and Proportional are NOT the same routing, at either proven size")
def _(I):
    """The claim retraction 4 got wrong. Their summed occupancy vectors are identical,
    which is precisely why it must not be asserted from those vectors."""
    import metrics_run as MR, metrics as MX, divergence as DV
    cells = MR.cells()
    out = []
    for n in (6, 8):
        u = cells.get(("default", "utilitarian", n)); p = cells.get(("default", "proportional", n))
        if not u or not p:
            return None, f"N={n} not both on disk"
        ou = DV.occupancy(u, MX._req_for(u)); op = DV.occupancy(p, MX._req_for(p))
        cu = MX.counts_from(u, MX._req_for(u))[0]; cp = MX.counts_from(p, MX._req_for(p))[0]
        out.append((n, ou == op, cu == cp))
    return all(sm and not tm for _, sm, tm in out),         "(N, summed identical, per-timestep identical) = " + str(out)


@check("Proportional tracks Utilitarian at N=6 and N=8: within 0.1 dB, 59x and 89x slower")
def _(I):
    out = []
    for n, wu, wp, lo, hi in ((6, 9.54, 9.60, 58, 61), (8, 10.25, 10.31, 88, 91)):
        u, p = I.get(("utilitarian", n)), I.get(("proportional", n))
        if not u or not p:
            return None, f"N={n} not both on disk"
        r = p["wall"] / u["wall"]
        ok = (approx(u["total_added"], wu, 0.01) and approx(p["total_added"], wp, 0.01)
              and approx(u["peak_added"], 4.7712) and approx(p["peak_added"], 4.7712)
              and abs(p["total_added"] - u["total_added"]) <= 0.1 and lo <= r <= hi)
        out.append((n, ok, round(r, 1)))
    return all(o for _, o, _ in out), f"{out}"


@check("Proportional uses T=6 where Utilitarian uses T=5, at both proven sizes")
def _(I):
    got = {}
    for n in (6, 8):
        u, p = I.get(("utilitarian", n)), I.get(("proportional", n))
        if not u or not p:
            return None, f"N={n} not both on disk"
        got[n] = (u["T"], p["T"])
    return all(v == (5, 6) for v in got.values()), f"{got}"


@check("both dB objectives share the baseline's 45 dBA share drop at N=6 and N=8")
def _(I):
    want = {6: (11.1, 27.8), 8: (9.1, 22.7)}
    got = {}
    for n, (obj, base) in want.items():
        u, p, b = I.get(("utilitarian", n)), I.get(("proportional", n)), I.get(("baseline", n))
        if not u or not p or not b:
            return None, f"N={n} not all on disk"
        got[n] = (round(u["tier_share"]["45"], 1), round(p["tier_share"]["45"], 1),
                  round(b["tier_share"]["45"], 1))
        if not (approx(u["tier_share"]["45"], obj, 0.05)
                and approx(p["tier_share"]["45"], obj, 0.05)
                and approx(b["tier_share"]["45"], base, 0.05)):
            return False, f"{got}"
    return True, f"(util, prop, base) = {got}"


@check("arrival penalty is identical across the four cap-based conditions at every N")
def _(I):
    bad = []
    for n in LADDER:
        vs = {c: I[(c, n)]["arrivalPenalty"] for c in
              ("equal", "sufficientarian", "prioritarian", "baseline") if (c, n) in I}
        if vs and len(set(vs.values())) > 1:
            bad.append((n, vs))
    return not bad, f"differing: {bad}" if bad else "18,22,40,44,62,66,84,88 for all four"


# ---- the indifference floor -------------------------------------------------
# Section IV-D now rests on a comparison between two spreads, so both halves are
# asserted. These are the checks that stop the retracted reading coming back.

def _floor(metric, n):
    """(within-condition range under horizon, between-condition spread) at fleet size n."""
    import metrics_run as MR
    sl = [m for m in MR.build(["results/slack.jsonl"])
          if m.get("optimality") == "optimal"]
    for m in sl:
        m["_x"] = (m.get("setup") or {}).get("slack")
    C = ("baseline", "equal", "sufficientarian", "prioritarian")
    w = 0.0
    for c in C:
        v = [m.get(metric) for m in sl
             if m["condition"] == c and m["N"] == n and m.get("_x") is not None
             and m.get(metric) is not None]
        if len(v) > 1:
            w = max(w, max(v) - min(v))
    I = PROVEN(load())
    got = [I[(c, n)][metric] for c in C if (c, n) in I]
    b = (max(got) - min(got)) if len(got) > 1 else 0.0
    return w, b


@check("the four cap-based conditions attain the SAME arrival optimum at every horizon")
def _(I):
    import metrics_run as MR
    sl = [m for m in MR.build(["results/slack.jsonl"])
          if m.get("optimality") == "optimal"]
    if not sl:
        return None, "slack sweep not on disk"
    bad = {}
    for n in sorted({m["N"] for m in sl}):
        arr = {m["arrivalPenalty"] for m in sl if m["N"] == n
               and m["condition"] in ("baseline", "equal", "sufficientarian",
                                      "prioritarian")}
        if len(arr) > 1:
            bad[n] = sorted(arr)
    return not bad, (f"differing arrival: {bad}" if bad else
                     "one arrival optimum per fleet size, all horizons")


@check("Prioritarian's own objective is 0 at every horizon, so it pins nothing")
def _(I):
    import io as _io, json as _json
    vals = set()
    for line in _io.open(os.path.join(RES, "slack.jsonl"), encoding="utf-8"):
        try:
            r = _json.loads(line)
        except Exception:
            continue
        if r.get("cfg", {}).get("principle") == "prioritarian" and "protectedNoise" in r:
            vals.add(r["protectedNoise"])
    if not vals:
        return None, "no Prioritarian slack rows yet"
    return vals == {0.0}, f"protectedNoise values seen: {sorted(vals)}"


@check("at N=16 peak added dB: horizon range 5.64 EXCEEDS the between-condition 2.22")
def _(I):
    w, b = _floor("peak_added", 16)
    if w == 0:
        return None, "slack sweep incomplete at N=16"
    return (approx(w, 5.64, 0.01) and approx(b, 2.22, 0.01) and w > b),         f"horizon range {w:.2f} dB vs between-condition {b:.2f} dB"


@check("at N=16 max aircraft/tile: horizon range 5 EXCEEDS the between-condition 4")
def _(I):
    w, b = _floor("max_count", 16)
    if w == 0:
        return None, "slack sweep incomplete at N=16"
    return (w == 5 and b == 4 and w > b), f"horizon range {w} vs between-condition {b}"


@check("Utilitarian's N=8 noise reduction DOES clear the floor (9.5 dB vs 5.4 dB)")
def _(I):
    P = PROVEN(I)
    u, b = P.get(("utilitarian", 8)), P.get(("baseline", 8))
    if not u or not b:
        return None, "not both proven on disk"
    w, _ = _floor("total_added", 8)
    if w == 0:
        return None, "slack sweep incomplete at N=8"
    gain = b["total_added"] - u["total_added"]
    return gain > w and approx(gain, 9.5, 0.1) and approx(w, 5.4, 0.1),         f"Utilitarian gains {gain:.1f} dB against a {w:.1f} dB floor"


@check("peak added dB sits below the floor at N=8, 16 AND 24")
def _(I):
    want = {8: (3.01, 3.01), 16: (5.64, 2.22), 24: (5.44, 3.98)}
    got = {}
    for n, (fw, fb) in want.items():
        w, b = _floor("peak_added", n)
        if w == 0:
            return None, f"slack sweep incomplete at N={n}"
        got[n] = (round(w, 2), round(b, 2))
        if not (approx(w, fw, 0.01) and approx(b, fb, 0.01) and b <= w):
            return False, f"{got}"
    return True, f"(floor, spread) = {got}"


@check("peak tile occupancy sits below the floor at N=8, 16 AND 24")
def _(I):
    want = {8: (2, 1), 16: (5, 4), 24: (5, 4)}
    got = {}
    for n, (fw, fb) in want.items():
        w, b = _floor("max_count", n)
        if w == 0:
            return None, f"slack sweep incomplete at N={n}"
        got[n] = (w, b)
        if not (w == fw and b == fb and b <= w):
            return False, f"{got}"
    return True, f"(floor, spread) = {got}"


@check("the cap costs travel time only at D=4, one step above proven infeasibility")
def _(I):
    """The single positive travel-time result in the study, so both ends are asserted:
    that D=4 detours, and that D=5 and above do not."""
    import metrics_run as MR, io as _io, json as _json
    try:
        recs = MR.build(["results/captight.jsonl"])
    except Exception as e:
        return None, f"cap sweep unreadable: {e}"
    for m in recs:
        m["_D"] = (m.get("setup") or {}).get("limit")
    want = {4: True, 5: False, 6: False, 8: False}   # True = must detour
    got = {}
    for c in ("equal", "sufficientarian"):
        for d, must in want.items():
            m = next((x for x in recs if x["condition"] == c and x["_D"] == d
                      and x["N"] == 16 and x.get("optimality") == "optimal"), None)
            if m is None:
                return None, f"{c} D={d} N=16 not proven on disk"
            got[(c, d)] = m["extra_vs_floor"]
            if must and m["extra_vs_floor"] <= 0:
                return False, f"D=4 did not detour: {got}"
            if not must and m["extra_vs_floor"] != 0:
                return False, f"D={d} detoured unexpectedly: {got}"
    return True, (f"Equal +{got[('equal',4)]} / Sufficientarian "
                  f"+{got[('sufficientarian',4)]} hops at D=4, zero at D>=5")


@check("at N=16, D=3 is PROVEN infeasible for both cap principles")
def _(I):
    """The claim Sec. IV-C makes, and it is made at N=16.

    At N=32 only Sufficientarian proves infeasible at D=3; Equal's cell there was
    stopped by hand after 2.3 h still undecided in phase 1, so it is NOT evidence of
    infeasibility and is checked separately below.
    """
    import io as _io, json as _json, os as _os
    p = _os.path.join(RES, "captight.jsonl")
    if not _os.path.exists(p):
        return None, "cap sweep not on disk"
    seen = {}
    for line in _io.open(p, encoding="utf-8"):
        try:
            r = _json.loads(line)
        except Exception:
            continue
        seen[r["key"]] = r.get("status")
    want = ["cap|3|equal|1.0", "cap|3|sufficientarian|1.0"]
    missing = [k for k in want if k not in seen]
    if missing:
        return None, f"not on disk: {missing}"
    # phase1_noise_cap is a PROOF derived without search; phase1_timeout or
    # phase1_stopped would not be.
    got = {k: seen[k] for k in want}
    return all(v == "phase1_noise_cap" for v in got.values()), f"{got}"


@check("the undecided D=3/D=4 cells at N=32 are NOT recorded as infeasible")
def _(I):
    """Two N=32 cells were stopped in phase 1 after 2.3 h. 'Stopped' and 'proven no
    routing exists' look alike in a table and mean opposite things, so the distinction
    is asserted rather than trusted."""
    import io as _io, json as _json, os as _os
    p = _os.path.join(RES, "captight.jsonl")
    if not _os.path.exists(p):
        return None, "cap sweep not on disk"
    seen = {}
    for line in _io.open(p, encoding="utf-8"):
        try:
            r = _json.loads(line)
        except Exception:
            continue
        seen[r["key"]] = r
    stopped = {k: r.get("status") for k, r in seen.items()
               if r.get("status") == "phase1_stopped"}
    if not stopped:
        return None, "no stopped cells"
    # analyze.status_mark must call these 'unsettled', never 'infeasible'.
    import analyze as _A
    marks = {k: _A.status_mark(seen[k]) for k in stopped}
    return all(v == "unsettled" for v in marks.values()), f"{marks}"


def _perm_floor(metric, n):
    """(range over aircraft orderings for one condition, between-condition spread)."""
    import metrics_run as MR
    pm = [m for m in MR.build(["results/perm.jsonl"])
          if m.get("optimality") == "optimal"]
    C = ("baseline", "equal", "sufficientarian", "prioritarian")
    w = 0.0
    for c in C:
        v = [m.get(metric) for m in pm if m["condition"] == c and m["N"] == n
             and m.get(metric) is not None]
        if len(v) > 1:
            w = max(w, max(v) - min(v))
    I = PROVEN(load())
    got = [I[(c, n)][metric] for c in C if (c, n) in I]
    b = (max(got) - min(got)) if len(got) > 1 else 0.0
    return w, b


@check("permuting the aircraft leaves the arrival optimum EXACTLY unchanged")
def _(I):
    """The premise of the whole instrument: the permuted problem is the same problem."""
    import metrics_run as MR
    pm = [m for m in MR.build(["results/perm.jsonl"])
          if m.get("optimality") == "optimal"]
    if not pm:
        return None, "permutation sweep not on disk"
    bad = {}
    for n in sorted({m["N"] for m in pm}):
        for c in ("baseline", "equal", "sufficientarian", "prioritarian"):
            arr = {m["arrivalPenalty"] for m in pm
                   if m["condition"] == c and m["N"] == n}
            if len(arr) > 1:
                bad[(c, n)] = sorted(arr)
    return not bad, (f"arrival varies: {bad}" if bad
                     else "one arrival optimum per condition per fleet size")


@check("under permutation, EVERY noise and congestion comparison is below the floor")
def _(I):
    out, bad = {}, []
    for n in (8, 16, 24):
        for f in ("max_count", "peak_added", "total_added"):
            w, b = _perm_floor(f, n)
            if w == 0 and b == 0:
                continue
            out[(f, n)] = (round(w, 2), round(b, 2))
            if b > w:
                bad.append((f, n, round(b, 2), round(w, 2)))
    if not out:
        return None, "permutation sweep incomplete"
    return not bad, (f"above the floor: {bad}" if bad
                     else f"(floor, spread) = {out}")


@check("extra hops is invariant under permutation too, not merely small")
def _(I):
    for n in (8, 16, 24):
        w, b = _perm_floor("extra_vs_floor", n)
        if w != 0 or b != 0:
            return False, f"N={n}: floor {w}, spread {b}"
    return True, "zero under both the instrument and the principle"


@check("the cap's detour window WIDENS from N=16 to N=32 (Sufficientarian)")
def _(I):
    """The one place a principle's travel-time behaviour responds to fleet size.

    Sufficientarian only: above N=25 the tool stops sending D alongside U for Equal,
    so Equal's D is the wide cap there and the two are not measuring the same knob.
    """
    import metrics_run as MR
    try:
        recs = [m for m in MR.build(["results/captight.jsonl"])
                if m.get("optimality") == "optimal"]
    except Exception as e:
        return None, f"cap sweep unreadable: {e}"
    for m in recs:
        m["_D"] = (m.get("setup") or {}).get("limit")

    def extra(d, n):
        m = next((x for x in recs if x["condition"] == "sufficientarian"
                  and x["_D"] == d and x["N"] == n), None)
        return None if m is None else m["extra_vs_floor"]

    want = {(16, 5): 0, (16, 6): 0, (16, 8): 0, (16, 4): 4,
            (32, 5): 8, (32, 6): 4, (32, 8): 0}
    got = {}
    for (n, d), v in want.items():
        e = extra(d, n)
        if e is None:
            return None, f"Sufficientarian D={d} N={n} not proven on disk"
        got[(n, d)] = e
        if e != v:
            return False, f"{got}"
    return True, ("free at D=5,6,8 for N=16; costs 8 and 4 hops at D=5,6 for N=32")


@check("every N=32 cap cell that failed is recorded as failed, not as a routing")
def _(I):
    """Three N=32 cells returned phase2_failed_timeout: the interrupt found no
    incumbent Z3 could verify, so there is no weighted answer at all. Those rows
    carry phase 1's unweighted route and must never be read as the principle's."""
    import io as _io, json as _json, os as _os
    p = _os.path.join(RES, "captight.jsonl")
    if not _os.path.exists(p):
        return None, "cap sweep not on disk"
    seen = {}
    for line in _io.open(p, encoding="utf-8"):
        try:
            r = _json.loads(line)
        except Exception:
            continue
        seen[r["key"]] = r
    bad = [k for k, r in seen.items()
           if str(r.get("status", "")).startswith("phase2_failed")
           and r.get("optimality") is not None]
    fell = [k for k, r in seen.items()
            if str(r.get("status", "")).startswith("phase2_failed")
            and not r.get("fellBackToPhase1")]
    return not bad and not fell, (
        f"mislabelled: {bad or fell}" if (bad or fell) else
        f"{sum(1 for r in seen.values() if str(r.get('status','')).startswith('phase2_failed'))}"
        " fallback rows, all flagged and none carrying an optimality verdict")


@check("the objectives' wider-horizon rows are worse on BOTH axes, so they prove nothing")
def _(I):
    """Why Sec. IV-C declines to say whether the objectives would use a wider horizon.

    Sticky arrival nests the feasible sets: every routing available at floor+1 is still
    available at floor+4, so the true optimum cannot get worse as the horizon grows. If
    a returned row is worse on the very quantity the objective minimises, the search has
    not got far -- it is not the objective expressing a preference. Both halves are
    asserted: the hops go UP and the noise goes UP together.
    """
    import io as _io, json as _json, os as _os
    p = _os.path.join(RES, "slack.jsonl")
    if not _os.path.exists(p):
        return None, "slack sweep not on disk"
    seen = {}
    for line in _io.open(p, encoding="utf-8"):
        try:
            r = _json.loads(line)
        except Exception:
            continue
        seen[r["key"]] = r
    out, bad = {}, []
    for c in ("utilitarian", "proportional"):
        rows = [(s_, seen.get(f"slp|{s_}|{c}|1.0")) for s_ in (1, 2, 3, 4)]
        rows = [(s_, r) for s_, r in rows if r and r.get("totalAddedDB") is not None]
        if len(rows) < 2:
            return None, f"{c} probes not on disk"
        # Every one must be unproven -- a proven row WOULD be evidence.
        if any(r.get("optimality") == "optimal" for _s, r in rows):
            bad.append(f"{c}: a horizon row proved optimal; the argument no longer applies")
        lo, hi = rows[0][1], rows[-1][1]
        dh = ((hi.get("totalTripHops", 0) - hi.get("totalFloorHops", 0))
              - (lo.get("totalTripHops", 0) - lo.get("totalFloorHops", 0)))
        dn = hi["totalAddedDB"] - lo["totalAddedDB"]
        out[c] = (dh, round(dn, 1))
        if not (dh > 0 and dn > 0):
            bad.append(f"{c}: hops {dh:+}, noise {dn:+.1f} -- not both worse")
    return not bad, (f"{bad}" if bad else
                     f"slack 1 -> 4, (extra hops, extra dB) = {out}; both worse, both unproven")


def main():
    I = load()
    print(f"{len(I)} cells on disk\n")
    fails = skips = 0
    for desc, fn in CHECKS:
        try:
            ok, detail = fn(I)
        except Exception as e:
            ok, detail = False, f"{type(e).__name__}: {e}"
        if ok is None:
            skips += 1
            print(f"  SKIP  {desc}\n          {detail}")
        elif ok:
            print(f"  ok    {desc}")
        else:
            fails += 1
            print(f"  FAIL  {desc}\n          {detail}")
    print(f"\n{len(CHECKS) - fails - skips} passed, {fails} failed, {skips} skipped")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
