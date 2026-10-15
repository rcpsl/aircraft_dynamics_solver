"""Aggregate the surrogate sweep: does the ranking move the routing, and at what cost?

Primary column is `routings` -- distinct occupancy vectors across the 30
rankings. Reference points from Z3: today's noise pricing gives 1, count pricing
gives 5.

Ties are canonicalized (solve() keeps the lexicographically smallest occupancy
vector among equal-cost optima), so a routing counted here is a genuinely
different optimum and not the search landing somewhere else on a plateau.
"""
import json, statistics as st, sys
from collections import defaultdict


def load(path):
    return [json.loads(l) for l in open(path)]


def table(recs, wp):
    rows = [r for r in recs if r["w_prox"] == wp]
    by = defaultdict(list)
    for r in rows:
        by[r["scheme"]].append(r)
    order = sorted(by, key=lambda s: (s.split(":")[0], float(s.split(":")[1]) if ":" in s else 0))
    print(f"\n=== weightProximity = {wp} ===")
    print(f"{'scheme':12}{'n':>4}{'routings':>10}{'tiers':>7}{'peak dB':>20}"
          f"{'quiet med':>11}{'dose med':>10}{'w0dose med':>12}")
    for s in order:
        rs = by[s]
        occs = {tuple(r["occ"]) for r in rs}
        tiers = {tuple(r["tier"][b] for b in ("45", "55", "65")) for r in rs}
        peaks = sorted({r["peak"] for r in rs})
        pk = ",".join(f"{p:g}" for p in peaks)
        print(f"{s:12}{len(rs):>4}{len(occs):>10}{len(tiers):>7}{pk[:19]:>20}"
              f"{st.median(r['quiet'] for r in rs):>11.0f}"
              f"{st.median(r['dose'] for r in rs):>10.1f}"
              f"{st.median(r['w0dose'] for r in rs):>12.0f}")


def alpha_curve(recs, wp=1.0):
    """The trade-off, as one dial: gradient cancelled (alpha) vs what it costs."""
    rows = [r for r in recs if r["w_prox"] == wp and r["scheme"].startswith("alpha:")]
    by = defaultdict(list)
    for r in rows:
        by[float(r["scheme"].split(":")[1])].append(r)
    print(f"\n=== alpha curve at weightProximity={wp} "
          f"(alpha=0 is today's pricing, alpha=1 cancels the gradient exactly) ===")
    print(f"{'alpha':>7}{'routings':>10}{'peak med':>10}{'peak max':>10}"
          f"{'quiet med':>11}{'dose med':>10}{'w0dose med':>12}")
    for a in sorted(by):
        rs = by[a]
        print(f"{a:>7.1f}{len({tuple(r['occ']) for r in rs}):>10}"
              f"{st.median(r['peak'] for r in rs):>10.3f}{max(r['peak'] for r in rs):>10.3f}"
              f"{st.median(r['quiet'] for r in rs):>11.0f}"
              f"{st.median(r['dose'] for r in rs):>10.1f}"
              f"{st.median(r['w0dose'] for r in rs):>12.0f}")


if __name__ == "__main__":
    recs = load(sys.argv[1] if len(sys.argv) > 1 else "surr.jsonl")
    print(f"{len(recs)} rows")
    for wp in sorted({r["w_prox"] for r in recs}):
        table(recs, wp)
    for wp in sorted({r["w_prox"] for r in recs}):
        alpha_curve(recs, wp)
