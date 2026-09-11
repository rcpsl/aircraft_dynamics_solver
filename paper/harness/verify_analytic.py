"""Check every ANALYTIC claim the paper makes against the production solver's own code.

Nothing here runs Z3. These are the claims that follow from the noise model and the
encoding alone, so they can be settled exactly -- and they are the claims most likely
to have been copied forward from an older version of the system.

usage: python verify_analytic.py            (writes ../results/analytic_checks.md)
"""
import importlib.util as iu
import io
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import payload as P

SOLVER = r"d:/Documents/EECS_199_Shoukry/solver_server_dB.py"
spec = iu.spec_from_file_location("SOLVER_DB", SOLVER)
S = iu.module_from_spec(spec)
spec.loader.exec_module(S)

OUT = []
FAILS = []


def check(label, got, want, tol=None, note=""):
    if tol is None:
        ok = got == want
    else:
        ok = abs(got - want) <= tol
    OUT.append((label, got, want, ok, note))
    if not ok:
        FAILS.append(label)
    return ok


def section(t):
    OUT.append(("##", t, "", True, ""))


# ---------------------------------------------------------------- noise model
section("Noise model: delta_m(n) = 10 log10(1 + n 10^((alpha-b)/10))")
ALPHA = 45.0
for b, n, want in [(45, 1, 3.0103), (45, 2, 4.7712), (45, 3, 6.0206), (45, 4, 6.9897),
                   (55, 1, 0.4139), (55, 11, 3.2222), (65, 1, 0.0432), (65, 4, 0.1703)]:
    got = S.dB_increase(b, n, ALPHA)
    check(f"delta({b} dBA, n={n})", round(got, 4), want, tol=5e-4)

# The ~70x implicit price gradient quoted in Sec. 3.3 property 3.
r = S.dB_increase(45, 1, ALPHA) / S.dB_increase(65, 1, ALPHA)
check("gradient delta(45,1)/delta(65,1)", round(r, 1), 69.7, tol=0.15,
      note="quoted in the paper as 'a ratio of about 70'")

# Concavity of the TRUE curve, and its loss under centi-dB rounding.
true_diffs = [S.dB_increase(65, n, ALPHA) - S.dB_increase(65, n - 1, ALPHA) for n in range(1, 6)]
check("true marginals at 65 dBA are strictly decreasing",
      all(true_diffs[i] > true_diffs[i + 1] for i in range(len(true_diffs) - 1)), True,
      note=f"{[round(d,3) for d in true_diffs]}")
row = S.build_scaled_table(1, 5, [65.0], ALPHA)[0]
check("rounded row at 65 dBA", row, [0, 4, 9, 13, 17, 21],
      note="the paper quotes this row verbatim")
rd = [row[n] - row[n - 1] for n in range(1, 6)]
check("rounding destroys concavity (marginals not monotone)",
      any(rd[i] < rd[i + 1] for i in range(len(rd) - 1)), True, note=str(rd))

# ---------------------------------------------------------------- capacity table
section("Capacity kappa_m under a cap D (Table: capacity)")
# NB: _compute_d_counts caps at the fleet size passed in, so a large n_max is used
# here to expose the TRUE capacity rather than a fleet-size artefact.
NMAX = 20000
cap_table = {}
for D in (3, 4, 5, 7, 10, 15, 20):
    row = []
    for b in (45.0, 55.0, 65.0):
        st = S.build_scaled_table(1, NMAX, [b], ALPHA)
        k = S._compute_d_counts(1, NMAX, round(D * S.SCALE), st)[0]
        row.append(k)
    cap_table[D] = row
# Exact real-valued capacity: kappa* = floor( (10^(D/10) - 1) / 10^((alpha-b)/10) ).
# The table in the workshop notes reads 16 for several of these cells only because it
# was capped at the fleet size; these are the true capacities.
def kappa_exact(D, b):
    return int(math.floor((10 ** (D / 10.0) - 1) / 10 ** ((ALPHA - b) / 10.0)))

for D in (3, 4, 5, 7, 10, 15):
    want = [kappa_exact(D, b) for b in (45.0, 55.0, 65.0)]
    got = cap_table[D]
    # The solver compares ROUNDED centi-dB against a rounded D, so at large counts it
    # can admit one or two aircraft beyond the exact capacity: delta_65(901) = 10.0043
    # dB rounds to exactly 1000 centi-dB and passes D = 10. The discrepancy is an
    # artefact of the integerisation, is always in the permissive direction, and is
    # unreachable at any fleet size used in this paper (N <= 32).
    slack = [g - w for g, w in zip(got, want)]
    check(f"kappa at D={D} for (45,55,65) dBA (exact vs solver)",
          all(0 <= d <= 3 for d in slack), True,
          note=f"exact={want}, solver={got}, rounding slack={slack}")
check("rounding slack is zero wherever the count is reachable at N<=32",
      [min(cap_table[D][j], 32) for D in (3, 4, 5, 7, 10, 15) for j in range(3)]
      == [min(kappa_exact(D, b), 32) for D in (3, 4, 5, 7, 10, 15)
          for b in (45.0, 55.0, 65.0)], True,
      note="so no result in this paper is affected by it")
check("a 45 dBA tile holds ZERO aircraft at D=3", cap_table[3][0], 0,
      note="the unsat cliff in Sec. 4")
check("a 45 dBA tile holds ONE aircraft at D=4", cap_table[4][0], 1)

# ---------------------------------------------------------------- normalisation
section("Proximity normalisation: naive bound vs exact knapsack")
req = P.build_request("proportional")
M = req["M"]
mult = req["aircraftMultipliers"]
budget = sum(mult)
T = req["T_max"]
st = S.build_scaled_table(M, budget, req["baseline"], req["aircraftDB"])
Dc = S._compute_d_counts(M, budget, round(req["D"] * S.SCALE), st)
int_pw = [round(w * 100) for w in req["proximityWeights"]]
exact = S._max_weighted_price(st, int_pw, Dc, budget, M, T)
naive = M * T * max(st[m][budget] for m in range(M)) * max(int_pw)
check("exact knapsack bound < naive bound", exact < naive, True,
      note=f"exact={exact}, naive={naive}, ratio={naive/exact:.1f}x")
OUT.append(("naive/exact overstatement factor", round(naive / exact, 1), "--", True,
            "paper says 'a factor of M on our map'; M=25"))

# ---------------------------------------------------------------- U encoding cost
section("Disparity encoding: constraint COUNTS only (see pairwise_bench.py for timings)")
# Per timestep, the pairwise form needs one implication per ORDERED pair of tiles per
# reachable count of the first tile; the max/min form needs 2M+1.
#
# These are counts, NOT a speedup. Reporting the ratio as though it were one is the
# mistake this file used to make: pairwise_bench.py builds and times both encodings and
# finds the pairwise form SOLVES 6-9x faster, with max/min's advantage confined to
# construction and gone by N=16. Constraint count proxies encoding cost, not search cost.
kappa_sum = sum(Dc)
pairwise = M * (M - 1) * (max(Dc) + 1)
maxmin = 2 * M + 1
OUT.append(("pairwise constraints / timestep", pairwise, "--", True, f"M={M}, max kappa={max(Dc)}"))
OUT.append(("max/min constraints / timestep", maxmin, "--", True, ""))
check("max/min emits at least 100x FEWER constraints per timestep",
      pairwise / maxmin > 100, True,
      note=f"{pairwise/maxmin:.0f}x fewer assertions -- NOT a solve-time speedup; "
           f"measured, the pairwise form solves faster (see results/pairwise.jsonl)")

# ---------------------------------------------------------------- collapse theorem
section("Equal / Sufficientarian: the payloads the dashboard actually sends")
for f, n in [(1.0, 16), (1.75, 30), (2.0, 32)]:
    eq = P.build_request("equal", limit=10, demand_factor=f)
    su = P.build_request("sufficientarian", limit=10, demand_factor=f)
    OUT.append((f"demand {f} (N={eq['N']}): Equal D/U", f"{eq['D']}/{eq['U']}",
                f"Suff D/U {su['D']}/{su['U']}", True,
                "identical constraint sets" if (eq["D"], eq["U"]) == (10.0, 10.0)
                and (su["D"], su["U"]) == (10.0, 30.0) else "PAYLOADS DIVERGE"))
    check(f"N={eq['N']}: fleet vs stations pigeonhole holds", eq["N"] < 25, f < 1.75)

# ---------------------------------------------------------------- report
lines = ["# Analytic checks against the production solver", "",
         "Generated by `paper/harness/verify_analytic.py`. No Z3 involved: every row",
         "below follows from the noise model and the encoding alone.", ""]
for label, got, want, ok, note in OUT:
    if label == "##":
        lines += ["", f"## {got}", "", "| claim | value | expected | ok |", "|---|---|---|---|"]
        continue
    mark = "yes" if ok else "**NO**"
    lines.append(f"| {label} | `{got}` | `{want}` | {mark} |" + (f" {note}" if note else ""))
lines += ["", f"**{len(FAILS)} failure(s)**" + (": " + ", ".join(FAILS) if FAILS else ".")]
path = os.path.join(HERE, "..", "results", "analytic_checks.md")
with io.open(path, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
print("\n".join(lines))
print("\nwrote", os.path.normpath(path))
sys.exit(1 if FAILS else 0)
