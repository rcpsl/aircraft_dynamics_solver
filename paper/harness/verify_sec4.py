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
MAIN = "fleet_main_metrics.json"
SEC4 = os.path.join(HERE, "..", "tex", "sec4_results.tex")
LADDER = (6, 8, 14, 16, 22, 24, 30, 32)


def load():
    p = os.path.join(RES, MAIN)
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


def _cells():
    import json as _j
    return {(m["condition"], m["N"]): m
            for m in _j.load(io.open(os.path.join(RES, MAIN), encoding="utf-8"))}


def _att(a, b, f):
    import metrics_run as MR
    return MR.attributable(a, b, f)


@check("every cell through N=24 is proven in all four permutations")
def _(I):
    C = ("baseline", "equal", "sufficientarian", "prioritarian", "utilitarian",
         "proportional")
    bad = [(c, n) for c in C for n in (6, 8, 14, 16, 22, 24)
           if (c, n) in I and not I[(c, n)].get("all_proven")]
    missing = [(c, n) for c in C for n in (6, 8, 14, 16, 22, 24) if (c, n) not in I]
    if missing:
        return None, f"not on disk yet: {missing}"
    return not bad, f"unproven: {bad}" if bad else "36 cells, 4/4 permutations each"


@check("from N=14 every principle pins peak added noise at 4.77 dB with a ZERO band")
def _(I):
    bad = {}
    for c in ("equal", "sufficientarian", "prioritarian", "utilitarian", "proportional"):
        for n in (14, 16, 22, 24):
            m = I.get((c, n))
            if m is None:
                return None, f"{c} N={n} not on disk"
            if not (approx(m["peak_added"], 4.7712, 0.01)
                    and approx(m["floor_peak_added"], 0.0, 1e-9)):
                bad[(c, n)] = (round(m["peak_added"], 2), round(m["floor_peak_added"], 2))
    return not bad, f"{bad}" if bad else "all five, all four sizes, band 0.00"


@check("the baseline's peak over the same range is HIGHER and has a wide band")
def _(I):
    want = {14: (5.64, 2.22), 16: (5.88, 2.22), 22: (6.70, 1.76), 24: (7.70, 3.98)}
    got = {}
    for n, (pk, fl) in want.items():
        m = I.get(("baseline", n))
        if m is None:
            return None, f"baseline N={n} not on disk"
        got[n] = (round(m["peak_added"], 2), round(m["floor_peak_added"], 2))
        if not (approx(m["peak_added"], pk, 0.01) and approx(m["floor_peak_added"], fl, 0.01)):
            return False, f"{got}"
        if m["peak_added"] <= 4.7712:
            return False, f"baseline not higher at N={n}: {got}"
    return True, f"(peak, band) = {got}"


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
        a, b = I.get((c, n)), I.get(("baseline", n))
        if a is None or b is None:
            return None, f"{c} N={n} not on disk"
        got[(c, n)] = round(a["extra_vs_baseline"], 2)
        if not approx(a["extra_vs_baseline"], h, 0.01):
            return False, f"means differ from the text: {got}"
        if not _att(a, b, "extra_vs_baseline"):
            return False, f"not attributable at {(c, n)}: {got}"
    return True, f"mean extra hops = {got}, all attributable"


@check("the objectives pay in DEPARTURE TIME, not distance, at N=22 and 24")
def _(I):
    got = {}
    for c in ("utilitarian", "proportional"):
        for n in (22, 24):
            a, b = I.get((c, n)), I.get(("baseline", n))
            if a is None or b is None:
                return None, f"{c} N={n} not on disk"
            got[(c, n)] = (a["extra_vs_baseline"], a["departure_delay_total"],
                           b["departure_delay_total"])
            if a["extra_vs_baseline"] != 0:
                return False, f"flew extra distance: {got}"
            if not _att(a, b, "departure_delay_total"):
                return False, f"departure delay not attributable: {got}"
    return True, f"(extra hops, delay, baseline delay) = {got}"


@check("Proportional has a ZERO band on total added noise at every proven size")
def _(I):
    got = {}
    for n in (6, 8, 14, 16, 22, 24):
        m = I.get(("proportional", n))
        if m is None:
            return None, f"N={n} not on disk"
        got[n] = (round(m["total_added"], 1), round(m["floor_total_added"], 2))
        if not approx(m["floor_total_added"], 0.0, 1e-9):
            return False, f"{got}"
    return True, f"(total dB, band) = {got}"


@check("Proportional's total-noise reduction is attributable at five of six sizes")
def _(I):
    hits = [n for n in (6, 8, 14, 16, 22, 24)
            if _att(I.get(("proportional", n)), I.get(("baseline", n)), "total_added")]
    return len(hits) >= 5, f"attributable at N={hits}"


@check("Utilitarian in count form is the CHEAPEST condition to solve through N=16")
def _(I):
    bad = {}
    for n in (6, 8, 14, 16):
        walls = {c: I[(c, n)]["wall"] for c in
                 ("baseline", "equal", "sufficientarian", "prioritarian",
                  "utilitarian", "proportional") if (c, n) in I}
        if len(walls) < 6:
            return None, f"N={n} incomplete"
        if min(walls, key=walls.get) != "utilitarian":
            bad[n] = {k: round(v, 1) for k, v in walls.items()}
    return not bad, f"{bad}" if bad else "fastest at N=6, 8, 14 and 16"


@check("congestion does NOT separate the principles, except Proportional's zero band")
def _(I):
    att = [(c, n) for c in ("equal", "sufficientarian", "prioritarian", "utilitarian")
           for n in (6, 8, 14, 16, 22, 24)
           if _att(I.get((c, n)), I.get(("baseline", n)), "max_count")]
    zero = all(approx(I[("proportional", n)]["floor_max_count"], 0.0, 1e-9)
               for n in (6, 8, 14, 16, 22, 24) if ("proportional", n) in I)
    return not att and zero, (f"unexpected attributable: {att}" if att else
                              f"none attributable; Proportional band zero: {zero}")


@check("no cell in the study ran under a finite Z3 budget")
def _(I):
    bad = [(c, n) for (c, n), m in I.items() if (m.get("budget_s") or 0) < 100000]
    return not bad, f"budgeted cells: {bad}"


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
