"""Proportional benefit map for the 45 dB collection.

The benefit rule itself is unchanged from the 55 dB collection's
proportional_benefit.py -- it is a deterministic function of vertiport
locations, king-move adjacency, and per-station income, none of which routing
affects. What changes is the income source: this module takes income from
lens_definitions.build_station_income(), which parses the workbook row-major
with NO 6<->8 swap.

Consequence of removing the swap (see spec 5 section 4.2): station 6 is Dove
Springs, income Low, not Medium. Station 6 is king-adjacent to vertiport 1, so
under the swap it scored benefit 1 and joined `all_benefited`; correctly it
scores 0 and drops out. The low-income community under the flight path is no
longer treated as a beneficiary of the vertiport it sits next to.

Rule:
    vertiport                -> 3 (High)
    adjacent & income High   -> 2 (Medium)
    adjacent & income Medium -> 1 (Low)
    adjacent & income Low    -> 0 (None)
    overlap                  -> max()
    everything else          -> 0

Usage: python benefit45.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lens_definitions import build_station_income

_ADD_BY_INCOME = {"High": 2, "Medium": 1, "Low": 0}
VERTIPORTS = [1, 16]

# ------------------------------------------------- corridor analysis (utility)
#
# NOT part of the benefit rule -- the rule is adjacency+income, unmodified.
# Retained because it computes the fact behind a measured finding:
#
#   Stations 2 and 5 are vertiport-adjacent, so the rule grants them benefit,
#   but they sit off the route the traffic takes and received EXACTLY 0.000
#   added dB in every scheme tried (data/probes/proportional_tiers.csv).
#   Restricting benefit to the corridor was tested and did not deliver a
#   medium > low ordering either (data/probes/corridor_tiers.csv), because
#   corridor stations 6 and 11 are SERIAL waypoints on the one shortest path --
#   every aircraft traverses both exactly once, so their traffic counts are
#   equal by construction and no weighting can separate them. Where their
#   baselines differ, added dB diverges purely from ambient level, not traffic.
#
# Conclusion recorded: in a two-vertiport line network, benefit tiers cannot be
# reflected in noise burden. The toggle was removed; the rule stands as-is.


def _bfs_dist(src, adjacency, M):
    """Hop distance from src to every station, over the adjacency matrix
    minus self-loops. Derived from the matrix rather than assuming grid
    geometry, so it stays correct if the adjacency ever changes."""
    dist = {src: 0}
    frontier = [src]
    while frontier:
        nxt = []
        for u in frontier:
            for v in range(1, M + 1):
                if v != u and adjacency[u - 1][v - 1] == 1 and v not in dist:
                    dist[v] = dist[u] + 1
                    nxt.append(v)
        frontier = nxt
    return dist


def corridor_stations(adjacency, M, vertiports=VERTIPORTS, max_moves=None):
    """Stations lying on SOME route between the vertiports within `max_moves`.

    A station s qualifies when dist(v1, s) + dist(s, v2) <= max_moves for some
    vertiport pair -- i.e. a path through s exists inside the budget.

    `max_moves=None` (the default) uses the SHORTEST path length between the
    vertiports, giving the strict corridor. That is the right default because it
    matches where traffic demonstrably goes: measured routings put every
    non-vertiport aircraft on 1-6-11-16 and left the wider 4-move corridor
    stations at exactly 0.000 added dB. A larger budget re-admits stations that
    are reachable in principle but never actually used, which is the very
    mismatch this rule exists to remove.
    """
    dists = {v: _bfs_dist(v, adjacency, M) for v in vertiports}
    if max_moves is None:
        max_moves = min(dists[v1][v2]
                        for i, v1 in enumerate(vertiports)
                        for v2 in vertiports[i + 1:])
    out = set()
    for i, v1 in enumerate(vertiports):
        for v2 in vertiports[i + 1:]:
            d1, d2 = dists[v1], dists[v2]
            for s in range(1, M + 1):
                if s in d1 and s in d2 and d1[s] + d2[s] <= max_moves:
                    out.add(s)
    return sorted(out)


def king_neighbors(v, adjacency, M):
    """Grid-adjacent (next + diagonal) stations of vertiport v, excluding v.
    = the adjacency row minus its self-loop."""
    return [m for m in range(1, M + 1) if m != v and adjacency[v - 1][m - 1] == 1]


def compute_benefit(vertiports, income, adjacency, M):
    """{station: benefit 0..3}, by vertiport-adjacency and income."""
    benefit = {m: 0 for m in range(1, M + 1)}
    for v in vertiports:
        benefit[v] = max(benefit[v], 3)
    for v in vertiports:
        for m in king_neighbors(v, adjacency, M):
            benefit[m] = max(benefit[m], _ADD_BY_INCOME.get(income[m], 0))
    return benefit


def compute_demand_served(vertiports, start, end, mult):
    return {v: sum(mult[i] for i in range(len(mult))
                   if start[i] == v or end[i] == v) for v in vertiports}


def benefit_sets(benefit):
    high = sorted(m for m, b in benefit.items() if b == 3)
    allb = sorted(m for m, b in benefit.items() if b > 0)
    return high, allb


def tier_label(b):
    return {3: "Vertiport", 2: "Medium", 1: "Low", 0: "None"}[b]


def sets_for(cyo_choices, adjacency, M):
    income = build_station_income(cyo_choices)
    benefit = compute_benefit(VERTIPORTS, income, adjacency, M)
    high, allb = benefit_sets(benefit)
    return income, benefit, high, allb


def tiered_list(benefit):
    """proportionalStations with multiplicity == benefit tier.

    The solver sums dB over this list without de-duplicating, so listing a
    station k times gives it coefficient k, and `max_proportional_dB` scales
    with len(), keeping the objective normalised. This is how per-station
    weighting is expressed WITHOUT modifying the solver.
    """
    out = []
    for st in sorted(benefit, key=lambda s: (-benefit[s], s)):
        out.extend([st] * benefit[st])
    return out


if __name__ == "__main__":
    from _helpers45 import ADJ, M, FULL_START, FULL_END, FULL_MULT

    for label, choices in (("default", {}), ("c11-tech", {11: 1})):
        income, benefit, high, allb = sets_for(choices, ADJ, M)
        dem = compute_demand_served(VERTIPORTS, FULL_START, FULL_END, FULL_MULT)
        print(f"=== CYO scenario: {label}  {choices or '{}'} ===")
        print(f"{'St':>3}  {'Benefit':<11} {'Income':<7} {'DemandServed'}")
        for m in range(1, M + 1):
            print(f"{m:>3}  {benefit[m]}={tier_label(benefit[m]):<9} "
                  f"{income[m]:<7} {dem.get(m, 0)}")
        print(f"  high_benefit  = {high}")
        print(f"  all_benefited = {allb}\n")

    # The specific regression the SWAP removal fixes.
    income, benefit, _, allb = sets_for({}, ADJ, M)
    print(f"station 6: income={income[6]}, benefit={benefit[6]}, "
          f"in all_benefited={6 in allb}  "
          f"(under the old SWAP bug it was Medium/1/True)")
