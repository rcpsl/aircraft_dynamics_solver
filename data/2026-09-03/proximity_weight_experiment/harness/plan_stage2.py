"""Stage 2: finalists from stage 1 across all 30 rankings, plus the second dial.

Two dials are in play and they are independent:

  the WEIGHT dial (scheme)  how much of the dB curve's implicit 0.88-0.94
      ambient rank weight is cancelled. Decides which shortest path the routing
      picks.
  the STRENGTH dial (w_prox)  how loudly the proximity term speaks against the
      soft-T penalty. At slack 0 the time penalty sits at its floor of 44 for
      every routing, so it acts as a hard "take a shortest path" constraint and
      proximity only breaks ties among those. Raising w_prox is what would let
      the ranking BUY A DETOUR instead of merely choosing between equal-length
      routes -- a different and arguably stronger sense of "the ranking matters".

usage: python plan_stage2.py <scheme>[:w_prox] [<scheme>[:w_prox] ...]
"""
import itertools, json, sys

F = ["income", "ambient", "distance", "population"]


def all_rankings():
    for p in itertools.permutations(F):
        yield list(p), True
    for p in itertools.permutations([f for f in F if f != "population"]):
        yield list(p) + ["population"], False


def main(specs):
    jobs = []
    for spec in specs:
        parts = spec.split("@")
        scheme = parts[0]
        wp = float(parts[1]) if len(parts) > 1 else 1.0
        for order, pop in all_rankings():
            j = {"scheme": scheme, "order": order, "pop": pop, "T_max": 5,
                 "timeout_ms": 1500000, "wall_kill": 1700}
            if wp != 1.0:
                j["w_prox"] = wp
            jobs.append(j)
    json.dump({"out": "stage2.jsonl", "par": 18, "jobs": jobs}, open("plan_stage2.json", "w"))
    print(f"{len(jobs)} jobs over {len(specs)} scheme/strength combinations")


if __name__ == "__main__":
    main(sys.argv[1:])
