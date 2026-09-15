"""Check every numeric claim in the paper's results against results/fleet_main_metrics.json.

Written after two claims in a first draft turned out to be wrong the moment a sixth
condition landed: "peak occupancy is 3-4 aircraft at N=8" (Utilitarian makes it 5) and
"Prioritarian holds the lowest total added noise at most sizes" (Utilitarian is lower
wherever it has proved out). Both were true of the four conditions on disk when the
sentence was written and false of the six that were there at the end. A prose claim
that silently depends on which cells have finished is exactly the failure this project
already has a retraction record for, so the claims are asserted here instead of trusted.

The paper reports the ladder to N = 24. Every check reads only N <= 24, and one check
fails if the text names a fleet size above 24. The same metrics file drives the figures
(export_plot_data.py), so figure and text cannot disagree.

Each entry is (description, callable -> (ok, detail)). Run after every regeneration.

usage: python verify_sec4.py
"""
import io
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RES = os.path.join(HERE, "results")
MAIN = "fleet_main_metrics.json"
REF = "fleet_metrics.json"          # the shipped settings, one paragraph of Sec. III
TEX = os.path.join(HERE, "..", "tex")
SEC4 = os.path.join(TEX, "sec4_results.tex")
TEXT = [os.path.join(TEX, f) for f in ("main.tex", "sec1_intro.tex", "sec3_encoding.tex",
                                        "sec4_results.tex", "sec5_conclusion.tex")]
LADDER = (6, 8, 14, 16, 22, 24)
PRINC = ("equal", "sufficientarian", "prioritarian", "utilitarian", "proportional")
ALL = PRINC + ("baseline",)


def load(name=MAIN):
    p = os.path.join(RES, name)
    recs = [m for m in json.load(io.open(p, encoding="utf-8"))
            if not m.get("probe") and m.get("N") in LADDER]
    return {(m["condition"], m["N"]): m for m in recs}


def PROVEN(I):
    """Only cells whose optimality was proved.

    Every cross-condition claim is of the form "every proven cell ...". A stopped search
    pays extra arrival time for having been stopped, so letting one into a travel-time
    comparison manufactures precisely the difference being tested for. On the reported
    ladder every cell is proven (first check), so this filter is a guard, not a cut.
    """
    return {k: m for k, m in I.items() if m.get("optimality") == "optimal"}


def approx(a, b, tol=0.005):
    return a is not None and b is not None and abs(a - b) <= tol


def band0(m, f):
    return approx(m.get(f + "_min"), m.get(f + "_max"), 1e-9)


CHECKS = []


def check(desc):
    def deco(fn):
        CHECKS.append((desc, fn))
        return fn
    return deco


def _att(a, b, f):
    import metrics_run as MR
    return MR.attributable(a, b, f)


def _att_set(I, conds, f):
    return {(c, n) for c in conds for n in LADDER
            if _att(I.get((c, n)), I.get(("baseline", n)), f)}


def _cap(D, b, alpha=45.0):
    return max(0, math.floor((10 ** (D / 10) - 1) / 10 ** ((alpha - b) / 10)))


# --------------------------------------------------------------- the ladder
def fleet_sizes(tex):
    """Every fleet size a LaTeX text names: N=<n>, N\\le<n>, N<n, N\\in\\{..\\}, and the
    numbers listed straight after one ("$N=8$, 16 and 24", "from $N=6$ to 22")."""
    tex = re.sub(r"(?<!\\)%.*", "", tex)
    out = []
    lead = re.compile(r"N\s*(?:\{=\}|=|\\leq?|\\geq?|<|>)\s*\$?\s*(\d+)")
    # A number followed by a unit ("and 200\,s") is a measurement, not a fleet size.
    follow = re.compile(r"(?:\s|\$|,|~|\\,|\\dots|\\ldots|\band\b|\bor\b|\bto\b|--)*"
                        r"(\d+)(?![\d.])(?!\s*(?:\\,|\\SI|s\b|dB|h\b|aircraft))")
    for m in lead.finditer(tex):
        out.append(int(m.group(1)))
        pos = m.end()
        while True:
            m2 = follow.match(tex, pos)
            if not m2 or m2.end() == pos:
                break
            out.append(int(m2.group(1)))
            pos = m2.end()
    for m in re.finditer(r"N\s*\\in\s*\\\{([^}]*)\\\}", tex):
        out += [int(x) for x in re.findall(r"\d+", m.group(1))]
    return out


@check("no fleet size above N=24 is named in sec4_results.tex (or the other sections)")
def _(I):
    bad = {}
    for p in TEXT:
        sizes = [s for s in fleet_sizes(io.open(p, encoding="utf-8").read()) if s > 24]
        if sizes:
            bad[os.path.basename(p)] = sizes
    sec4 = len(fleet_sizes(io.open(SEC4, encoding="utf-8").read()))
    return not bad, (f"above 24: {bad}" if bad else
                     f"{sec4} fleet-size mentions in sec4, none above 24")


@check("every cell through N=24 is proven in all four permutations")
def _(I):
    missing = [(c, n) for c in ALL for n in LADDER if (c, n) not in I]
    bad = [(c, n) for c in ALL for n in LADDER
           if (c, n) in I and not (I[(c, n)].get("all_proven") and I[(c, n)]["runs"] == 4)]
    if missing:
        return False, f"not on disk: {missing}"
    return not bad, f"unproven: {bad}" if bad else "36 cells, 4/4 orderings each"


@check("no cell in the study ran under a finite Z3 budget")
def _(I):
    bad = [(c, n) for (c, n), m in I.items() if (m.get("budget_s") or 0) < 100000]
    return not bad, f"budgeted cells: {bad}"


# ------------------------------------------------------------ Sec. II / III
@check("caps sent: Equal D=U=6, other principles D=6 U=30, baseline D=U=30")
def _(I):
    want = {c: (6.0, 30.0) for c in PRINC}
    want.update(equal=(6.0, 6.0), baseline=(30.0, 30.0))
    bad = {(c, n): (m.get("D"), m.get("U")) for (c, n), m in I.items()
           if (m.get("D"), m.get("U")) != want[c]}
    return not bad, f"{bad}" if bad else "as Table I states, every cell"


@check("capacity (eq:capclosed): 2/29/298 at D=6, 9/90/900 at D=10, none at 45 dBA below "
       "3.01 dB, and every principle cell recorded 2/29/298")
def _(I):
    t = {b: _cap(6, b) for b in (45, 55, 65)}
    t10 = {b: _cap(10, b) for b in (45, 55, 65)}
    ok = (t == {45: 2, 55: 29, 65: 298} and t10 == {45: 9, 55: 90, 65: 900}
          and _cap(3.00, 45) == 0 and _cap(3.02, 45) == 1)
    rec = {(c, n): m.get("tile_capacity") for (c, n), m in I.items() if c != "baseline"}
    bad = {k: v for k, v in rec.items()
           if {str(a): b for a, b in (v or {}).items()} != {"45": 2, "55": 29, "65": 298}}
    return ok and not bad, f"D=6 {t}, D=10 {t10}, recorded mismatches {bad}"


@check("shipped settings: caps fill at most 0.44 of a tile at N=16, and the baseline "
       "never enters the shipped protected set (stations 16, 20, 25)")
def _(I):
    """The shipped settings' decibel-form timings left the text in session 5: Experiment 5
    measures both encodings on the study's own setup, so they are no longer quoted."""
    import plans as PL
    R = load(REF)
    util16 = max(m.get("capacity_utilisation_max") or 0
                 for (c, n), m in R.items() if n == 16)
    prot = [s + 1 for s in PL.PROT_BURDEN]
    on = {n: [R[("baseline", n)]["per_station_peak"][s - 1] for s in prot] for n in LADDER}
    ok = (round(util16, 2) == 0.44 and prot == [16, 20, 25]
          and all(v == 0 for vs in on.values() for v in vs))
    return ok, f"N=16 max util {util16:.3f}, set {prot}"


@check("horizon: T=6 at every cell except Utilitarian, which runs at the bound (T=5) "
       "through N=16 and is raised to 6 by phase 1 at N=22, 24")
def _(I):
    bad = {}
    for (c, n), m in I.items():
        want = (5 if n <= 16 else 6) if c == "utilitarian" else 6
        if m.get("T") != want:
            bad[(c, n)] = m.get("T")
    return not bad, f"{bad}" if bad else "as stated"


# -------------------------------------------------------- Exp. 1, congestion
@check("congestion ranges: peak occupancy 1-3 at N=6 and 11-14 at N=24; shared "
       "tile-timesteps 0-3 and 15-18")
def _(I):
    def rng(f, n):
        v = [I[(c, n)][f] for c in ALL]
        return round(min(v)), round(max(v))
    got = {("max_count", 6): rng("max_count", 6), ("max_count", 24): rng("max_count", 24),
           ("shared", 6): rng("shared_tile_timesteps", 6),
           ("shared", 24): rng("shared_tile_timesteps", 24)}
    want = {("max_count", 6): (1, 3), ("max_count", 24): (11, 14),
            ("shared", 6): (0, 3), ("shared", 24): (15, 18)}
    return got == want, f"{got}"


@check("the only attributable congestion differences: Proportional's peak occupancy at "
       "N=8 (5 vs 3.5) and Sufficientarian's shared tile-timesteps at N=16 (11.75 vs 14.25)")
def _(I):
    a = _att_set(I, PRINC, "max_count")
    b = _att_set(I, PRINC, "shared_tile_timesteps")
    vals = (I[("proportional", 8)]["max_count"], I[("baseline", 8)]["max_count"],
            I[("sufficientarian", 16)]["shared_tile_timesteps"],
            I[("baseline", 16)]["shared_tile_timesteps"])
    ok = (a == {("proportional", 8)} and b == {("sufficientarian", 16)}
          and all(approx(x, y) for x, y in zip(vals, (5.0, 3.5, 11.75, 14.25))))
    return ok, f"max_count {a}, shared {b}, values {vals}"


@check("congestion does NOT separate the principles, except Proportional's zero band")
def _(I):
    att = [(c, n) for c in ("equal", "sufficientarian", "prioritarian", "utilitarian")
           for n in LADDER if _att(I.get((c, n)), I.get(("baseline", n)), "max_count")]
    zero = all(band0(I[("proportional", n)], "max_count") for n in LADDER)
    return not att and zero, (f"unexpected attributable: {att}" if att else
                              f"none attributable; Proportional band zero: {zero}")


@check("Equal and Sufficientarian: identical arrival at every size; cap utilisation "
       "0.50-0.75 at N=6, 8; 1.00 in every ordering from N=14 for all five principles")
def _(I):
    same = all(I[("equal", n)]["arrivalPenalty"] == I[("sufficientarian", n)]["arrivalPenalty"]
               and band0(I[("equal", n)], "arrivalPenalty") for n in LADDER)
    small = [I[(c, n)]["capacity_utilisation_max"] for c in ("equal", "sufficientarian")
             for n in (6, 8)]
    full = all(approx(I[(c, n)]["capacity_utilisation_max_min"], 1.0, 1e-9)
               for c in PRINC for n in (14, 16, 22, 24))
    ok = same and approx(min(small), 0.50) and approx(max(small), 0.75) and full
    return ok, f"arrival equal {same}, N=6/8 util {[round(x, 3) for x in small]}, full {full}"


@check("Prioritarian: protected set at 0.00 dB in every ordering; footprint 8-9 tiles "
       "vs the baseline's 10-12, attributable exactly at N=6, 14, 16")
def _(I):
    pk = [I[("prioritarian", n)].get("protected_peak_max",
                                     I[("prioritarian", n)].get("protected_peak"))
          for n in LADDER]
    pr = [I[("prioritarian", n)]["stations_touched"] for n in LADDER]
    bs = [I[("baseline", n)]["stations_touched"] for n in LADDER]
    att = {n for c, n in _att_set(I, ("prioritarian",), "stations_touched")}
    prot = I[("prioritarian", 16)].get("protected_stations")
    ok = (all(p == 0 for p in pk) and 8 <= round(min(pr)) and round(max(pr)) <= 9
          and round(min(bs)) == 10 and round(max(bs)) == 12 and att == {6, 14, 16}
          and sorted(prot) == [4, 8, 14])
    return ok, f"protected peak {pk}, tiles {pr}, baseline {bs}, attributable {sorted(att)}"


@check("Utilitarian and the baseline fly the shortest-path floor with no hover at every "
       "size; Utilitarian's congestion never separates from the baseline")
def _(I):
    fl = all(I[(c, n)]["extra_vs_floor_max"] == 0 and I[(c, n)]["hover_steps_total_max"] == 0
             for c in ("utilitarian", "baseline") for n in LADDER)
    sep = [f for f in ("max_count", "shared_tile_timesteps", "stations_touched")
           if _att_set(I, ("utilitarian",), f)]
    return fl and not sep, f"on the floor {fl}, separating metrics {sep}"


@check("Proportional: the same 6 tiles (vertiports 5, 11, 18 and 55 dBA stations 9, 12, "
       "13) at every size, attributable N=6-22 only; peak occupancy 3,5,8,10,12,14, zero band")
def _(I):
    import payload as P
    tiles = {n: [i + 1 for i, v in enumerate(I[("proportional", n)]["per_station_peak"])
                 if v and v > 0] for n in LADDER}
    same = all(t == [5, 9, 11, 12, 13, 18] for t in tiles.values())
    ports = sorted(v + 1 for v in P.vertiport_indices()) == [5, 11, 18]
    amb = all(P.BASELINE[s - 1] == 55 for s in (9, 12, 13))
    six = all(I[("proportional", n)]["stations_touched_min"] == 6
              and I[("proportional", n)]["stations_touched_max"] == 6 for n in LADDER)
    att = {n for _c, n in _att_set(I, ("proportional",), "stations_touched")}
    occ = [(I[("proportional", n)]["max_count"], band0(I[("proportional", n)], "max_count"))
           for n in LADDER]
    ok = (same and ports and amb and six and att == {6, 8, 14, 16, 22}
          and occ == [(3.0, True), (5.0, True), (8.0, True), (10.0, True), (12.0, True),
                      (14.0, True)])
    return ok, f"tiles {tiles[16]}, attributable {sorted(att)}, occupancy {occ}"


# ------------------------------------------------------- Exp. 2, travel time
@check("travel: every principle attains the baseline's arrival (18, 22, 40, 44) at N<=16 on "
       "shortest paths with no hover; +3 at N=22, 24 (65/62, 69/66), zero band, attributable")
def _(I):
    lo = all(I[(c, n)]["arrivalPenalty"] == I[("baseline", n)]["arrivalPenalty"]
             and band0(I[(c, n)], "arrivalPenalty") and I[(c, n)]["extra_vs_floor_max"] == 0
             and I[(c, n)]["hover_steps_total_max"] == 0
             for c in ALL for n in (6, 8, 14, 16))
    base = [I[("baseline", n)]["arrivalPenalty"] for n in LADDER]
    hi = all(approx(I[(c, n)]["arrivalPenalty"], I[("baseline", n)]["arrivalPenalty"] + 3)
             and band0(I[(c, n)], "arrivalPenalty")
             and _att(I[(c, n)], I[("baseline", n)], "arrivalPenalty")
             for c in PRINC for n in (22, 24))
    ok = lo and hi and base == [18, 22, 40, 44, 62, 66]
    return ok, f"free to 16 {lo}, +3 at 22/24 {hi}, baseline {base}"


@check("the caps pay in DISTANCE at N=22 and 24, attributably")
def _(I):
    """Means over four permutations, not a rounded integer. The first draft of IV-C
    said "3 fleet-hops" for Equal, read off a table that printed the mean with zero
    decimals; the mean is 2.75 and the individual runs are 2 or 3."""
    want = {("equal", 22): 2.75, ("equal", 24): 2.75,
            ("sufficientarian", 22): 3.00, ("sufficientarian", 24): 2.75,
            ("prioritarian", 22): 2.50, ("prioritarian", 24): 2.50}
    got = {}
    for (c, n), h in want.items():
        a, b = I[(c, n)], I[("baseline", n)]
        got[(c, n)] = round(a["extra_vs_baseline"], 2)
        if not approx(a["extra_vs_baseline"], h, 0.01):
            return False, f"means differ from the text: {got}"
        if not _att(a, b, "extra_vs_baseline"):
            return False, f"not attributable at {(c, n)}: {got}"
    return True, f"mean extra hops = {got}, all attributable"


@check("the objectives pay in DEPARTURE TIME, not distance: no extra hop at any size, "
       "25 and 27 against 22 and 24 at N=22, 24, zero band")
def _(I):
    got = {}
    for c in ("utilitarian", "proportional"):
        if any(I[(c, n)]["extra_vs_floor_max"] != 0 for n in LADDER):
            return False, f"{c} flew extra distance"
        for n, want in ((22, 25), (24, 27)):
            a, b = I[(c, n)], I[("baseline", n)]
            got[(c, n)] = (a["departure_delay_total"], b["departure_delay_total"])
            if not (approx(a["departure_delay_total"], want) and band0(a, "departure_delay_total")
                    and band0(b, "departure_delay_total")
                    and approx(b["departure_delay_total"], n)
                    and _att(a, b, "departure_delay_total")):
                return False, f"{got}"
    return True, f"(delay, baseline delay) = {got}"


# ------------------------------------------------------------ Exp. 3, noise
@check("from N=14 every principle pins peak added noise at 4.77 dB with a ZERO band")
def _(I):
    bad = {}
    for c in PRINC:
        for n in (14, 16, 22, 24):
            m = I[(c, n)]
            if not (approx(m["peak_added"], 4.7712, 0.01) and band0(m, "peak_added")):
                bad[(c, n)] = (round(m["peak_added"], 2), m["peak_added_min"], m["peak_added_max"])
    return not bad, f"{bad}" if bad else "all five, all four sizes, band 0.00"


@check("the baseline's peak over the same range averages 5.64/5.88/6.70/7.70 with bands "
       "2.22/2.22/1.76/3.98, spans 4.77-10.00 dB, and clears the band at N=22 only")
def _(I):
    want = {14: (5.64, 2.22), 16: (5.88, 2.22), 22: (6.70, 1.76), 24: (7.70, 3.98)}
    got = {}
    for n, (pk, fl) in want.items():
        m = I[("baseline", n)]
        got[n] = (round(m["peak_added"], 2), round(m["floor_peak_added"], 2))
        if not (approx(m["peak_added"], pk, 0.01) and approx(m["floor_peak_added"], fl, 0.01)):
            return False, f"{got}"
    lo = min(I[("baseline", n)]["peak_added_min"] for n in want)
    hi = max(I[("baseline", n)]["peak_added_max"] for n in want)
    att = {n for _c, n in _att_set(I, PRINC, "peak_added")}
    every22 = all(_att(I[(c, 22)], I[("baseline", 22)], "peak_added") for c in PRINC)
    ok = approx(lo, 4.77, 0.01) and approx(hi, 10.00, 0.01) and att == {22} and every22
    return ok, f"(peak, band) = {got}, span {lo:.2f}-{hi:.2f}, attributable at {sorted(att)}"


@check("peaks at N=6 and 8 lie between 3.01 and 3.89 dB and none separates from the baseline")
def _(I):
    v = [I[(c, n)]["peak_added"] for c in PRINC for n in (6, 8)]
    att = [(c, n) for c, n in _att_set(I, PRINC, "peak_added") if n in (6, 8)]
    ok = approx(min(v), 3.01, 0.01) and approx(max(v), 3.89, 0.01) and not att
    return ok, f"{min(v):.2f}-{max(v):.2f}, attributable {att}"


@check("capacity table at N=24: the 45 dBA tier runs at 0.88-1.00 under every principle, "
       "the 65 dBA tier at 0.02")
def _(I):
    t45 = [round(I[(c, 24)]["capacity_utilisation_by_tier"]["45"], 2) for c in PRINC]
    t65 = [round(I[(c, 24)]["capacity_utilisation_by_tier"]["65"], 2) for c in PRINC]
    ok = min(t45) == 0.88 and max(t45) == 1.00 and all(x == 0.02 for x in t65)
    return ok, f"45 dBA {t45}, 65 dBA {t65}"


@check("Proportional summed noise 10.9/11.6/19.2/19.7/28.5/29.0 vs 17.6/19.4/35.7/37.7/"
       "48.8/47.9, zero band, attributable at all but N=24 (baseline band 24.9 dB)")
def _(I):
    pw = [10.9, 11.6, 19.2, 19.7, 28.5, 29.0]
    bw = [17.6, 19.4, 35.7, 37.7, 48.8, 47.9]
    pg = [round(I[("proportional", n)]["total_added"], 1) for n in LADDER]
    bg = [round(I[("baseline", n)]["total_added"], 1) for n in LADDER]
    zero = all(band0(I[("proportional", n)], "total_added") for n in LADDER)
    att = {n for _c, n in _att_set(I, ("proportional",), "total_added")}
    fl24 = round(I[("baseline", 24)]["floor_total_added"], 1)
    ok = pg == pw and bg == bw and zero and att == {6, 8, 14, 16, 22} and fl24 == 24.9
    return ok, f"prop {pg}, base {bg}, attributable {sorted(att)}, band at 24 {fl24}"


@check("Proportional occupies 13 tile-timesteps at N<=16 against the baseline's 16-19, "
       "attributably, with the same airborne time")
def _(I):
    p = [I[("proportional", n)]["occupied_tile_timesteps"] for n in (6, 8, 14, 16)]
    b = [I[("baseline", n)]["occupied_tile_timesteps"] for n in (6, 8, 14, 16)]
    att = all(_att(I[("proportional", n)], I[("baseline", n)], "occupied_tile_timesteps")
              for n in (6, 8, 14, 16))
    same = all(I[("proportional", n)]["total_trip_hops"] == I[("baseline", n)]["total_trip_hops"]
               for n in (6, 8, 14, 16))
    ok = (all(x == 13 for x in p) and round(min(b)) == 16 and round(max(b)) == 19
          and att and same)
    return ok, f"prop {p}, base {b}, attributable {att}, same airborne time {same}"


@check("Prioritarian summed noise 29.7 and 28.0 vs 35.7 and 37.7, attributable exactly at "
       "N=14, 16; Equal, Sufficientarian, Utilitarian never attributable on summed noise")
def _(I):
    got = [round(I[(c, n)]["total_added"], 1) for c in ("prioritarian", "baseline")
           for n in (14, 16)]
    att = {n for _c, n in _att_set(I, ("prioritarian",), "total_added")}
    others = _att_set(I, ("equal", "sufficientarian", "utilitarian"), "total_added")
    ok = got == [29.7, 28.0, 35.7, 37.7] and att == {14, 16} and not others
    return ok, f"{got}, attributable {sorted(att)}, others {others}"


@check("Proportional's total-noise reduction is attributable at five of six sizes")
def _(I):
    hits = [n for n in LADDER
            if _att(I[("proportional", n)], I[("baseline", n)], "total_added")]
    return len(hits) == 5, f"attributable at N={hits}"


# ------------------------------------------------------ Exp. 4, solve time
@check("solve time: Equal, Sufficientarian, Prioritarian within 2x of the baseline at every "
       "size; baseline 5.9 s at N=6 and 200 s at N=24; eight solves in parallel")
def _(I):
    r = {(c, n): I[(c, n)]["wall"] / I[("baseline", n)]["wall"]
         for c in ("equal", "sufficientarian", "prioritarian") for n in LADDER}
    par = {m.get("runner_par") for m in I.values()}
    ok = (all(0.5 <= x <= 2 for x in r.values())
          and round(I[("baseline", 6)]["wall"], 1) == 5.9
          and round(I[("baseline", 24)]["wall"]) == 200 and par == {8})
    return ok, f"ratio {min(r.values()):.2f}-{max(r.values()):.2f}, par {par}"


@check("Utilitarian in count form is the CHEAPEST condition to solve through N=16 "
       "(1.6 and 8.5 s against 5.9 and 55.3 s), ranges disjoint")
def _(I):
    bad = {}
    for n in (6, 8, 14, 16):
        u = I[("utilitarian", n)]
        others = [I[(c, n)] for c in ALL if c != "utilitarian"]
        if not all(u["wall_max"] < o["wall_min"] for o in others):
            bad[n] = round(u["wall"], 1)
    vals = [round(I[(c, n)]["wall"], 1) for c in ("utilitarian", "baseline") for n in (6, 16)]
    ok = not bad and vals == [1.6, 8.5, 5.9, 55.3]
    return ok, f"{vals}, not fastest at {bad}"


@check("Proportional is the slowest condition at N=22 and 24 (227 and 439 s), ranges disjoint")
def _(I):
    ok = True
    for n in (22, 24):
        p = I[("proportional", n)]
        ok &= all(p["wall_min"] > I[(c, n)]["wall_max"] for c in ALL if c != "proportional")
    vals = [round(I[("proportional", n)]["wall"]) for n in (22, 24)]
    return ok and vals == [227, 439], f"{vals}"


# ----------------------------------------------------- Table II and abstract
@check("response table: mean wall at N=24 is 107/109/191/151/439/200 s, and 439 s is the "
       "largest mean wall on the ladder")
def _(I):
    got = [round(I[(c, 24)]["wall"]) for c in ALL]
    top = max(I.values(), key=lambda m: m["wall"])
    ok = got == [107, 109, 191, 151, 439, 200] and (top["condition"], top["N"]) == (
        "proportional", 24)
    return ok, f"{got}, largest {top['condition']} N={top['N']}"


@check("response table activation sizes: distance attributable exactly at N=22, 24 for "
       "Equal/Sufficientarian/Prioritarian; delay exactly at N=22, 24 for Utilitarian/"
       "Proportional; peak fixed from N=14 and not at N=8; baseline peak banded from N=14")
def _(I):
    dist = {c: {n for _c, n in _att_set(I, (c,), "extra_vs_baseline")} for c in PRINC}
    dly = {c: {n for _c, n in _att_set(I, (c,), "departure_delay_total")} for c in PRINC}
    ok = (all(dist[c] == {22, 24} and not dly[c]
              for c in ("equal", "sufficientarian", "prioritarian"))
          and all(dly[c] == {22, 24} and not dist[c] for c in ("utilitarian", "proportional")))
    not8 = all(not (approx(I[(c, 8)]["peak_added"], 4.7712, 0.01) and band0(I[(c, 8)], "peak_added"))
               for c in PRINC)
    base = all(I[("baseline", n)]["floor_peak_added"] > 0 for n in (14, 16, 22, 24))
    return ok and not8 and base, f"distance {dist}, delay {dly}"


@check("abstract: Proportional cuts summed added noise from 37.7 to 19.7 dB at N=16")
def _(I):
    got = (round(I[("baseline", 16)]["total_added"], 1),
           round(I[("proportional", 16)]["total_added"], 1))
    return got == (37.7, 19.7), f"{got}"


# ---------------------------------------------- Exp. 5, the two encodings
# encoding.py writes results/encoding.json from fleet_main.jsonl and fleet_db.jsonl; the
# decibel-form cells go through the ladder's own metrics pipeline into
# fleet_db_metrics.json. These checks are the invariants the comparison rests on; the
# numbers the text quotes are asserted below them.
ENC = os.path.join(RES, "encoding.json")
DBJ = os.path.join(RES, "fleet_db.jsonl")


def enc():
    return json.load(io.open(ENC, encoding="utf-8"))


def db_rows():
    out = []
    for l in io.open(DBJ, encoding="utf-8"):
        try:
            out.append(json.loads(l))
        except ValueError:
            pass
    return out


@check("Exp. 5: the decibel objective is re-derived exactly -- every decibel-form row "
       "reproduces the solver's reported value")
def _(I):
    st = enc()["selftest"]
    return st["checked"] > 0 and not st["mismatches"], (
        f"{st['checked']} rows reproduced" if not st["mismatches"]
        else f"mismatches {st['mismatches'][:2]}")


@check("Exp. 5: proven decibel orderings agree on one J* per cell; every count routing "
       "has the decibel run's horizon (so it is feasible for the decibel problem) and none "
       "beats J*")
def _(I):
    bad = []
    for c in enc()["cells"]:
        if "J_star" in c and (not c["J_star_consistent"] or c["count_beats_star"]):
            bad.append((c["principle"], c["N"], "J*"))
        if not c["T_match"]:
            bad.append((c["principle"], c["N"], "horizon"))
    n = sum(1 for c in enc()["cells"] if "J_star" in c)
    return not bad, f"{bad}" if bad else f"{n} cells with a proven J*, all consistent"


@check("Exp. 5: every decibel run is an answer (proven or verified feasible, no fallback, "
       "no phase-1 stop), ran with no Z3 budget, and lies on the N <= 24 ladder")
def _(I):
    rows = db_rows()
    bad = [(r["key"], r.get("status"), r.get("optimality")) for r in rows
           if r.get("status") != "sat" or r.get("optimality") not in ("optimal", "partial")
           or (r.get("budget_s") or 0) < 100000 or r.get("N", 99) > 24]
    return bool(rows) and not bad, f"{len(rows)} rows" + (f", bad {bad[:3]}" if bad else "")


def _cell(p, n):
    return next(c for c in enc()["cells"] if c["principle"] == p and c["N"] == n)


def _fc(p, n):
    return next(r for r in enc()["form_compare"] if r["principle"] == p and r["N"] == n)


@check("Exp. 5 Utilitarian N=6, 8: decibel form proves in 49 and 296 s vs 1.6 and 2.4 s "
       "(30x, 124x); count routings score 20.79 and 20.37 dB vs J* 9.52 and 10.24 dB, loss "
       "11.27 and 10.13 dB (118 %, 99 %), attributable")
def _(I):
    got = []
    for n in (6, 8):
        c = _cell("utilitarian", n)
        if len(c["db_proven"]) != 4:
            return None, f"N={n} decibel cell not proven 4/4 yet"
        got.append((round(c["wall_db"]["mean"]), round(c["wall_count"]["mean"], 1),
                    round(c["speedup"]), round(c["J_count"]["mean"], 2), round(c["J_star"], 2),
                    round(c["loss_abs"]["mean"], 2), round(100 * c["loss"]["mean"]),
                    c["loss_attributable"]))
    want = [(49, 1.6, 30, 20.79, 9.52, 11.27, 118, True),
            (296, 2.4, 124, 20.37, 10.24, 10.13, 99, True)]
    return got == want, f"{got}"


@check("Exp. 5 Utilitarian N=6, 8: decibel form occupies 10 tile-timesteps vs 15.25 and "
       "16.25 and departs 7 vs 6 and 9 vs 8 aircraft-timesteps, both attributable; peak and "
       "footprint within the band")
def _(I):
    got = []
    for n in (6, 8):
        r = _fc("utilitarian", n)
        o, d = r["occupied_tile_timesteps"], r["departure_delay_total"]
        got.append((o["db"], o["count"], o["attributable"], d["db"], d["count"],
                    d["attributable"], r["peak_added"]["attributable"],
                    r["stations_touched"]["attributable"]))
    want = [(10.0, 15.25, True, 7.0, 6.0, True, False, False),
            (10.0, 16.25, True, 9.0, 8.0, True, False, False)]
    return got == want, f"{got}"


@check("Exp. 5 Proportional N=6, 8: decibel form 2655 and 17793 s vs 4.2 and 8.2 s "
       "(625x, 2159x); count routings 128.00 and 134.43 in every ordering vs J* 109.43 and "
       "115.85, loss 18.58 (17 %, 16 %), attributable; summed 9.60/10.31 vs 10.92/11.63 dB, "
       "occupied 11 vs 13, peak 4.77 vs 3.01 dB, departure 9 vs 6 and 11 vs 8, attributable")
def _(I):
    want = {6: ((2655, 4.2, 625, 128.0, 128.0, 109.43, 18.58, 17, True),
                ((9.6, 10.92, True), (11.0, 13.0, True), (4.77, 3.01, True), (9.0, 6.0, True))),
            8: ((17793, 8.2, 2159, 134.43, 134.43, 115.85, 18.58, 16, True),
                ((10.31, 11.63, True), (11.0, 13.0, True), (4.77, 3.01, True),
                 (11.0, 8.0, True)))}
    got = {}
    for n in (6, 8):
        c, r = _cell("proportional", n), _fc("proportional", n)
        if len(c["db_proven"]) != 4:
            return None, f"N={n} decibel cell not proven 4/4 yet"
        g = (round(c["wall_db"]["mean"]), round(c["wall_count"]["mean"], 1),
             round(c["speedup"]), round(c["J_count"]["min"], 2), round(c["J_count"]["max"], 2),
             round(c["J_star"], 2), round(c["loss_abs"]["mean"], 2),
             round(100 * c["loss"]["mean"]), c["loss_attributable"])
        m = tuple((round(r[f]["db"], 2), round(r[f]["count"], 2), r[f]["attributable"])
                  for f in ("total_added", "occupied_tile_timesteps", "peak_added",
                            "departure_delay_total"))
        got[n] = (g, m)
    return got == want, f"{got}"


@check("Exp. 5 Utilitarian N=14, 16: 2 and 1 decibel orderings proved in a mean of 3.5 and "
       "12.3 h; count routings 35.66 and 39.31 dB vs J* 19.18 and 19.72, loss 86 % and 99 %, "
       "attributable")
def _(I):
    got = []
    for n in (14, 16):
        c = _cell("utilitarian", n)
        got.append((len(c["db_proven"]), round(c["wall_db"]["mean"] / 3600, 1),
                    round(c["J_count"]["mean"], 2), round(c["J_star"], 2),
                    round(100 * c["loss"]["mean"]), c["loss_attributable"]))
    return got == [(2, 3.5, 35.66, 19.18, 86, True), (1, 12.3, 39.31, 19.72, 99, True)], f"{got}"


@check("Exp. 5 reach: H = 20.0 h; decibel proven frontier N=16 (Utilitarian) and N=8 "
       "(Proportional); 19 proved, 8 harvested, 21 never started of 48; 7 of 8 harvested "
       "report no finite bound, Utilitarian N=16's closed at J*; count forms' slowest run "
       "472 s")
def _(I):
    e = enc()
    rows = db_rows()
    proven = [r for r in rows if r.get("optimality") == "optimal"]
    harv = [r for r in rows if r.get("optimality") == "partial"]
    front = {p: max(c["N"] for c in e["cells"] if c["principle"] == p and c["db_proven"])
             for p in ("utilitarian", "proportional")}
    nobound = [r for r in harv if r.get("tier1_lower") is None]
    closed = [r for r in harv if r.get("tier1_lower") is not None]
    closed_ok = (len(closed) == 1 and "utilitarian_db|1.0|" in closed[0]["key"]
                 and abs(closed[0]["tier1_lower"] - closed[0]["tier1_incumbent"]) < 1e-9
                 and round(_cell("utilitarian", 16)["J_db_by_perm"]["1"], 2) == 19.72)
    slow = max(c["wall_count"]["max"] for c in e["cells"])
    ok = (round(e["H_s"] / 3600, 1) == 20.0 and front == {"utilitarian": 16, "proportional": 8}
          and (len(proven), len(harv), 48 - len(rows)) == (19, 8, 21)
          and len(nobound) == 7 and closed_ok and round(slow) == 472)
    return ok, (f"H {e['H_s'] / 3600:.2f} h, frontier {front}, proven/harvested/absent "
                f"{len(proven)}/{len(harv)}/{48 - len(rows)}, no bound {len(nobound)}, "
                f"closed {closed_ok}, slowest count run {slow:.1f} s")


@check("Exp. 5 lower bounds: count routings lose at least 55 % and 40 % (Utilitarian N=22, "
       "24) and 1.3, 1.2, 0.0 % (Proportional N=14, 16, 22); at N=24 the count routing's "
       "331.37 lies below the decibel incumbent's 334.30, reached in 14.8 h")
def _(I):
    lb = {(p, n): round(100 * _cell(p, n)["loss_lower_bound"]["mean"], 1)
          for p, n in (("utilitarian", 22), ("utilitarian", 24), ("proportional", 14),
                       ("proportional", 16), ("proportional", 22))}
    c24 = _cell("proportional", 24)
    inc = c24["J_db_by_perm"]["0"]
    ok = (round(lb[("utilitarian", 22)]) == 55 and round(lb[("utilitarian", 24)]) == 40
          and lb[("proportional", 14)] == 1.3 and lb[("proportional", 16)] == 1.2
          and lb[("proportional", 22)] == 0.0
          and round(c24["J_count"]["mean"], 2) == 331.37 and round(inc, 2) == 334.30
          and round(c24["db_wall"]["0"] / 3600, 1) == 14.8
          and all(not c.get("loss") for c in enc()["cells"]
                  if (c["principle"], c["N"]) in lb))
    return ok, f"{lb}, N=24 count {c24['J_count']['mean']:.2f} vs incumbent {inc:.2f}"


@check("Exp. 5 trade-off: proven decibel runs span 49 s to 12.3 h; speed-ups 30-2159x where "
       "all four orderings prove; loss 16-17 % (Proportional) and 86-118 % (Utilitarian); "
       "above N=8 Proportional's count routing is within 1.4 % of, or below, the best "
       "decibel routing reached (N=14 is 1.31 %, so 'within 1.3 %' would be false)")
def _(I):
    e = enc()["cells"]
    sp = [c["speedup"] for c in e if c.get("speedup")]
    loss = {p: sorted(round(100 * c["loss"]["mean"]) for c in e if c["principle"] == p and c.get("loss"))
            for p in ("utilitarian", "proportional")}
    walls = [w for c in e for k, w in (c.get("db_wall") or {}).items()
             if int(k) in c["db_proven"]]
    lo_mean = min(c["wall_db"]["mean"] for c in e if len(c["db_proven"]) == 4)
    prop_hi = [c for c in e if c["principle"] == "proportional" and c["N"] > 8]
    within = all(c["J_count"]["mean"] <= 1.014 * c["J_best_known"] + 1e-9 for c in prop_hi)
    ok = (round(min(sp)) == 30 and round(max(sp)) == 2159
          and (loss["proportional"][0], loss["proportional"][-1]) == (16, 17)
          and (loss["utilitarian"][0], loss["utilitarian"][-1]) == (86, 118)
          and round(lo_mean) == 49 and round(max(walls) / 3600, 1) == 12.3 and within)
    return ok, (f"speed-ups {min(sp):.1f}-{max(sp):.1f}, loss {loss}, proven walls "
                f"{lo_mean:.1f} s .. {max(walls) / 3600:.2f} h, Prop within 1.3 %: {within}")


@check("Exp. 5 decibel forms against the baseline at N=6 and 8: 6 tiles (attributably narrower), "
       "fewer occupied tile-timesteps than their count forms, 1 and 3 aircraft-timesteps more "
       "departure delay with no extra hop, summed 9.54 and 9.60 dB vs 17.6 at N=6, peak "
       "4.77 dB with zero band; all attributable where stated")
def _(I):
    import metrics_run as MR
    dbm = {(m["condition"], m["N"]): m
           for m in json.load(io.open(os.path.join(RES, "fleet_db_metrics.json"),
                                      encoding="utf-8"))}
    bad = []
    for p, extra in (("utilitarian", 1), ("proportional", 3)):
        for n in (6, 8):
            a, b, cnt = dbm[(p + "_db", n)], I[("baseline", n)], I[(p, n)]
            if not (a["runs"] == 4 and a["all_proven"]):
                bad.append((p, n, "not 4/4"))
                continue
            if not (a["stations_touched"] == 6 and MR.attributable(a, b, "stations_touched")):
                bad.append((p, n, "tiles"))
            if not (a["occupied_tile_timesteps"] < cnt["occupied_tile_timesteps"]
                    and MR.attributable(a, cnt, "occupied_tile_timesteps")):
                bad.append((p, n, "occupied"))
            if not (a["departure_delay_total"] - b["departure_delay_total"] == extra
                    and MR.attributable(a, b, "departure_delay_total")
                    and a["extra_vs_baseline_max"] == 0):
                bad.append((p, n, "delay"))
            if not (approx(a["peak_added"], 4.7712, 0.01) and band0(a, "peak_added")):
                bad.append((p, n, "peak"))
    s6 = (round(dbm[("utilitarian_db", 6)]["total_added"], 2),
          round(dbm[("proportional_db", 6)]["total_added"], 2),
          round(I[("baseline", 6)]["total_added"], 1))
    att6 = all(MR.attributable(dbm[(p + "_db", 6)], I[("baseline", 6)], "total_added")
               for p in ("utilitarian", "proportional"))
    ok = not bad and s6 == (9.54, 9.6, 17.6) and att6
    return ok, f"bad {bad}, summed at N=6 {s6}, attributable {att6}"


def _dbm():
    return {(m["condition"], m["N"]): m
            for m in json.load(io.open(os.path.join(RES, "fleet_db_metrics.json"),
                                       encoding="utf-8"))}


@check("Exp. 1-3 report the decibel forms where an ordering proved: exactly N=6, 8 for both "
       "and N=14, 16 for Utilitarian")
def _(I):
    got = sorted(k for k, m in _dbm().items() if (m.get("runs_proven") or 0) > 0)
    want = sorted([(p + "_db", n) for p in ("utilitarian", "proportional") for n in (6, 8)]
                  + [("utilitarian_db", 14), ("utilitarian_db", 16)])
    return got == want, f"cells with a proven ordering {got}"


@check("Utilitarian decibel form at N=14, 16, every ordering that ran agreeing: 6 tiles, fewer "
       "occupied tile-timesteps than the count form, no extra hop, 12 and 16 aircraft-timesteps "
       "more departure delay than the baseline; summed 19.2 and 19.7 dB against 35.7 and 39.3 "
       "in count form; Proportional's count form within 0.01 dB of it at the baseline's "
       "arrival, 12 and 16 aircraft-timesteps earlier")
def _(I):
    dbm = _dbm()
    same = ("stations_touched", "occupied_tile_timesteps", "extra_vs_floor",
            "departure_delay_total", "arrivalPenalty", "total_added")
    bad = []
    for n, extra, s_db, s_cnt in ((14, 12, 19.2, 35.7), (16, 16, 19.7, 39.3)):
        a = dbm[("utilitarian_db", n)]
        cnt, b, pc = I[("utilitarian", n)], I[("baseline", n)], I[("proportional", n)]
        if (a.get("runs_proven") or 0) < 1:
            bad.append((n, "no proven ordering"))
        if a["runs"] > 1 and not all(band0(a, f) for f in same):
            bad.append((n, "orderings disagree"))
        if a["stations_touched"] != 6 or a["extra_vs_floor"] != 0:
            bad.append((n, "tiles/hops"))
        if not a["occupied_tile_timesteps"] < cnt["occupied_tile_timesteps"]:
            bad.append((n, "occupied"))
        if a["departure_delay_total"] - b["departure_delay_total"] != extra:
            bad.append((n, "delay"))
        if not (pc["arrivalPenalty"] == b["arrivalPenalty"]
                and a["arrivalPenalty"] - pc["arrivalPenalty"] == extra):
            bad.append((n, "arrival"))
        if not (round(a["total_added"], 1) == s_db and round(cnt["total_added"], 1) == s_cnt
                and abs(pc["total_added"] - a["total_added"]) < 0.01
                and band0(pc, "total_added")):
            bad.append((n, "summed"))
    return not bad, f"bad {bad}"


@check("capacity: the decibel forms fill the 45 dBA tier (1.00) at every size where an "
       "ordering proved, against 0.50-0.80 for their count forms; two aircraft over a 45 dBA "
       "tile add 4.77 dB against 6.02 over two")
def _(I):
    dbm = _dbm()
    cells = [(p, n) for p in ("utilitarian", "proportional") for n in (6, 8)]
    cells += [("utilitarian", 14), ("utilitarian", 16)]
    dbv = [dbm[(p + "_db", n)]["capacity_utilisation_by_tier"]["45"] for p, n in cells]
    cv = [I[(p, n)]["capacity_utilisation_by_tier"]["45"] for p, n in cells]

    def d(k, b=45.0):
        return 10 * math.log10(1 + k * 10 ** ((45.0 - b) / 10))
    ok = (all(approx(x, 1.0, 1e-9) for x in dbv)
          and (round(min(cv), 2), round(max(cv), 2)) == (0.5, 0.8)
          and round(d(2), 2) == 4.77 and round(2 * d(1), 2) == 6.02)
    return ok, f"decibel {dbv}, count {[round(x, 2) for x in cv]}"


def main():
    I = load()
    print(f"{len(I)} cells on disk at N <= {max(LADDER)}\n")
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
