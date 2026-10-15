"""Read back the emitted prioritarian files and separate real lens effects from
tie-breaking artifacts.

The previous collection shipped four "distinct" lens outcomes per cell, of which
three were arbitrary picks from a tied-optimal set: once a lens's protected
stations can all be driven to zero added dB, every routing that achieves zero
scores identically and Z3 returns whichever it happened to find. The files
differ; the fairness content does not.

Two things are checked per (combo, mode):

  degeneracy  -- protectedNoise straight out of the preamble. 0.0 means the lens
                 imposed no cost, so its routing is one arbitrary member of the
                 tied set.
  identity    -- lenses grouped by identical ZONE TABLE (what a reader actually
                 sees) and, separately, by identical ROUTING (the raw solution).
                 Two lenses can share a zone table while differing in routing;
                 that still means the published outcome is the same.

Usage: python summarize_prioritarian.py            # all combos
       python summarize_prioritarian.py <combo>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths45 import ROUTES, SUMMARIES
from _helpers45 import COMBOS
from lens_definitions import LENSES

MODES = ["community", "people"]


def parse(path):
    """-> (meta dict, routing rows tuple, zone rows tuple)."""
    meta, routing, zones = {}, [], []
    section = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            k, _, v = line[2:].partition(",")
            meta[k] = v
        elif line.startswith("Routing"):
            section = "routing"
        elif line.startswith("Zone,"):
            section = "zones"
        elif line.startswith("Zone "):
            zones.append(line)
        elif section == "routing" and line and line[0].isdigit():
            routing.append(line)
        elif line.startswith("Time Steps"):
            meta["T"] = line.split(",")[1]
    return meta, tuple(routing), tuple(zones)


def groups(keyed):
    """{lens: hashable} -> list of lens-name lists sharing a value."""
    buckets = {}
    for lens, val in keyed.items():
        buckets.setdefault(val, []).append(lens)
    return list(buckets.values())


def main():
    combos = [sys.argv[1]] if len(sys.argv) > 1 else COMBOS
    rows = ["combo,mode,lens,protectedStations,protectedNoise,degenerate,"
            "maxAvgAddedDb,maxPeakAddedDb,T,demandFulfilledPct,"
            "avgTravelTimeWeighted,zoneTableGroup,routingGroup"]

    for combo in combos:
        for mode in MODES:
            d = ROUTES / combo / "prioritarian" / mode
            found = {l: d / f"{l}.csv" for l in LENSES if (d / f"{l}.csv").exists()}
            missing = [l for l in LENSES if l not in found]
            print(f"\n=== {combo} / {mode} ===")
            if missing:
                print(f"  MISSING: {', '.join(missing)}")
            if not found:
                continue

            parsed = {l: parse(p) for l, p in found.items()}
            zgroups = groups({l: v[2] for l, v in parsed.items()})
            rgroups = groups({l: v[1] for l, v in parsed.items()})
            zid = {l: i for i, g in enumerate(zgroups) for l in g}
            rid = {l: i for i, g in enumerate(rgroups) for l in g}

            print(f"  {'lens':<16} {'protNoise':>9} {'degen':>5} {'maxAvg':>7} "
                  f"{'maxPeak':>7} {'T':>2} {'demand%':>7} {'travel':>6} "
                  f"{'zoneGrp':>7} {'routeGrp':>8}")
            for lens in LENSES:
                if lens not in parsed:
                    continue
                m = parsed[lens][0]
                pn = float(m.get("protectedNoise", "nan"))
                print(f"  {lens:<16} {pn:>9} {('YES' if pn == 0 else 'no'):>5} "
                      f"{m['maxAvgAddedDb']:>7} {m['maxPeakAddedDb']:>7} "
                      f"{m['T']:>2} {m['demandFulfilledPct']:>7} "
                      f"{m['avgTravelTimeWeighted']:>6} {zid[lens]:>7} "
                      f"{rid[lens]:>8}")
                rows.append(",".join([
                    combo, mode, lens, f"\"{m['protectedStations']}\"", str(pn),
                    "YES" if pn == 0 else "no", m["maxAvgAddedDb"],
                    m["maxPeakAddedDb"], m["T"], m["demandFulfilledPct"],
                    m["avgTravelTimeWeighted"], str(zid[lens]), str(rid[lens])]))

            dup = [g for g in zgroups if len(g) > 1]
            if dup:
                for g in dup:
                    print(f"  IDENTICAL ZONE TABLE: {', '.join(g)}")
            print(f"  distinct zone tables: {len(zgroups)}/{len(parsed)}   "
                  f"distinct routings: {len(rgroups)}/{len(parsed)}")
            binding = [l for l in parsed
                       if float(parsed[l][0].get("protectedNoise", 0)) != 0]
            print(f"  lenses that actually bound (protectedNoise > 0): "
                  f"{', '.join(binding) if binding else 'NONE'}")

    SUMMARIES.mkdir(parents=True, exist_ok=True)
    out = SUMMARIES / "prioritarian_summary.csv"
    out.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
