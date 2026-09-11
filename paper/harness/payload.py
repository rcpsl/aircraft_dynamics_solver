"""Faithful Python port of the 5x5 dashboard's buildSolveRequest(), for ALL FIVE
fairness principles.

The dashboard (5x5_realtime_solver/uam-dashboard-NEXT-5x5_v2.html) is the only place
where "a fairness principle" is turned into a /solve payload; the solver itself knows
nothing about principles, only about objective flags and caps. Every experiment in this
paper therefore has to go through the same translation the workshop tool uses, or it
would be measuring a system nobody runs.

`lex_objective_experiment/harness/mkreq.py` already does this for Proportional only.
This module generalises it and is checked against it in validate_payload.py.

Line references below are to uam-dashboard-NEXT-5x5_v2.html as of commit f231cb9.
"""
import math

M = 25

# ── COMMUNITIES, row-major: array index i  <->  solver station i+1 (dashboard :481)
# (baseline dB, Population, Income, vertiport-or-None, name)
ROWS = [
    (45, 'Medium', 'Medium', None,        'Rural-Suburban Outskirts'),
    (55, 'Low',    'High',   None,        'Suburban Tech Campus'),
    (None, None,   None,     None,        'Create Your Own 1'),
    (55, 'High',   'Low',    None,        'University'),
    (45, 'Medium', 'Medium', 'Community', 'Exurban Commuter Town'),
    (45, 'Low',    'Low',    None,        'Quiet Rural Low-Income Community'),
    (45, 'Medium', 'High',   None,        'Affluent Suburban Neighborhood'),
    (45, 'Medium', 'Low',    None,        'Working-Class Homeowner Neighborhood'),
    (None, None,   None,     None,        'Create Your Own 2'),
    (45, 'Low',    'Medium', None,        'Greenbelt Edge'),
    (65, 'Medium', 'Low',    'Airport',   'Airport'),
    (None, None,   None,     None,        'Create Your Own 3'),
    (55, 'Medium', 'High',   None,        'Popular Urban Residence with Shops'),
    (45, 'High',   'Low',    None,        'Lower-Income Urban Neighborhood'),
    (55, 'Medium', 'Medium', None,        'International District'),
    (65, 'Medium', 'Low',    None,        'Underdeveloped Neighborhood'),
    (45, 'Low',    'Medium', None,        'Retirement Community'),
    (65, 'High',   'High',   'Downtown',  'Downtown'),
    (55, 'Medium', 'Medium', None,        'Historic Black Neighborhood'),
    (65, 'High',   'Medium', None,        'New High-Density Development'),
    (55, 'High',   'High',   None,        'Retail and Entertainment Center'),
    (55, 'High',   'Low',    None,        'Mixed Urban Community'),
    (55, 'Medium', 'Medium', None,        'Gentrifying Neighborhood'),
    (None, None,   None,     None,        'Create Your Own 4'),
    (65, 'Low',    'Low',    None,        'Industrial Center'),
]
NAMES = [r[4] for r in ROWS]
# Unclaimed Create-Your-Own tiles are treated as 55 dB (dashboard :753, :706).
BASELINE = [(r[0] if r[0] is not None else 55) for r in ROWS]

# ── Proportional weight model (dashboard :531-545, :568-592)
PROP_SCALE = 3
PROX_BASE = 5
DEFAULT_PROP_ORDER = ('income', 'ambient', 'distance', 'population')
RANKW = [0.40, 0.30, 0.20, 0.10]
RANKW_NOPOP = [0.45, 0.35, 0.20]
PROP_INCOME = {'Low': PROP_SCALE, 'Medium': PROP_SCALE / 2, 'High': 0}
PROP_POPULATION = {'Low': 0, 'Medium': PROP_SCALE / 2, 'High': PROP_SCALE}
PROP_NEUTRAL = PROP_SCALE / 2

# "who counts = People" station weights (dashboard :372)
POPW = {'Low': 1, 'Medium': 2, 'High': 3}

# SOLVER constants (dashboard :451-476)
WIDE_CAP = 30.0
PEOPLE_WEIGHT = 0.3
SLACK = 1
AIRCRAFT_DB = 45.0
DEMAND = (4, 2, 2)

PRINCIPLES = ('equal', 'sufficientarian', 'prioritarian', 'utilitarian', 'proportional')


def vertiport_indices():
    return [i for i, r in enumerate(ROWS) if r[3]]


def proximity_ring(i):
    """Manhattan ring count to the nearest vertiport (dashboard :548)."""
    r, c = divmod(i, 5)
    return min(abs(r - vr) + abs(c - vc)
               for vr, vc in (divmod(v, 5) for v in vertiport_indices()))


def ambient_map(kind='default'):
    """The per-tile ambient level the request is built on.

    'default' is the dashboard's own map. The two variants exist so the fleet-size
    study can ask whether a finding is a property of the principles or of THIS map's
    loud-tile discount, and they are parameters rather than edits to BASELINE because
    the Proportional weights read the same map (prop_factor_scores, 'ambient'), so an
    in-place edit would silently change the price vector as well as the physics.

      'flat55'    every non-vertiport tile at 55 dBA. Removes the discount: adding an
                  aircraft now costs the same dB wherever it flies.
      'quietrow'  the default map with row 3 (stations 11-15), the row the corridors
                  cross, dropped to 45 dBA. Keeps the discount but moves it onto the
                  direct line, so flying straight becomes the expensive option.
    """
    if kind == 'default':
        return list(BASELINE)
    if kind == 'flat55':
        return [55 if ROWS[i][3] is None else BASELINE[i] for i in range(M)]
    if kind == 'quietrow':
        b = list(BASELINE)
        for i in range(10, 15):
            if ROWS[i][3] is None:
                b[i] = 45
        return b
    raise ValueError(f"unknown ambient map {kind!r}")


def prop_factor_scores(ambient=None):
    """Per-tile 0..PROP_SCALE protection score for each factor (dashboard :568)."""
    amb = list(BASELINE) if ambient is None else list(ambient)
    out = []
    for i, (b, pop, inc, _vp, _n) in enumerate(ROWS):
        base = amb[i]
        out.append({
            'income':     PROP_INCOME.get(inc, PROP_NEUTRAL),
            'ambient':    max(0.0, min(1.0, (65 - base) / 20)) * PROP_SCALE,
            'distance':   proximity_ring(i),
            'population': PROP_POPULATION.get(pop, PROP_NEUTRAL),
        })
    return out


def proportional_weights(order=DEFAULT_PROP_ORDER, include_population=True,
                         ambient=None):
    """weight[m] = PROX_BASE ** sum_f rank_f * score_f[m]   (dashboard :580)."""
    clean = []
    for k in order:
        if k in DEFAULT_PROP_ORDER and k not in clean:
            clean.append(k)
    for k in DEFAULT_PROP_ORDER:
        if k not in clean:
            clean.append(k)
    clean = clean[:4]
    ranked = [k for k in clean if include_population or k != 'population']
    rw = RANKW if include_population else RANKW_NOPOP
    w = {k: 0.0 for k in DEFAULT_PROP_ORDER}
    for i, k in enumerate(ranked):
        w[k] = rw[i]
    scores = prop_factor_scores(ambient)
    return [round(PROX_BASE ** sum(w[k] * s[k] for k in ranked), 4) for s in scores]


def adjacency(kind='grid8'):
    """Flight adjacency, WITH self-loops (mandatory under soft T).

    'grid8' is the dashboard's own Chebyshev/Moore neighbourhood: an aircraft may
    step to any of the eight surrounding tiles.

    'grid4' is a von Neumann neighbourhood -- no diagonal steps. It is not in the
    dashboard; it exists so the paper can test whether its degeneracy findings are
    properties of the principles or of a map with abundant routing alternatives.
    Removing diagonals roughly halves the out-degree and lengthens every corridor,
    which is the cheapest way to make routings scarce without changing the city.
    """
    if kind not in ('grid8', 'grid4'):
        raise ValueError(f"unknown adjacency kind {kind!r}")
    A = [[0] * M for _ in range(M)]
    for a in range(M):
        ca, ra = a % 5, a // 5
        for b in range(M):
            cb, rb = b % 5, b // 5
            if kind == 'grid8':
                ok = max(abs(ca - cb), abs(ra - rb)) <= 1
            else:
                ok = abs(ca - cb) + abs(ra - rb) <= 1
            if ok:
                A[a][b] = 1
    return A


def od_pairs():
    """(Downtown,Airport), (Community,Downtown), (Community,Airport) — order matches DEMAND."""
    air = next(i for i, r in enumerate(ROWS) if r[3] == 'Airport')
    dtn = next(i for i, r in enumerate(ROWS) if r[3] == 'Downtown')
    com = next(i for i, r in enumerate(ROWS) if r[3] == 'Community')
    return [(dtn, air), (com, dtn), (com, air)]


def _jsround(x):
    """JavaScript Math.round: half away from zero for positives, NOT Python's
    banker's rounding. round(2.5) is 3 in JS and 2 in Python, and demand factors
    such as 1.25 hit exactly that case, so the difference would silently change
    the fleet size relative to the dashboard."""
    return math.floor(x + 0.5)


def build_streams(demand_factor=1.0, mode='individual', demand=DEMAND):
    """dashboard :621. 'individual' = one aircraft per flight (N=16 at factor 1);
    'split' = two streams per direction at 1/3 and 2/3 of the count (N=12 always)."""
    starts, ends, mult = [], [], []
    for (a, b), c0 in zip(od_pairs(), demand):
        c = max(1, _jsround(c0 * demand_factor))
        for s, e in ((a, b), (b, a)):
            if mode == 'split':
                lo = max(1, _jsround(c / 3))
                hi = max(1, c - lo)
                for m in (lo, hi):
                    starts.append(s + 1); ends.append(e + 1); mult.append(m)
            else:
                for _ in range(c):
                    starts.append(s + 1); ends.append(e + 1); mult.append(1)
    return starts, ends, mult


def chebyshev_t_lower(starts, ends, kind='grid8'):
    """dashboard :642. T >= max hop distance + 1.

    Under grid8 the minimum hop count is the Chebyshev distance; under grid4 it is
    the Manhattan distance. Using the wrong one would send a T_max below the true
    minimum, which the solver reports and the harness retries -- correct, but slow.
    """
    d = 0
    for s, e in zip(starts, ends):
        a, b = s - 1, e - 1
        dc, dr = abs(a % 5 - b % 5), abs(a // 5 - b // 5)
        d = max(d, max(dc, dr) if kind == 'grid8' else dc + dr)
    return max(2, d + 1)


def slack_for(principle, who):
    """dashboard :836. The extra timestep is dropped whenever the utilitarian
    objective is live — by the Utilitarian principle, or by who counts = People."""
    util_on = (principle == 'utilitarian') or (who_for(principle, who) == 'people')
    return 0 if util_on else SLACK


def who_for(principle, who):
    """dashboard :737. Proportional already ranks population, so the People toggle
    is forced off for it to avoid double-counting."""
    return 'communities' if principle == 'proportional' else who


def build_request(principle, who='communities', limit=10, protected=(),
                  demand_factor=1.0, prop_order=DEFAULT_PROP_ORDER,
                  prop_population=True, stream_mode='individual',
                  demand=DEMAND, timeout_ms=600000, slack=None,
                  adjacency_kind='grid8', ambient_kind='default',
                  aircraft_db=AIRCRAFT_DB, **extra):
    """Port of buildSolveRequest() (dashboard :741).

    principle : one of PRINCIPLES
    who       : 'communities' | 'people'
    limit     : the dB limit, used only by Equal and Sufficientarian
    protected : 0-based COMMUNITY INDICES (converted to 1-based stations here)
    """
    if principle not in PRINCIPLES:
        raise ValueError(f"unknown principle {principle!r}")
    starts, ends, mult = build_streams(demand_factor, stream_mode, demand)
    amb = ambient_map(ambient_kind)
    uses_limit = principle in ('equal', 'sufficientarian')
    lim = float(limit) if uses_limit else WIDE_CAP
    # dashboard :753 — the Equal D-tightening is only sound while pigeonhole
    # guarantees an empty station at every timestep.
    some_station_always_empty = len(starts) < M

    people = who_for(principle, who) == 'people'
    util = (principle == 'utilitarian') or people

    req = {
        "N": len(starts), "M": M,
        "D": WIDE_CAP if (principle == 'equal' and not some_station_always_empty) else lim,
        "U": lim if principle == 'equal' else WIDE_CAP,
        "adjacency": adjacency(adjacency_kind),
        "startPositions": starts, "endPositions": ends,
        "aircraftMultipliers": mult,
        "baseline": amb, "aircraftDB": float(aircraft_db),
        "hardT": False,
        "optimizeUtilitarian": util,
        "optimizePrioritarian": principle == 'prioritarian' and len(protected) > 0,
        "optimizeProximity": principle == 'proportional',
        "weightUtilitarian": 1.0 if principle == 'utilitarian' else PEOPLE_WEIGHT,
        "weightPrioritarian": 1.0,
        "weightProximity": 1.0,
        "weightTime": 1.0,
        "utilNoiseMode": principle == 'utilitarian',
        "timeoutMs": timeout_ms,
    }
    if req["optimizePrioritarian"]:
        req["protectedStations"] = [i + 1 for i in protected]
    if req["optimizeProximity"]:
        req["proximityWeights"] = proportional_weights(prop_order, prop_population, amb)
    if util and people:
        req["stationTransitWeights"] = [POPW.get(r[1], 2) for r in ROWS]

    sl = slack_for(principle, who) if slack is None else int(slack)
    req["T_max"] = chebyshev_t_lower(starts, ends, adjacency_kind) + sl
    req.update(extra)
    return req


if __name__ == "__main__":
    import json, sys
    print(json.dumps(build_request(*(sys.argv[1:2] or ['proportional']))))
