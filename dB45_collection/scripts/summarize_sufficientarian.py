"""Read back the sufficientarian CSVs and answer the report questions.

Deliberately reads only the emitted files -- it re-derives nothing from the
solver, so what it prints is exactly what a downstream consumer of the CSVs
would see.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths45 import ROUTES
from _helpers45 import COMBOS, baseline_for

MODES = ["unweighted", "weighted"]
CAPS = [3, 8, 18]


def parse(path):
    meta, zones, routing = {}, [], []
    section = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            k, _, v = line[2:].partition(",")
            meta[k] = v
        elif line.startswith("Time Steps"):
            meta["T"] = int(line.split(",")[1])
        elif line.startswith("Routing ("):
            section = "routing"
        elif line.startswith("Aircraft,"):
            continue
        elif line.startswith("Zone,"):
            section = "zones"
        elif line.startswith("Zone "):
            f = line.split(",")
            zones.append({"zone": int(f[0].split()[1]), "avg_added": float(f[1]),
                          "peak_added": float(f[3]), "avg_ac": float(f[5]),
                          "peak_ac": float(f[6])})
        elif section == "routing" and line and line[0].isdigit():
            routing.append(line)
    return meta, zones, routing


def main():
    rows, files = [], {}
    for combo in COMBOS:
        for mode in MODES:
            for cap in CAPS:
                p = ROUTES / combo / "sufficientarian" / mode / f"D{cap}.csv"
                if not p.exists():
                    rows.append((combo, mode, cap, "MISSING"))
                    continue
                meta, zones, routing = parse(p)
                files[(combo, mode, cap)] = (meta, zones, routing)
                rows.append((combo, mode, cap, meta, zones))

    print("=" * 118)
    print(f"{'combo':<13} {'mode':<11} {'D':>3} {'maxAvgAdd':>10} {'maxPkAdd':>9} "
          f"{'T':>2} {'demand%':>8} {'travel':>7} {'fullFleet':>10} {'variant':<14} {'Dbinds':>7}")
    print("=" * 118)
    for r in rows:
        if r[3] == "MISSING":
            print(f"{r[0]:<13} {r[1]:<11} {r[2]:>3}  *** MISSING ***")
            continue
        combo, mode, cap, meta, zones = r
        mxa = max(z["avg_added"] for z in zones)
        mxp = max(z["peak_added"] for z in zones)
        print(f"{combo:<13} {mode:<11} {cap:>3} {mxa:>10.2f} {mxp:>9.2f} "
              f"{meta['T']:>2} {meta['demandFulfilledPct']:>8} "
              f"{meta['avgTravelTimeWeighted']:>7} {meta['fullFleetFeasible']:>10} "
              f"{meta['variant']:<14} {meta['Dbinding']:>7}")

    # ---- where did the traffic go -------------------------------------------
    print("\n" + "=" * 118)
    print("TRAFFIC ABSORPTION -- avg weighted aircraft per station, "
          "grouped by that station's baseline")
    print("=" * 118)
    for combo in COMBOS:
        base = baseline_for(combo)
        loud = [i + 1 for i, b in enumerate(base) if b == 65]
        mid = [i + 1 for i, b in enumerate(base) if b == 55]
        quiet = [i + 1 for i, b in enumerate(base) if b == 45]
        print(f"\n{combo}   65dB={loud}  55dB={mid}  45dB={quiet}")
        for mode in MODES:
            for cap in CAPS:
                key = (combo, mode, cap)
                if key not in files:
                    continue
                _, zones, _ = files[key]
                by = {z["zone"]: z["avg_ac"] for z in zones}
                tot = sum(by.values()) or 1
                sl = sum(by[z] for z in loud)
                sm = sum(by[z] for z in mid)
                sq = sum(by[z] for z in quiet)
                top = sorted(zones, key=lambda z: -z["avg_ac"])[:4]
                topstr = " ".join(f"s{z['zone']}({base[z['zone']-1]}dB):{z['avg_ac']:.1f}"
                                  for z in top if z["avg_ac"] > 0)
                print(f"  {mode:<11} D{cap:<3} 65dB={sl:6.1f} ({100*sl/tot:5.1f}%) "
                      f"55dB={sm:6.1f} ({100*sm/tot:5.1f}%) "
                      f"45dB={sq:5.1f} ({100*sq/tot:5.1f}%)  | top: {topstr}")

    # ---- D=8 vs D=18 ---------------------------------------------------------
    print("\n" + "=" * 118)
    print("DOES D=8 DIFFER FROM D=18?  (identical routing block => cap ladder is inert here)")
    print("=" * 118)
    for combo in COMBOS:
        for mode in MODES:
            a, b = files.get((combo, mode, 8)), files.get((combo, mode, 18))
            if not (a and b):
                print(f"  {combo:<13} {mode:<11} incomplete")
                continue
            same_route = a[2] == b[2]
            same_zone = [(z["avg_added"], z["peak_added"]) for z in a[1]] == \
                        [(z["avg_added"], z["peak_added"]) for z in b[1]]
            print(f"  {combo:<13} {mode:<11} routing {'IDENTICAL' if same_route else 'DIFFERS':<9} "
                  f"zone table {'IDENTICAL' if same_zone else 'DIFFERS'}")

    # ---- weighted vs unweighted ---------------------------------------------
    print("\n" + "=" * 118)
    print("DOES POPULATION WEIGHTING CHANGE THE ROUTING?")
    print("=" * 118)
    for combo in COMBOS:
        for cap in CAPS:
            a, b = files.get((combo, "unweighted", cap)), files.get((combo, "weighted", cap))
            if not (a and b):
                print(f"  {combo:<13} D{cap:<3} incomplete")
                continue
            same_route = a[2] == b[2]
            same_zone = [(z["avg_added"], z["peak_added"]) for z in a[1]] == \
                        [(z["avg_added"], z["peak_added"]) for z in b[1]]
            print(f"  {combo:<13} D{cap:<3} routing {'IDENTICAL' if same_route else 'DIFFERS':<9} "
                  f"zone table {'IDENTICAL' if same_zone else 'DIFFERS'}")


if __name__ == "__main__":
    main()
