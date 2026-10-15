"""Reproduce the dashboard's buildSolveRequest() for ANY (principle, who) pair.

mkreq.py only covers Proportional. This covers all five principles and the People
toggle, because the case under test -- Utilitarian with People on -- is the one
combination where two objectives are live at once.
"""
import mkreq as mk

WIDE = 30
PEOPLE_W = 0.3
POPW = {"Low": 1, "Medium": 2, "High": 3}
PROT = [14, 22, 16]          # Lower-Income Urban, Mixed Urban, Underdeveloped
DEFAULT_LIMIT = 10           # the Equal/Sufficientarian dB limit

def station_transit_weights():
    # attrs default to Medium for the empty stations, matching
    # POPW[(c.attrs?.Population)||'Medium'] on the client.
    return [POPW.get(r[1] or "Medium", 2) for r in mk.rows]

def build(principle, who="communities", limit=DEFAULT_LIMIT, slack=None, **extra):
    """principle: equal | sufficientarian | utilitarian | prioritarian | proportional
       who:       communities | people"""
    people = who == "people"
    util   = principle == "utilitarian" or people
    uses_limit = principle in ("equal", "sufficientarian")
    lim = limit if uses_limit else WIDE

    r = mk.build()                       # start from the real payload, then re-derive
    for k in ("proximityWeights", "protectedStations", "stationTransitWeights"):
        r.pop(k, None)

    some_station_always_empty = r["N"] < 25
    r["D"] = WIDE if (principle == "equal" and not some_station_always_empty) else lim
    r["U"] = lim if principle == "equal" else WIDE

    r["optimizeUtilitarian"]  = util
    r["optimizePrioritarian"] = principle == "prioritarian"
    r["optimizeProximity"]    = principle == "proportional"
    r["weightUtilitarian"]    = 1.0 if principle == "utilitarian" else PEOPLE_W
    r["weightPrioritarian"]   = 1.0
    r["weightProximity"]      = 1.0
    r["weightTime"]           = 1.0
    # One flag cannot serve both meanings, so the PRINCIPLE owns utilNoiseMode and
    # People is expressed through the 0.3 transit weight instead.
    r["utilNoiseMode"]        = principle == "utilitarian"

    if r["optimizePrioritarian"]: r["protectedStations"] = PROT
    if r["optimizeProximity"]:    r["proximityWeights"]  = mk.weights(
        ["income", "ambient", "distance", "population"])
    if util and people:           r["stationTransitWeights"] = station_transit_weights()

    # slackFor(): the extra step is dropped whenever the utilitarian objective is on
    if slack is None:
        slack = 0 if (principle == "utilitarian" or people) else 1
    r["T_max"] = mk.cheb(r["startPositions"], r["endPositions"]) + slack
    r.update(extra)
    return r

def util_noise(res, req):
    """Recompute the Utilitarian noise objective from the RETURNED routing.

    Needed because the solver only reports totalUtilNoise when the objective is
    switched on -- and the whole question is what the number looks like when it is
    switched off. noiseMatrix is M x T of real dB increases, so this is the same
    sum the solver minimizes, in the same units."""
    tw = req.get("stationTransitWeights") or [1] * req["M"]
    return sum(v * tw[m] for m, row in enumerate(res["noiseMatrix"]) for v in row)

def transit_cost(res, req):
    """Recompute the count-mode utilitarian (transit) objective from the routing.

    Mirrors the solver exactly: it[i][t] = moved-by-t AND not-arrived-by-(t-1),
    and each such timestep costs the flown-over tile's weight times the aircraft
    multiplier."""
    tw = req.get("stationTransitWeights") or [1] * req["M"]
    mult = req["aircraftMultipliers"]
    tot = 0
    for i, p in enumerate(res["paths"]):
        end, start = req["endPositions"][i], p[0]
        moved = False
        for t in range(1, len(p)):
            moved = moved or (p[t] != start)
            arrived_by_prev = any(p[k] == end for k in range(t))
            if moved and not arrived_by_prev:
                tot += tw[p[t] - 1] * mult[i]
    return tot

def arrivals(res, req):
    return sum(next((t for t, v in enumerate(p) if v == req["endPositions"][i]), len(p) - 1)
               for i, p in enumerate(res["paths"]))
