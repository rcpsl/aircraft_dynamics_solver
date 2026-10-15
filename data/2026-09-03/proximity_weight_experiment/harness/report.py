"""Summarize a results jsonl: does the ranking move the routing, and at what cost?

Primary metric (the one asked for): distinct occupancy vectors across the
rankings in the file. Today's noise pricing gives 1; count pricing gives 5 over
all 30 rankings and 5 over the 9-ranking stage-1 subset.
"""
import json, os, statistics as st, sys
from collections import defaultdict


def load(path):
    return [json.loads(l) for l in open(path)] if os.path.exists(path) else []


def summarize(recs, label=""):
    by = defaultdict(list)
    for r in recs:
        by[r["scheme"]].append(r)
    print(f"\n=== {label} ===")
    print(f"{'scheme':12}{'sat':>6}{'slow/fail':>10}{'routings':>10}{'tiers':>7}"
          f"{'peaks':>22}{'wall med':>10}{'wall max':>10}")
    out = {}
    for s, rs in sorted(by.items()):
        sat = [r for r in rs if r["status"] == "sat"]
        bad = [r for r in rs if r["status"] != "sat"]
        occs = {tuple(r["occ"]) for r in sat}
        tiers = {tuple(r["tier"][b] for b in ("45", "55", "65")) for r in sat}
        peaks = sorted({r["peak"] for r in sat})
        walls = [r["elapsed"] for r in sat]
        print(f"{s:12}{len(sat):>6}{len(bad):>10}{len(occs):>10}{len(tiers):>7}"
              f"{str(peaks)[:21]:>22}{(st.median(walls) if walls else 0):>10.0f}"
              f"{(max(walls) if walls else 0):>10.0f}")
        out[s] = {"sat": len(sat), "bad": len(bad), "routings": len(occs),
                  "tiers": sorted(tiers), "peaks": peaks,
                  "wall_med": st.median(walls) if walls else None,
                  "wall_max": max(walls) if walls else None}
        for r in bad:
            print(f"             ! {'-'.join(r['order'])[:44]:46}{r['status']} {r['elapsed']:.0f}s")
    return out


def tier_detail(recs):
    print(f"\n{'scheme':12}{'ranking':46}{'tier(45/55/65)':>18}{'peak':>8}{'wall':>8}")
    for r in sorted(recs, key=lambda r: (r["scheme"], r["key"])):
        if r["status"] != "sat":
            continue
        t = "/".join(str(r["tier"][b]) for b in ("45", "55", "65"))
        k = "-".join(r["order"]) + ("" if r["pop"] else " NOPOP")
        print(f"{r['scheme']:12}{k[:45]:46}{t:>18}{r['peak']:>8}{r['elapsed']:>8.0f}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "stage1.jsonl"
    recs = load(path)
    if not recs:
        sys.exit(f"{path}: nothing yet")
    summarize(recs, path)
    if "-v" in sys.argv:
        tier_detail(recs)
