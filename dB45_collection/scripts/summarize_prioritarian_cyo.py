"""Classify every CYO variant by what the lens actually DID.

Once CYO slots feed lens membership, `protectedNoise == 0` stops being a
reliable degeneracy test. It now covers two opposite situations:

  no-op      pn == 0 AND routing identical to the unconstrained diagonal.
             The protected set was already free; the lens changed nothing.
  succeeded  pn == 0 BUT routing differs. The solver REROUTED aircraft off the
             protected stations and drove the cost to zero. The lens worked
             completely -- the opposite of degenerate.

and a nonzero pn splits too:

  forced     pn > 0 with routing identical to the diagonal. The protected set
             contains something unavoidable; the cost is charged, not chosen,
             and the lens still changed no behaviour.
  traded     pn > 0 with a different routing. The lens moved aircraft and still
             could not reach zero.

So the real test is ROUTING vs the unconstrained reference, not pn alone. The
reference is taken from the frozen-lens tree (prioritarian/<combo>/<mode>/), any
file whose pn == 0 and which we already know reproduces the plain diagonal.

Usage: python summarize_prioritarian_cyo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths45 import ROUTES, SUMMARIES
from _helpers45 import COMBOS
from summarize_prioritarian import parse

MODES = ["community", "people"]


def reference_routing(combo, mode):
    """Unconstrained diagonal routing, from a frozen-lens file known to be a no-op."""
    d = ROUTES / combo / "prioritarian" / mode
    for name in ("few_jobs.csv", "transit_desert.csv", "people_of_color.csv"):
        p = d / name
        if p.exists():
            meta, routing, _ = parse(p)
            if float(meta.get("protectedNoise", -1)) == 0.0:
                return routing
    return None


def classify(pn, same_routing):
    if same_routing:
        return "no-op" if pn == 0 else "forced"
    return "succeeded" if pn == 0 else "traded"


def main():
    rows = ["combo,mode,variant,lens,gainedFromCyo,protectedStations,"
            "protectedNoise,routingVsUnconstrained,effect,maxAvgAddedDb,"
            "maxPeakAddedDb,T,demandFulfilledPct,avgTravelTimeWeighted"]
    tally = {}

    for combo in COMBOS:
        for mode in MODES:
            d = ROUTES / combo / "prioritarian_cyo" / mode
            files = sorted(d.glob("*.csv")) if d.exists() else []
            ref = reference_routing(combo, mode)
            print(f"\n=== {combo} / {mode} ===")
            if not files:
                print("  (no files)")
                continue
            print(f"  {'variant':<30} {'protNoise':>9} {'route':>8} "
                  f"{'effect':>10} {'maxAvg':>7} {'maxPeak':>7} {'T':>2}")
            for p in files:
                meta, routing, _ = parse(p)
                pn = float(meta.get("protectedNoise", "nan"))
                same = (routing == ref)
                eff = classify(pn, same)
                tally[eff] = tally.get(eff, 0) + 1
                print(f"  {p.stem:<30} {pn:>9} {('same' if same else 'DIFFER'):>8} "
                      f"{eff:>10} {meta['maxAvgAddedDb']:>7} "
                      f"{meta['maxPeakAddedDb']:>7} {meta['T']:>2}")
                rows.append(",".join([
                    combo, mode, p.stem, meta["lens"],
                    f"\"{meta.get('lensGainedFromCyo','')}\"",
                    f"\"{meta['protectedStations']}\"", str(pn),
                    "same" if same else "differs", eff,
                    meta["maxAvgAddedDb"], meta["maxPeakAddedDb"], meta["T"],
                    meta["demandFulfilledPct"], meta["avgTravelTimeWeighted"]]))

            nroutes = len({parse(p)[1] for p in files})
            print(f"  distinct routings: {nroutes}/{len(files)}")

    print("\n\n=== effect tally across all variants ===")
    for k in ("no-op", "forced", "traded", "succeeded"):
        if k in tally:
            print(f"  {k:<10} {tally[k]}")
    print("\n  'succeeded' and 'traded' are the only ones where the lens "
          "changed any aircraft's route.")

    SUMMARIES.mkdir(parents=True, exist_ok=True)
    out = SUMMARIES / "prioritarian_cyo_summary.csv"
    out.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
