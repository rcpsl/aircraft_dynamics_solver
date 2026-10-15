"""Paired per-ranking comparison. Medians across rankings hide the distribution:
a scheme that IGNORES the ranking posts a good median by overriding everyone.
The question that matters is, for the SAME ranking, how does scheme X compare to
count (today's tractable fallback) and to base (today's dB pricing)?
"""
import json, sys
from collections import defaultdict


def main(path, ref_scheme):
    rows = [json.loads(l) for l in open(path) if json.loads(l)["w_prox"] == 1.0]
    by = defaultdict(dict)
    for r in rows:
        k = "|".join(r["order"]) if r["pop"] else "|".join(
            f for f in r["order"] if f != "population") + "|NOPOP"
        by[k][r["scheme"]] = r
    for base_scheme in ("count", "base"):
        wins = ties = losses = 0
        pw = pt = pl = 0
        print(f"\n=== {ref_scheme} vs {base_scheme}, per ranking (30) ===")
        for k, d in by.items():
            if ref_scheme not in d or base_scheme not in d:
                continue
            a, b = d[ref_scheme], d[base_scheme]
            if a["dose"] < b["dose"] - 1e-9:
                wins += 1
            elif a["dose"] > b["dose"] + 1e-9:
                losses += 1
            else:
                ties += 1
            if a["peak"] < b["peak"] - 1e-9:
                pw += 1
            elif a["peak"] > b["peak"] + 1e-9:
                pl += 1
            else:
                pt += 1
        print(f"  total dose : {ref_scheme} better in {wins}, tied {ties}, worse in {losses}")
        print(f"  peak added : {ref_scheme} better in {pw}, tied {pt}, worse in {pl}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "surr.jsonl",
         sys.argv[2] if len(sys.argv) > 2 else "ref:55")
