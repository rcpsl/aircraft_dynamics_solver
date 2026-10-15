"""Is the restored lever meaningful, or just different?

Counting distinct routings says the ranking changes SOMETHING. It does not say
the change tracks what the group actually asked for. This groups the 30 rankings
by the routing they produce and prints what those rankings have in common, so a
scheme that merely scrambles can be told from one that responds.

Also reports, per scheme, how often the routing is the one that minimizes THAT
ranking's own weighted noise dose among all routings the scheme produces -- a
scheme whose routing is frequently beaten by another of its own outputs is not
serving the ranking well.
"""
import json, sys
from collections import defaultdict


def main(path, schemes):
    recs = [json.loads(l) for l in open(path) if json.loads(l)["w_prox"] == 1.0]
    for s in schemes:
        rs = [r for r in recs if r["scheme"] == s]
        if not rs:
            continue
        by = defaultdict(list)
        for r in rs:
            by[tuple(r["occ"])].append(r)
        print(f"\n=== {s}: {len(by)} routings over {len(rs)} rankings ===")
        for occ, group in sorted(by.items(), key=lambda kv: -len(kv[1])):
            g0 = group[0]
            first = defaultdict(int)
            for r in group:
                first[r["order"][0] if r["pop"] else
                      [f for f in r["order"] if f != "population"][0]] += 1
            top = ", ".join(f"{k} x{v}" for k, v in sorted(first.items(), key=lambda kv: -kv[1]))
            print(f"  {len(group):2} rankings | tier {g0['tier']['45']}/{g0['tier']['55']}/"
                  f"{g0['tier']['65']} peak {g0['peak']:6} | ranked FIRST: {top}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "surr.jsonl",
         sys.argv[2:] or ["base", "ref:55", "alpha:0.6", "alpha:1.0", "count"])
