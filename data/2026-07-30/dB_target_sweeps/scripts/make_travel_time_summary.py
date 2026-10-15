"""Supplementary dataset: average aircraft travel time per proportional scenario.

Travel time for one aircraft = the timestep index at which it first reaches its
End station (0-indexed; all aircraft start parked at their Start at T0, so this is
also the number of move-steps to complete the journey). Pure post-processing of
the routing table already inside each proportional CSV — no solver, no re-solve.

Writes full_routes/proportional/travel_time_summary.csv, one row per data file:
  combo, mode, cyoScenario, N, T, avgTravel, avgTravelWeighted, minTravel, maxTravel
- avgTravel          : mean over physical aircraft
- avgTravelWeighted  : mean weighted by aircraftMultiplier (demand-weighted) —
                       differs from avgTravel only at N=14 (non-uniform multipliers)
"""
from pathlib import Path

from _paths import ROUTES as SRC, SUMMARIES
COMBOS = ["s2-65_s6-55", "s2-65_s6-45", "s2-55_s6-55", "s2-55_s6-45"]
FILES = [
    ("high_benefit", "high_benefit.csv"),
    ("all_benefited", "all_benefited.csv"),
    ("all_benefited", "all_benefited__c11-tech.csv"),
]


def travel_times(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    meta = {}
    for l in lines:
        if l.startswith("#"):
            k, _, v = l.lstrip("# ").partition(",")
            meta[k.strip()] = v.strip()
    T = int(next(l for l in lines if l.startswith("Time Steps")).split(",")[1])
    i = lines.index("Routing (station per aircraft per timestep):")
    hdr = lines[i + 1].split(",")
    ntcol = sum(1 for c in hdr if c.startswith("T"))
    rows, j = [], i + 2
    while j < len(lines) and lines[j].strip():
        rows.append(lines[j].split(","))
        j += 1
    out = []
    for r in rows:
        mult = int(r[1])
        end = r[3]
        path_cells = r[4:4 + ntcol]
        arrive = next((t for t, s in enumerate(path_cells) if s == end), ntcol - 1)
        out.append((arrive, mult))
    return meta, T, out


def main():
    header = ["combo", "mode", "cyoScenario", "N", "T",
              "avgTravel", "avgTravelWeighted", "minTravel", "maxTravel"]
    lines = [
        "# supplementary,proportional average aircraft travel time",
        "# definition,travel time = timestep index of first arrival at End (0-indexed = move-steps to finish)",
        "# source,derived from the routing table in each full_routes/<combo>/proportional/*.csv (no re-solve)",
        ",".join(header),
    ]
    for combo in COMBOS:
        for mode, fname in FILES:
            p = SRC / combo / "proportional" / fname
            if not p.exists():
                continue
            meta, T, tt = travel_times(p)
            n = len(tt)
            avg = sum(a for a, _ in tt) / n
            wavg = sum(a * m for a, m in tt) / sum(m for _, m in tt)
            cyo = meta.get("cyoScenario", "default")
            lines.append(",".join([
                combo, mode, cyo, str(n), str(T),
                f"{avg:.3f}", f"{wavg:.3f}",
                str(min(a for a, _ in tt)), str(max(a for a, _ in tt)),
            ]))
    out = SUMMARIES / "proportional_travel_time_summary.csv"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out} ({len(lines) - 4} data rows)")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
