"""Proportional *benefit* allocation for the UAM fairness model.

Unlike the four noise domains (which route-optimize a burden map), the benefit
map is a deterministic function of three static inputs, none of which routing
changes:

  1. vertiport locations       -> High benefit (3)
  2. grid-adjacent tiles        -> Medium(2)/Low(1)/None(0), by the tile's income
  3. everything else            -> 0

"Adjacent (next + diagonal)" is the 4x4 grid king-move neighborhood, which is
exactly the solver's `adjacency` matrix minus its self-loops (verified: the
config adjacency IS the king-move grid). Income comes from the workbook via
extract_station_income (NOT from the config, which has no income).

Rule (as specified):
  vertiport                         -> 3
  adjacent & income High            -> 2
  adjacent & income Medium          -> 1
  adjacent & income Low             -> 0
  overlap (adjacent to 2 vertiports, or vertiport+adjacent) -> max()

This module only computes the benefit overlay. The burden side (routing noise
onto benefited stations) is done by the existing Z3 solver via its
`optimizeProportional` / `proportionalStations` objective — see run_proportional.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # scripts/
from extract_station_income import build_station_income

_ADD_BY_INCOME = {"High": 2, "Medium": 1, "Low": 0}


def king_neighbors(v, adjacency, M):
    """Grid-adjacent (next + diagonal) stations of vertiport v (1-indexed),
    excluding v itself. = adjacency row minus the self-loop."""
    return [m for m in range(1, M + 1)
            if m != v and adjacency[v - 1][m - 1] == 1]


def compute_benefit(vertiports, income, adjacency, M):
    """Return {station(1..M) -> benefit 0..3}. `income` maps station -> High/Medium/Low."""
    benefit = {m: 0 for m in range(1, M + 1)}
    for v in vertiports:
        benefit[v] = max(benefit[v], 3)                       # High tier
    for v in vertiports:
        for m in king_neighbors(v, adjacency, M):
            add = _ADD_BY_INCOME.get(income[m], 0)
            benefit[m] = max(benefit[m], add)                 # overlap = max
    return benefit


def compute_demand_served(vertiports, start, end, mult):
    """Weighted demand (sum of aircraftMultipliers) originating or terminating
    at each vertiport. Non-vertiport stations serve 0."""
    dem = {}
    for v in vertiports:
        dem[v] = sum(mult[i] for i in range(len(mult))
                     if start[i] == v or end[i] == v)
    return dem


def benefit_sets(benefit):
    """Return (high_benefit, all_benefited) station lists for the two datasets."""
    high = sorted(m for m, b in benefit.items() if b == 3)
    allb = sorted(m for m, b in benefit.items() if b > 0)
    return high, allb


def tier_label(b):
    return {3: "Vertiport", 2: "Medium", 1: "Low", 0: "None"}[b]


if __name__ == "__main__":
    # Self-check against the base scenario (vertiports {1,16}, default income).
    import json
    from _paths import CONFIG_JSON
    CFG = json.load(open(CONFIG_JSON, encoding="utf-8"))
    ADJ, M = CFG["adjacency"], CFG["M"]
    income = build_station_income()
    benefit = compute_benefit([1, 16], income, ADJ, M)
    dem = compute_demand_served([1, 16], CFG["startPos"], CFG["endPos"], CFG["aircraftMultipliers"])
    high, allb = benefit_sets(benefit)
    print(f"{'St':>2}  {'Benefit':<9} {'Income':<7} {'DemandServed':<12}")
    print("-" * 40)
    for m in range(1, M + 1):
        print(f"{m:>2}  {benefit[m]}={tier_label(benefit[m]):<7} {income[m]:<7} {dem.get(m, 0):<12}")
    print(f"\nhigh_benefit  proportionalStations = {high}")
    print(f"all_benefited proportionalStations = {allb}")
