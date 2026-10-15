"""Score saved routings on yardsticks that are common across schemes.

Each scheme minimizes its OWN normalized objective, so proximityCost values are
not comparable between schemes. These four are:

  peak      max added dB on any tile at any timestep -- the dashboard headline
  dose      added dB summed over all tiles and timesteps -- total noise poured
            into the map, the thing the dB term exists to reduce
  w0dose    that same dose weighted by the participant's OWN tile weights, so a
            scheme is credited for putting noise where THIS ranking said it was
            least objectionable. The closest thing to "did the group get what
            they asked for", and the only metric that can move when the ranking
            moves.
  quiet     aircraft-timesteps over 45 dB tiles (floor is 4: Community is a
            45 dB endpoint for four aircraft and an aircraft still counts on the
            timestep it lands)
"""
import json, os, sys
import schemes as sc

BASE = sc.BASELINE


def rescore(rec):
    paths = rec.get("paths")
    if not paths:
        return None
    T = len(paths[0])
    req = sc.mk.build()
    s0, e0, mult = req["startPositions"], req["endPositions"], req["aircraftMultipliers"]
    cnt = [[0] * T for _ in range(25)]
    for i, p in enumerate(paths):
        if s0[i] == e0[i]:
            continue
        t_fm = next((t for t in range(T) if p[t] != s0[i]), None)
        if t_fm is None:
            continue
        t_arr = next((t for t in range(T) if p[t] == e0[i]), T - 1)
        for t in range(t_fm, t_arr + 1):
            cnt[p[t] - 1][t] += mult[i]
    w0 = sc.weights_for(rec["order"], rec["pop"])
    peak = 0.0
    dose = 0.0
    w0dose = 0.0
    for m in range(25):
        for t in range(T):
            d = sc.dbinc(BASE[m], cnt[m][t])
            peak = max(peak, d)
            dose += d
            w0dose += d * w0[m]
    occ = [sum(cnt[m]) for m in range(25)]
    return {"peak": round(peak, 3), "dose": round(dose, 2), "w0dose": round(w0dose, 1),
            "quiet": sum(occ[m] for m in range(25) if BASE[m] == 45),
            "occ": occ}


def main(path):
    recs = [json.loads(l) for l in open(path)]
    sat = [r for r in recs if r["status"] == "sat"]
    print(f"{'scheme':12}{'ranking':40}{'peak':>7}{'dose':>9}{'w0dose':>10}{'quiet':>7}{'wall':>7}")
    for r in sorted(sat, key=lambda r: (r["scheme"], r["key"])):
        s = rescore(r)
        k = "-".join(r["order"]) + ("" if r["pop"] else "*")
        print(f"{r['scheme']:12}{k[:39]:40}{s['peak']:>7}{s['dose']:>9}{s['w0dose']:>10}"
              f"{s['quiet']:>7}{r['elapsed']:>7.0f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "stage1.jsonl")
