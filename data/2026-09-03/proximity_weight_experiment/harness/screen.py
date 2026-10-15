"""Free pre-screen: can a scheme's price landscape respond to the ranking at all?

Under noise pricing a tile's cost at one aircraft is w[m]*g[m]. Today the g term
sorts every 45 dB tile above every 65 dB tile under EVERY ranking, so the only
thing the ranking can still do is reorder tiles inside a baseline tier -- which
never changes which tier the traffic avoids. Breaking that tier monopoly is a
NECESSARY condition for the routing to move (not a sufficient one: the OD pairs
and T=5 also constrain what is reachable), so it is worth checking for free
before committing Z3 time.

Reports per scheme, across all 30 rankings:
  orderings   distinct price orderings of the 25 tiles
  topmono     how often the 8 most expensive tiles are exactly the eight 45 dB
              tiles (30/30 == the ranking cannot move burden between tiers)
  spread45/65 median price ratio between the tiers -- how big a gradient the
              ranking would have to overcome
  rankswing   median (max/min) of a tile's own price across the 30 rankings:
              how much leverage the ranking actually has on one tile
"""
import itertools, statistics as st
import schemes as sc

F = ["income", "ambient", "distance", "population"]
CFGS = ([(list(p), True) for p in itertools.permutations(F)] +
        [(list(p), False) for p in itertools.permutations([f for f in F if f != "population"])])
BASE = sc.BASELINE
QUIET = [m for m in range(25) if BASE[m] == 45]


def price_at_1(scheme, order, pop):
    w, extra = sc.build(scheme, order, pop)
    ref = extra.get("proximityNoiseRef")
    if extra.get("proximityMode") == "count":
        g = [1.0] * 25
    elif ref is not None:
        g = [sc.dbinc(ref, 1)] * 25
    else:
        g = sc.G1
    return [w[m] * g[m] for m in range(25)]


def report(schemes):
    print(f"{'scheme':14}{'orderings':>10}{'topmono':>9}{'45/65 ratio':>13}{'rankswing':>11}")
    for s in schemes:
        ps = [price_at_1(s, o, p) for o, p in CFGS]
        orders = {tuple(sorted(range(25), key=lambda m: pr[m])) for pr in ps}
        mono = sum(1 for pr in ps
                   if set(sorted(range(25), key=lambda m: -pr[m])[:8]) == set(QUIET))
        ratio = st.median([st.median([pr[m] for m in range(25) if BASE[m] == 45]) /
                           st.median([pr[m] for m in range(25) if BASE[m] == 65]) for pr in ps])
        swing = st.median([max(pr[m] for pr in ps) / min(pr[m] for pr in ps) for m in range(25)])
        print(f"{s:14}{len(orders):>10}{mono:>6}/30{ratio:>13.1f}{swing:>11.1f}")


if __name__ == "__main__":
    report(["count", "base", "ref:45", "ref:55", "ref:65",
            "alpha:0.25", "alpha:0.5", "alpha:0.75", "alpha:1.0", "alpha:1.25",
            "alphak:3", "gamma:0.25", "gamma:0.5"])
