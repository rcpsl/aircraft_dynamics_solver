"""Post-hoc analysis of the proportional-benefit datasets: does burden actually
follow benefit? Reads the 8 generated CSVs and prints the numbers the report needs."""
import sys
from pathlib import Path

COMBOS = ["s2-65_s6-55", "s2-65_s6-45", "s2-55_s6-55", "s2-55_s6-45"]
MODES = ["high_benefit", "all_benefited"]


def parse(path):
    meta, zones = {}, []
    section = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            k, _, v = line.lstrip("# ").partition(",")
            meta[k.strip()] = v.strip()
        elif line.startswith("Zone,"):
            section = "zones"
        elif section == "zones" and line.startswith("Zone "):
            p = line.split(",")
            zones.append({
                "zone": int(p[0].split()[1]), "avg_added": float(p[1]),
                "peak_added": float(p[3]), "avg_ac": float(p[5]),
                "benefit": int(p[7]), "income": p[9],
            })
    return meta, zones


def main():
    for combo in COMBOS:
        print(f"\n===== {combo} =====")
        for mode in MODES:
            path = ROUTES / combo / "proportional" / f"{mode}.csv"
            if not path.exists():
                print(f"  {mode}: MISSING")
                continue
            meta, zones = parse(path)
            prop = meta.get("proportionalStations", "?")
            n = meta.get("N", "?")
            benefited = [z for z in zones if z["benefit"] > 0]
            other = [z for z in zones if z["benefit"] == 0]
            avg_ben = sum(z["avg_added"] for z in benefited) / len(benefited)
            avg_oth = sum(z["avg_added"] for z in other) / len(other)
            loud = sorted(zones, key=lambda z: -z["avg_added"])[:4]
            loud_s = ", ".join(f"z{z['zone']}({z['avg_added']:.1f},b{z['benefit']})" for z in loud)
            print(f"  {mode:<13} N={n} propStns={prop} propNoise={meta.get('proportionalNoise')}")
            print(f"     mean avg_added: benefited={avg_ben:.2f}  non-benefited={avg_oth:.2f}")
            print(f"     loudest tiles (avg,benefit): {loud_s}")


if __name__ == "__main__":
    main()
