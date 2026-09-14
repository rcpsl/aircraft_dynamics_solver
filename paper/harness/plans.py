"""Generate the paper's experiment plans.

usage: python plans.py <name>       writes plans/<name>.json

Every job goes through payload.build_request, which is a validated port of the
dashboard's buildSolveRequest (see validate_payload.py), so each row measures the
system a workshop participant actually drives, not a solver call invented here.

Demand factor -> fleet size (JS-rounded, verified against the dashboard):
    0.25 -> N=6    0.75 -> N=14   1.25 -> N=22   1.75 -> N=30
    0.50 -> N=8    1.00 -> N=16   1.50 -> N=24   2.00 -> N=32
N >= 25 is the regime change: the dashboard's pigeonhole guarantee
(someStationAlwaysEmpty) fails, so Equal stops sending D = limit and sends D = 30.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PRINCIPLES = ('equal', 'sufficientarian', 'prioritarian', 'utilitarian', 'proportional')
FACTORS = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)

# Prioritarian protected set. The source document (Fairness theories in a nutshell)
# specifies "regions that presently and historically have borne the most noise burden
# from existing transportation infrastructure". On this map that is the 65 dB tier;
# Airport (11) and Downtown (18) are excluded because they are vertiports and every
# flight must land at one, which would make the objective unsatisfiable rather than
# binding. That leaves the three loudest non-vertiport tiles.
PROT_BURDEN = (15, 19, 24)      # Underdeveloped Nbhd, New High-Density Dev, Industrial Ctr
# A contrast set placed ON the natural corridors, to separate "the objective is
# satisfied for free" from "this map has nothing to protect".
PROT_CORRIDOR = (16, 13, 18)    # Retirement Community, Lower-Income Urban, Historic Black

# Chosen from the data, session 3. PROT_BURDEN turns out to carry ZERO aircraft-timesteps
# in the baseline routing at every fleet size -- the loudest tiles sit off every corridor,
# which is why the Prioritarian objective evaluates to 0.0 whether or not it is switched
# on. A protected set has to be somewhere aircraft want to fly or the principle has
# nothing to do.
#
# These are the three busiest NON-vertiport tiles that are also Low income, so the set is
# both active and normatively the right shape for Prioritarian -- it protects
# burden-bearing communities rather than whichever tile happens to be loud. Traffic
# summed over the baseline at N=8,16,24,32: 11, 9, 9 aircraft-timesteps.
#   13 -> station 14  Lower-Income Urban Neighborhood   45 dBA, Low income, High pop
#    3 -> station  4  University                        55 dBA, Low income, High pop
#    7 -> station  8  Working-Class Homeowner Nbhd      45 dBA, Low income, Medium pop
PROT_ACTIVE = (13, 3, 7)


def _k(*parts):
    return "|".join(str(p) for p in parts)


def scaling():
    """E1/E2/E3: routing, fairness metrics and solve time against fleet size."""
    jobs = []
    for p in PRINCIPLES:
        for f in FACTORS:
            cfg = {"principle": p, "who": "communities", "limit": 10,
                   "demand_factor": f}
            if p == "prioritarian":
                cfg["protected"] = list(PROT_BURDEN)
            jobs.append({"key": _k("scale", p, "communities", f), "cfg": cfg})
    # who = People, on the four principles that allow the toggle.
    for p in ("equal", "sufficientarian", "prioritarian", "utilitarian"):
        for f in (0.5, 1.0, 1.5, 2.0):
            cfg = {"principle": p, "who": "people", "limit": 10, "demand_factor": f}
            if p == "prioritarian":
                cfg["protected"] = list(PROT_BURDEN)
            jobs.append({"key": _k("scale", p, "people", f), "cfg": cfg})
    return {"out": "results/scaling.jsonl", "par": 9, "wall_kill": 1500, "jobs": jobs}


def ablation():
    """E5: does each principle's objective actually move the routing?

    Control = the identical payload with the principle's optimize* flag cleared.
    Soft T is still on, so phase 2 still runs and still applies the arrival
    tie-break; the ONLY difference is the principle term. Any change in the
    routing is therefore attributable to the principle and nothing else.
    """
    jobs = []
    flag = {"prioritarian": "optimizePrioritarian",
            "utilitarian": "optimizeUtilitarian",
            "proportional": "optimizeProximity"}
    for f in (0.5, 1.0, 1.5):
        for p in ("prioritarian", "utilitarian", "proportional"):
            cfg = {"principle": p, "who": "communities", "limit": 10, "demand_factor": f}
            if p == "prioritarian":
                cfg["protected"] = list(PROT_BURDEN)
            jobs.append({"key": _k("abl", p, "on", f), "cfg": dict(cfg)})
            jobs.append({"key": _k("abl", p, "off", f), "cfg": dict(cfg),
                         "req": {flag[p]: False}})
        # Equal and Sufficientarian have no objective to ablate; their control is
        # each other, plus a wide-cap run showing what the cap alone is buying.
        for p in ("equal", "sufficientarian"):
            cfg = {"principle": p, "who": "communities", "limit": 10, "demand_factor": f}
            jobs.append({"key": _k("abl", p, "on", f), "cfg": dict(cfg)})
            jobs.append({"key": _k("abl", p, "off", f), "cfg": dict(cfg),
                         "req": {"D": 30.0, "U": 30.0}})
    return {"out": "results/ablation.jsonl", "par": 9, "wall_kill": 1500, "jobs": jobs}


def caps():
    """E4: the cap-tightening study. Sufficientarian sweeps D, Equal sweeps U.

    This is where the 'a cap on ADDED noise protects the quiet and loads the loud'
    claim is tested, and where the unsat cliff at D=3 should appear.
    """
    jobs = []
    for lim in (3, 4, 5, 7, 10, 15, 20):
        for p in ("sufficientarian", "equal"):
            jobs.append({"key": _k("cap", p, lim),
                         "cfg": {"principle": p, "who": "communities",
                                 "limit": lim, "demand_factor": 1.0}})
    return {"out": "results/caps.jsonl", "par": 9, "wall_kill": 1500, "jobs": jobs}


def prior_sets():
    """E6: is Prioritarian's zero objective a property of the map or of the choice?"""
    jobs = []
    for name, prot in (("burden", PROT_BURDEN), ("corridor", PROT_CORRIDOR)):
        for f in (0.5, 1.0, 1.5, 2.0):
            jobs.append({"key": _k("prot", name, f),
                         "cfg": {"principle": "prioritarian", "who": "communities",
                                 "limit": 10, "demand_factor": f,
                                 "protected": list(prot)}})
    return {"out": "results/prior_sets.jsonl", "par": 8, "wall_kill": 1500, "jobs": jobs}


def reps():
    """Run-to-run timing variance. Routings are deterministic for a fixed payload,
    so these repetitions measure the clock, not the answer -- which is itself the
    claim being checked."""
    jobs = []
    for p in ("sufficientarian", "utilitarian", "proportional"):
        for r in range(3):
            jobs.append({"key": _k("rep", p, r),
                         "cfg": {"principle": p, "who": "communities",
                                 "limit": 10, "demand_factor": 1.0}})
    return {"out": "results/reps.jsonl", "par": 3, "wall_kill": 1500, "jobs": jobs}


def grid4():
    """Second instance: the same city, but no diagonal flight.

    Every finding in Sec. IV except Proposition 1 is a measurement on one map with
    abundant routing alternatives. Removing diagonals halves the out-degree and
    lengthens every corridor, which is the cheapest way to make routings scarce
    without changing the city, the demand or the principles. If the degeneracy
    results are artefacts of routing abundance, this is where they break.

    Covers the three claims that could break: the tier-share ordering (scaling
    rows), whether Prioritarian is still inert (ablation + both protected sets),
    and whether some community is still always at zero added noise.
    """
    jobs = []
    for p in PRINCIPLES:
        for f in (0.5, 1.0, 1.5):
            cfg = {"principle": p, "who": "communities", "limit": 10,
                   "demand_factor": f, "adjacency_kind": "grid4"}
            if p == "prioritarian":
                cfg["protected"] = list(PROT_BURDEN)
            jobs.append({"key": _k("g4", p, f), "cfg": cfg})
    # Ablation at the default demand: is any principle binding once routings are scarce?
    flag = {"prioritarian": "optimizePrioritarian",
            "utilitarian": "optimizeUtilitarian",
            "proportional": "optimizeProximity"}
    for p in ("prioritarian", "utilitarian", "proportional"):
        cfg = {"principle": p, "who": "communities", "limit": 10,
               "demand_factor": 1.0, "adjacency_kind": "grid4"}
        if p == "prioritarian":
            cfg["protected"] = list(PROT_BURDEN)
        jobs.append({"key": _k("g4abl", p, "off", 1.0), "cfg": dict(cfg),
                     "req": {flag[p]: False}})
    for p in ("equal", "sufficientarian"):
        jobs.append({"key": _k("g4abl", p, "off", 1.0),
                     "cfg": {"principle": p, "who": "communities", "limit": 10,
                             "demand_factor": 1.0, "adjacency_kind": "grid4"},
                     "req": {"D": 30.0, "U": 30.0}})
    # The corridor protected set matters more here: with diagonals gone there are
    # far fewer ways around a community sitting on the direct line.
    for f in (0.5, 1.0, 1.5):
        jobs.append({"key": _k("g4prot", "corridor", f),
                     "cfg": {"principle": "prioritarian", "who": "communities",
                             "limit": 10, "demand_factor": f,
                             "protected": list(PROT_CORRIDOR),
                             "adjacency_kind": "grid4"}})
    return {"out": "results/grid4.jsonl", "par": 9, "wall_kill": 1500, "jobs": jobs}


def binding():
    """Can Equal and Sufficientarian be made to bind, and to differ from each other?

    Two separate questions, and they need different levers.

    (A) DOES THE CAP CHANGE THE ROUTE AT ALL? Compare each limit against the identical
    payload with the cap opened to 30 dB. Both runs still carry the soft-T arrival
    objective, so if the capped run has a HIGHER arrival penalty the cap has provably
    excluded the unconstrained optimum -- it is binding, not merely present. Limits go
    down to 3 dB, where a 45 dBA tile holds zero aircraft.

    (B) CAN THEY DIVERGE FROM EACH OTHER? Equal caps the spread, Sufficientarian the
    level, and the two coincide exactly while some community sits at zero added noise
    (Prop. 1). Breaking that needs EVERY tile occupied at the binding timestep, which
    needs many more aircraft than tiles. We push demand to N=48 and N=64 and record
    whether the minimum ever lifts off zero. A negative answer is also a result: it
    would mean the disparity cap cannot be made to act as one on this map.
    """
    jobs = []
    # (A) tight caps vs. an open-cap control, at two fleet sizes.
    for f in (1.0, 2.0):
        for p in ("equal", "sufficientarian"):
            for lim in (3, 4, 5, 6, 8, 10):
                jobs.append({"key": _k("bind", p, lim, f),
                             "cfg": {"principle": p, "who": "communities",
                                     "limit": lim, "demand_factor": f}})
            jobs.append({"key": _k("bind", p, "wide", f),
                         "cfg": {"principle": p, "who": "communities",
                                 "limit": 10, "demand_factor": f},
                         "req": {"D": 30.0, "U": 30.0}})
    # (B) saturate the map. Above N=25 the dashboard stops sending D alongside U for
    # Equal, so these are the only rows where the two payloads genuinely differ.
    for f in (3.0, 4.0):
        for p in ("equal", "sufficientarian"):
            for lim in (5, 8):
                jobs.append({"key": _k("sat", p, lim, f),
                             "cfg": {"principle": p, "who": "communities",
                                     "limit": lim, "demand_factor": f}})
    return {"out": "results/binding.jsonl", "par": 9, "wall_kill": 1800, "jobs": jobs}


def longbudget():
    """Prove what the 600 s workshop budget could only guess at.

    Utilitarian and Proportional return unproven incumbents at almost every fleet size
    under the production budget, which forces a caveat onto every comparison involving
    them. That budget exists so a room full of people is not left waiting; it is not a
    property of the problem. Here each solve gets up to four hours.

    What this can settle:
      * whether the tier-share ordering in Sec. IV-E holds between PROVEN optima;
      * whether the ablation's "binds / does not bind" verdicts survive;
      * where the real tractability wall is, as opposed to where the budget is.
    """
    H = 3600 * 1000
    jobs = []
    # The two decibel-valued objectives, from the smallest fleet upward. 4 h each.
    for p in ("utilitarian", "proportional"):
        for f in (0.25, 0.5, 0.75, 1.0):
            jobs.append({"key": _k("long", p, f),
                         "cfg": {"principle": p, "who": "communities",
                                 "limit": 10, "demand_factor": f},
                         "timeout_ms": 4 * H})
    # Their ablation controls at the default demand, so the comparison in Sec. IV-G is
    # proven-against-proven rather than partial-against-proven.
    flag = {"utilitarian": "optimizeUtilitarian", "proportional": "optimizeProximity"}
    for p in ("utilitarian", "proportional"):
        jobs.append({"key": _k("longabl", p, "off", 1.0),
                     "cfg": {"principle": p, "who": "communities",
                             "limit": 10, "demand_factor": 1.0},
                     "req": {flag[p]: False}, "timeout_ms": 2 * H})
    # Prioritarian at the sizes where 600 s was not enough.
    for f in (1.5, 1.75, 2.0):
        jobs.append({"key": _k("long", "prioritarian", f),
                     "cfg": {"principle": "prioritarian", "who": "communities",
                             "limit": 10, "demand_factor": f,
                             "protected": list(PROT_BURDEN)},
                     "timeout_ms": 4 * H})
    # The three runs that fell back to an unweighted route at N=32 -- did they fail
    # because the problem is hard, or only because the clock was short?
    for p, who in (("equal", "communities"), ("equal", "people"),
                   ("sufficientarian", "people")):
        jobs.append({"key": _k("longfb", p, who, 2.0),
                     "cfg": {"principle": p, "who": who, "limit": 10,
                             "demand_factor": 2.0},
                     "timeout_ms": 4 * H})
    return {"out": "results/longbudget.jsonl", "par": 8, "wall_kill": 15000,
            "jobs": jobs}


def budgetfix():
    """Give the ablation's N=24 treatment cells the same budget as N=8 and N=16.

    Table III's two headline trends -- Utilitarian's effect decaying, Proportional's
    failing -- both terminate at N=24, and that is the one column never re-run at four
    hours: longbudget covered demand 0.25-1.0 only, and rescue skips `partial` rows
    because an incumbent counts as settled. A shorter search produces exactly the
    signature both trends show, a worse ratio, so until these land the trends cannot be
    told apart from a budget artefact.

    The cfg-keyed merge in analyze.load upgrades the ablation cells automatically once
    these rows exist; no analysis change is needed.
    """
    H = 3600 * 1000
    return {"out": "results/budgetfix.jsonl", "par": 5, "wall_kill": 16000,
            "jobs": [{"key": _k("long", p, 1.5),
                      "cfg": {"principle": p, "who": "communities",
                              "limit": 10, "demand_factor": 1.5},
                      "timeout_ms": 4 * H}
                     for p in ("utilitarian", "proportional")]}


def propranking():
    """Does the participant ranking change the Proportional routing?

    Contribution 1 claims "benefit" is an editable input rather than a hidden constant,
    and Sec. III-G spends a subsection on the price construction -- the base, the rank
    weights, the sign of the distance factor. No plan has ever varied any of it:
    Proportional ran at ONE ranking in all 213 solves. This is the question the workshop
    tool exists to ask, and the paper cannot currently answer it.

    Three orders chosen to move the price vector as far apart as the construction
    allows, holding demand, caps and horizon fixed.
    """
    H = 3600 * 1000
    orders = {
        "income":   ("income", "ambient", "distance", "population"),   # the default
        "distance": ("distance", "population", "income", "ambient"),
        "ambient":  ("ambient", "distance", "population", "income"),
    }
    return {"out": "results/propranking.jsonl", "par": 3, "wall_kill": 16000,
            "jobs": [{"key": _k("rank", name),
                      "cfg": {"principle": "proportional", "who": "communities",
                              "limit": 10, "demand_factor": 1.0,
                              "prop_order": list(o)},
                      "timeout_ms": 4 * H}
                     for name, o in orders.items()]}


# ==========================================================================
# FLEET-SIZE STUDY (2026-09-09 redirection).
#
# Everything below answers one question: how does each principle shape the routing,
# and how does that response change as the fleet grows past the 25 tiles of the map.
# Three things separate it from every sweep above.
#
# UNLIMITED BUDGET. Each solve runs to completion, so a row is `optimal` or
# `infeasible` and never "whatever the clock allowed". Every retraction in
# claims_audit.md came from comparing a run that ran out of time against one that did
# not; removing the clock removes the whole class of error. The cost is that some
# cells run for days, which is why worker.py now checkpoints.
#
# SIX CONDITIONS. The five principles plus a `baseline` -- the same fleet with the
# caps opened and every objective off, i.e. the solver's own shortest-time routing.
# Without it "Utilitarian detours by two hops" has no zero to be measured against.
#
# A SETUP, NOT A DEFAULT. The dashboard's default gives T_max one step above the
# Chebyshev floor, which leaves almost nowhere to detour to, so a principle can only
# express itself by reordering aircraft. `SETUP_MAIN` below is the setup selected by
# the Phase-1b screen for actually separating the principles; the default is kept as
# the reference.
# ==========================================================================

UNLIMITED_MS = 10 ** 9        # ~11.6 days of Z3 budget: cannot fire
NO_WALL_KILL = 10 ** 9        # seconds; the runner's hard kill, disabled

WIDE = 30.0                   # payload.WIDE_CAP, repeated to keep plans.py standalone

# The knobs Phase 1b screens over. A setup is this dict with some of them moved.
SETUP_DEFAULT = {
    "name": "default",
    "slack": None,            # None = the dashboard's own per-principle slack
    "limit": 10,              # D for Sufficientarian, U for Equal
    "hard_cap": None,         # if set, every principle faces this D
    "aircraft_db": 45.0,
    "demand": (4, 2, 2),
    "protected": PROT_BURDEN,
    "ambient_kind": "default",
}

# Chosen by the session-3 setup screen; log and justification in results/setup_choice.md.
#
# D = 6 applied to every principle (Equal and Sufficientarian through `limit`, the three
# objective principles through a `req` override) so that all five face one hard cap and
# differ only in their objective; the protected set moved onto the corridor.
#
# Why this and not the tool's default: at D = 10 with PROT_BURDEN, three of the five
# principles constrain nothing. The caps sit at capacity utilisation 0.31 and 0.25 and
# produce no attributable difference from the wide-cap baseline, and the protected set
# carries zero aircraft-timesteps so its objective is satisfied for free. At D = 6 with
# PROT_ACTIVE all five are active at N = 16: both caps bind exactly (utilisation 1.00),
# the Prioritarian control puts 3.45 dB on the protected set and the objective removes
# it, and both decibel objectives beat the baseline's score on their own metric by more
# than the permutation floor (17.9 vs 16.1, and 504.5 vs 16.1).
#
# D = 6 over D = 5: identical on activity (5/5) and on knobs moved (2), but more
# attributable differences at N = 24 (2/6 against 1/6), and the looser cap is the one
# more likely to stay tractable at the top of the ladder.
# `objective_encoding` selects which of the two forms the solver already exposes the
# two decibel-valued objectives run under. "count" sets utilNoiseMode=False and
# proximityMode="count"; "dB" leaves the tool's defaults. Sec. III describes both, so
# this states which encoding of the principle the ladder measures, not a new principle.
#
# Measured on SETUP_MAIN before choosing (results/encoding.jsonl): count mode proves
# every cell 4/4 permutations at N=6, 8 and 16 -- Utilitarian in 26 s and Proportional
# in 119 s at N=16, where the dB form did not prove in 15.4 h. At N=8 the speedups are
# 51x and 1110x. That is the difference between a ladder with two conditions on it and a
# ladder with five.
SETUP_MAIN = dict(SETUP_DEFAULT, hard_cap=6, limit=6, protected=PROT_ACTIVE,
                  objective_encoding="count", name="D6_protA")

# Request overrides that select the count-weighted form of each objective.
COUNT_ENCODING = {"utilitarian": {"utilNoiseMode": False},
                  "proportional": {"proximityMode": "count"}}

CONDITIONS = PRINCIPLES + ("baseline",)
# `prioritarian_off` is a control, not a condition of the study; it appears only
# in the setup screen, where Prioritarian's activity test needs it.
CONTROLS = ("prioritarian_off",)

# The flag each principle's objective rides on, for building its control.
OBJ_FLAG = {"prioritarian": "optimizePrioritarian",
            "utilitarian": "optimizeUtilitarian",
            "proportional": "optimizeProximity"}


def setup_of(**over):
    s = dict(SETUP_DEFAULT)
    s.update(over)
    if "name" not in over:
        short = {"slack": "sl", "hard_cap": "D", "limit": "lim",
                 "aircraft_db": "src", "demand": "dem", "protected": "prot",
                 "ambient_kind": "amb"}
        moved = []
        for k, v in over.items():
            if SETUP_DEFAULT.get(k) == v:
                continue
            if isinstance(v, (tuple, list)):
                v = "-".join(str(x) for x in v)
            elif isinstance(v, float) and v == int(v):
                v = int(v)
            moved.append(f"{short.get(k, k)}{v}")
        s["name"] = "_".join(moved) or "default"
    return s


def _cfg(setup, principle, factor):
    """The build_request kwargs for one condition. Only knobs that have MOVED are
    written, so a default-setup row keeps a cfg identical to the dashboard's own."""
    cfg = {"principle": principle, "who": "communities",
           "limit": setup["limit"], "demand_factor": factor}
    if principle == "prioritarian":
        cfg["protected"] = list(setup["protected"])
    if setup["slack"] is not None:
        cfg["slack"] = setup["slack"]
    if setup["aircraft_db"] != SETUP_DEFAULT["aircraft_db"]:
        cfg["aircraft_db"] = setup["aircraft_db"]
    if tuple(setup["demand"]) != SETUP_DEFAULT["demand"]:
        cfg["demand"] = list(setup["demand"])
    if setup["ambient_kind"] != SETUP_DEFAULT["ambient_kind"]:
        cfg["ambient_kind"] = setup["ambient_kind"]
    return cfg


def perm_req(setup, factor, seed, stream_mode='individual'):
    """A `req` override that relabels which aircraft is listed first.

    The permuted problem is the SAME problem: same origin-destination pairs, same
    fleet, same feasible set, same optimum under a different name. What changes is the
    order Z3 creates its variables in, and therefore which member of the optimal set it
    returns. Running every cell under several permutations turns the tie-break from an
    unmeasured confound into a measured band.

    The seed depends only on (factor, seed), NOT on the condition, so at permutation k
    every condition faces the identical aircraft ordering. That makes the comparison
    paired: a difference between two conditions at the same k cannot be an ordering
    difference, because they had the same ordering.

    T_max is unaffected -- chebyshev_t_lower takes a max over the OD pairs, and the
    multiset of pairs is preserved -- so the horizon does not move either.
    """
    import random
    import payload as P
    starts, ends, mult = P.build_streams(factor, stream_mode, tuple(setup["demand"]))
    idx = list(range(len(starts)))
    if seed:
        random.Random(1000 * seed + int(factor * 100)).shuffle(idx)
    return {"startPositions": [starts[i] for i in idx],
            "endPositions": [ends[i] for i in idx],
            "aircraftMultipliers": [mult[i] for i in idx]}


def condition(setup, name, factor, key, perm=None):
    """One of the six conditions as a runnable job.

    `baseline` is built from the Equal payload with the caps opened and every
    optimize* flag cleared, the way ablation() builds its "off" controls: same fleet,
    same adjacency, same soft-T arrival tie-break, no fairness constraint and no
    fairness objective. It is the shortest-time routing the solver would serve if
    nobody had chosen a principle, and it is the zero for every travel-time number in
    the paper.
    """
    if name == "baseline":
        cfg = _cfg(setup, "equal", factor)
        req = {"D": WIDE, "U": WIDE, "optimizeUtilitarian": False,
               "optimizePrioritarian": False, "optimizeProximity": False}
    elif name == "prioritarian_off":
        # Prioritarian's own ablation control: the identical payload with only its
        # objective cleared. It answers the question the principle's activity turns on
        # -- would the protected set be overflown if nobody were protecting it? -- which
        # the wide-cap baseline cannot, because the baseline also drops the cap.
        cfg = _cfg(setup, "prioritarian", factor)
        req = {"optimizePrioritarian": False}
        if setup["hard_cap"] is not None:
            req["D"] = float(setup["hard_cap"])
    elif name in DB_FORMS:
        # The exact (decibel) encoding of an objective principle: the same payload as
        # the ladder's condition, same cap, without the count override. The overrides
        # are written out even where they equal the payload default, so a row says
        # which encoding it ran without anyone having to know the default.
        principle, over = DB_FORMS[name]
        cfg = _cfg(setup, principle, factor)
        req = {}
        if setup["hard_cap"] is not None:
            req["D"] = float(setup["hard_cap"])
        req.update(over)
    else:
        cfg = _cfg(setup, name, factor)
        req = {}
        # Knob 2: make every principle face the SAME hard cap, so the five differ
        # only in their objective. Equal and Sufficientarian already get it through
        # `limit` (and Equal's pigeonhole guard, which must keep applying).
        if setup["hard_cap"] is not None and name not in ("equal", "sufficientarian"):
            req["D"] = float(setup["hard_cap"])
        if setup.get("objective_encoding") == "count" and name in COUNT_ENCODING:
            req.update(COUNT_ENCODING[name])
    if perm is not None:
        req.update(perm_req(setup, factor, perm))
    job = {"key": key, "cfg": cfg, "timeout_ms": UNLIMITED_MS,
           "setup": {k: (list(v) if isinstance(v, tuple) else v)
                     for k, v in setup.items()}}
    if perm is not None:
        job["perm"] = perm
    if req:
        job["req"] = req
    return job


K_PERM = 4          # permutations per cell; the spread over them IS the floor


def _sweep(setup, factors, out, prefix, conditions=CONDITIONS, par=8,
           timeout_ms=UNLIMITED_MS, wall_kill=NO_WALL_KILL, K=K_PERM):
    """Jobs ordered SMALL N FIRST, all conditions and permutations at one N.

    The runner pops from the front, so this ordering is what makes the ladder complete
    from the bottom: whenever the sweep is stopped, every N below the frontier is
    finished for all six conditions and is publishable as it stands.

    K > 1 runs each cell under K aircraft orderings. Without that a cell is one draw
    from the set of equally-optimal routings and its distance from another condition
    cannot be told from the distance between two draws of the same condition -- which
    is what sessions 1-2 established the hard way. K=1 keeps the old single-draw
    behaviour for screens, where the decision does not rest on a margin.
    """
    jobs = []
    for f in factors:
        for c in conditions:
            for k in (range(K) if K > 1 else [None]):
                key = _k(prefix, setup["name"], c, f) + (f"|p{k}" if K > 1 else "")
                j = condition(setup, c, f, key, perm=k)
                j["timeout_ms"] = timeout_ms
                jobs.append(j)
    return {"out": out, "par": par, "wall_kill": wall_kill,
            "checkpoint_s": 600, "setup": setup, "K": K, "jobs": jobs}


# ---------------------------------------------------------------- Phase 1b screen
#
# The knobs, in the order they are tried. One at a time, stopping at the first setup
# that passes the divergence check; if none passes alone, the two strongest combine.
#
# Horizon slack is first because it is the likeliest explanation for why every prior
# run flew shortest paths: the dashboard sends T_max = Chebyshev floor + 1 (+ 0 when
# the Utilitarian term is live), so there is barely a timestep of room to detour into.
# A principle with nowhere to go can only reorder aircraft, which occupancy cannot see.
SCREEN_KNOBS = [
    ("slack",      [{"slack": s} for s in (2, 3, 4)]),
    ("cap",        [{"hard_cap": d, "limit": d} for d in (8, 6, 5, 4)]),
    ("aircraftdb", [{"aircraft_db": a} for a in (50.0, 55.0)]),
    ("demand",     [{"demand": d} for d in ((2, 4, 2), (2, 2, 4), (4, 4, 0))]),
    ("protected",  [{"protected": PROT_CORRIDOR}]),
    ("ambient",    [{"ambient_kind": k} for k in ("flat55", "quietrow")]),
]

# Screening runs are capped. They decide which setup the paper is written on; they are
# never paper data, and no screen row reaches a table, a figure or fleet_metrics.csv
# (see DECISIONS.md D4). Utilitarian and Proportional do not settle at N=16 on any
# budget this session has, so without a cap the screen could not return at all.
SCREEN_MS = 900_000
SCREEN_KILL = 1200


# Session 3: the candidate setups, chosen from what sessions 1-2 measured rather than
# from the generic knob list. The cap is the lever that activates Equal and
# Sufficientarian (the cap sweep puts the binding point at D=5-6); the protected set is
# the lever that activates Prioritarian, and nothing else can, because its objective is
# zero wherever the set is off-corridor. Utilitarian and Proportional are already active
# at the default, so no knob is aimed at them.
SETUP3_CANDIDATES = [
    dict(hard_cap=6, limit=6, name="D6"),
    dict(hard_cap=5, limit=5, name="D5"),
    dict(protected=PROT_ACTIVE, name="protA"),
    dict(hard_cap=6, limit=6, protected=PROT_ACTIVE, name="D6_protA"),
    dict(hard_cap=5, limit=5, protected=PROT_ACTIVE, name="D5_protA"),
]
# The four that prove out fast, plus the baseline reference and Prioritarian's own
# ablation control. Utilitarian and Proportional are screened separately as probes.
SCREEN3_CONDS = ("equal", "sufficientarian", "prioritarian", "prioritarian_off",
                 "baseline")


def screen3(factors=(1.0,), setups=None, conds=SCREEN3_CONDS, K=K_PERM):
    """Session 3 setup search: which setups make every principle ACTIVE?

    Unlimited budget and K permutations per cell, because the verdict is a margin and a
    margin needs its floor measured alongside it. That is the whole change from the
    session-1 screen, which accepted "the routings differ" as evidence -- and distinct
    routings are exactly what the tie-break produces for free.
    """
    jobs = []
    for over in (setups if setups is not None else SETUP3_CANDIDATES):
        s = setup_of(**over)
        for f in factors:
            for c in conds:
                for k in range(K):
                    key = _k("s3", s["name"], c, f) + f"|p{k}"
                    jobs.append(condition(s, c, f, key, perm=k))
    return {"out": "results/screen3.jsonl", "par": 8, "wall_kill": NO_WALL_KILL,
            "checkpoint_s": 600, "K": K, "jobs": jobs}


def screen3_probe(setups, factors=(1.0,), ms=1800_000):
    """Utilitarian and Proportional at a candidate setup, capped.

    D4 convention: probes decide, they never enter a table. Their activity test is
    whether the objective's own value beats what the baseline routing scores on that
    same objective, by more than the cap-based floor at the same setup.
    """
    jobs = []
    for over in setups:
        s = setup_of(**over)
        for f in factors:
            for c in ("utilitarian", "proportional"):
                j = condition(s, c, f, _k("s3p", s["name"], c, f), perm=0)
                j["timeout_ms"] = ms
                j["probe"] = True
                jobs.append(j)
    return {"out": "results/screen3.jsonl", "par": 8, "wall_kill": ms // 1000 + 300,
            "checkpoint_s": 600, "jobs": jobs}


def screen_setups(knob=None):
    """The setups to screen, in order. `knob` restricts to one group."""
    out = []
    for name, variants in SCREEN_KNOBS:
        if knob and name != knob:
            continue
        for v in variants:
            out.append(setup_of(**v))
    return out


def screen(knob=None, factors=(1.0,), setups=None):
    """Phase 1b: screen one knob group at N=16 (and, when a knob passes, N=8 and 24).

    Everything lands in results/screen.jsonl, keyed by setup name, with the full setup
    dict on every row.
    """
    jobs = []
    for s in (setups if setups is not None else screen_setups(knob)):
        for f in factors:
            for c in CONDITIONS:
                j = condition(s, c, f, _k("scr", s["name"], c, f))
                j["timeout_ms"] = SCREEN_MS
                j["probe"] = True
                jobs.append(j)
    return {"out": "results/screen.jsonl", "par": 8, "wall_kill": SCREEN_KILL,
            "checkpoint_s": 600, "jobs": jobs}


def pilot():
    """Phase 1: the six conditions at N=16 on the dashboard's default setup.

    This is the divergence check's input, not a paper result on its own. If the five
    principles return five routings a reader can tell apart here, the fleet sweep runs
    on this setup; if they do not, screen() looks for one where they do.
    """
    return _sweep(SETUP_DEFAULT, (1.0,), "results/pilot.jsonl", "pilot")


def fleet():
    """Phase 2: the main sweep. Six conditions across the fleet ladder, unlimited.

    N >= 25 is a documented regime change and not a defect: build_request stops
    tightening D alongside U for Equal there, because the pigeonhole argument that
    guaranteed an empty station at every timestep no longer holds with more aircraft
    than tiles.
    """
    return _sweep(SETUP_MAIN, FACTORS, "results/fleet.jsonl", "fleet")


# Phase 2 runs as two sequential lanes into one results/fleet.jsonl. Thirteen of the
# 48 cells do not terminate on any horizon this session has (Utilitarian from N=14,
# Proportional from N=8), which is more than `par`, so interleaved they would occupy
# every slot before the ladder reached N=22 and the tractable cells at N=22, 24, 30, 32
# would never start. Splitting them lets the tractable ladder complete from the bottom,
# which is what the small-N-first ordering is for. See DECISIONS.md D3.
LANE_A = ("equal", "sufficientarian", "prioritarian", "baseline")
LANE_B = ("utilitarian", "proportional")


def fleet_a():
    """Lane A: the conditions that terminate. Completes."""
    return _sweep(SETUP_MAIN, FACTORS, "results/fleet.jsonl", "fleet",
                  conditions=LANE_A)


def fleet_b():
    """Lane B: Utilitarian and Proportional. Runs until stopped; how far it gets is
    the tractability result Experiment 4 reports."""
    return _sweep(SETUP_MAIN, FACTORS, "results/fleet.jsonl", "fleet",
                  conditions=LANE_B)


# ==========================================================================
# The two sweeps that exist because the main ladder shows NOTHING on travel time.
#
# Across all eight fleet sizes, the spread in `extra_vs_floor` between proven cells
# is exactly 0: every condition flies the shortest-path floor. Congestion and noise
# separate the principles cleanly; travel time does not separate them at all. That
# is a real finding, but a finding of the form "this lever is dead at this setup" is
# only worth stating once you have shown what DOES move it.
#
# Two independent mechanisms could, and they act on different halves of the menu:
#
#   E5 slack      An objective will buy noise with travel time if the horizon gives
#                 it anywhere to go. The tool sends T_max = Chebyshev floor + 1
#                 (+ 0 with the Utilitarian term live), which is barely a timestep.
#                 A screen at N=16 already showed Utilitarian and Proportional flying
#                 108 and 104 fleet hops against a floor of 44 at slack 3, while the
#                 three cap-based principles proved optimal and still flew 44.
#                 So this lever is expected to separate OBJECTIVES from CAPS.
#
#   E6 cap        A cap that binds forces traffic off full tiles, and the detour is
#                 the only way to route around them. This is the lever expected to
#                 move EQUAL and SUFFICIENTARIAN, which E5 leaves untouched.
#
# Together they say which principles can be made to cost travel time, and by what.
# ==========================================================================

SLACKS = (1, 2, 3, 4)
CAP_LIMITS = (3, 4, 5, 6, 8)      # D=10 is the default and is already in fleet.jsonl


def slack_sweep():
    """E5, paper grade: the four conditions that prove out, across horizon slack.

    Unlimited budget, so every cell is a proven optimum and a zero detour means the
    principle DECLINED the room rather than ran out of clock.
    """
    jobs = []
    for f in (0.5, 1.0, 1.5):
        for s in SLACKS:
            setup = setup_of(slack=s)
            for c in LANE_A:
                jobs.append(condition(setup, c, f, _k("sl", s, c, f)))
    return {"out": "results/slack.jsonl", "par": 8, "wall_kill": NO_WALL_KILL,
            "checkpoint_s": 600, "jobs": jobs}


def slack_probe():
    """E5, screening half: the two objectives, which do not prove at this horizon.

    Capped and marked `probe`, so nothing here reaches a table as a value. What it
    contributes is the DIRECTION -- whether the objective uses the room at all --
    which is visible in a routing regardless of whether that routing is optimal.
    """
    jobs = []
    for f in (0.5, 1.0):
        for s in SLACKS:
            setup = setup_of(slack=s)
            for c in LANE_B:
                j = condition(setup, c, f, _k("slp", s, c, f))
                j["timeout_ms"] = SCREEN_MS
                j["probe"] = True
                jobs.append(j)
    return {"out": "results/slack.jsonl", "par": 8, "wall_kill": SCREEN_KILL,
            "checkpoint_s": 600, "jobs": jobs}


def cap_sweep():
    """E6: tighten the cap until it bites, and watch what the traffic does.

    Equal and Sufficientarian only -- they are the two principles the cap IS. The
    other three send the wide cap by construction, so there is nothing to tighten.
    `caps.jsonl` in the old corpus puts the infeasibility cliff at D=3, which is why
    the ladder starts there: an infeasible cell is a real answer about where the
    rule stops being satisfiable at all.
    """
    jobs = []
    for f in (1.0, 2.0):
        for lim in CAP_LIMITS:
            setup = setup_of(limit=lim)
            for c in ("equal", "sufficientarian"):
                jobs.append(condition(setup, c, f, _k("cap", lim, c, f)))
    return {"out": "results/captight.jsonl", "par": 8, "wall_kill": NO_WALL_KILL,
            "checkpoint_s": 600, "jobs": jobs}


def perm_sweep(k=6, factors=(1.0, 1.5)):
    """The indifference floor, measured a second way: permute the aircraft list.

    The slack sweep measures the floor by widening the horizon, and that instrument has
    a weakness -- a longer horizon is a strictly LARGER feasible set, so in principle a
    condition could genuinely do better in it. (It does not: arrival is identical at
    every slack. But the objection is available.)

    Permuting the aircraft has no such weakness. Relabelling which aircraft is listed
    first leaves the problem mathematically identical: the same origin-destination
    pairs, the same fleet, the same feasible set, the same optimum. Every routing
    available before is available after. So ANY difference in the returned routing is
    the tie-break and nothing else, and the range over permutations is a floor with no
    confound at all.

    Z3's search order depends on the order its variables are created, which is the
    order the aircraft arrive in, so the permutations do return different routings.
    That is the point: they are all equally optimal, and which one a community actually
    lives under is decided by an ordering nobody chose deliberately.
    """
    import payload as P
    import random
    jobs = []
    for f in factors:
        starts, ends, mult = P.build_streams(f)
        for seed in range(k):
            idx = list(range(len(starts)))
            if seed:
                random.Random(seed).shuffle(idx)
            perm = {"startPositions": [starts[i] for i in idx],
                    "endPositions": [ends[i] for i in idx],
                    "aircraftMultipliers": [mult[i] for i in idx]}
            for c in LANE_A:
                j = condition(SETUP_DEFAULT, c, f, _k("perm", seed, c, f))
                j["req"] = dict(j.get("req", {}), **perm)
                j["perm_seed"] = seed
                jobs.append(j)
    return {"out": "results/perm.jsonl", "par": 8, "wall_kill": NO_WALL_KILL,
            "checkpoint_s": 600, "jobs": jobs}


def encoding_screen(factors=(0.25, 0.5, 1.0), K=K_PERM):
    """Step 3: can either objective be made to finish, without touching the solver?

    Utilitarian and Proportional stall because both objectives are decibel-valued
    lookups -- Z3 has to drive a table of dB expressions to its optimum and then prove
    it there. The solver already exposes a count-weighted form of each, and the request
    parameters that select them cost no code change:

        utilNoiseMode: false        Utilitarian over aircraft counts, not added dB
        proximityMode: "count"      Proportional prices plain occupancy, not dB

    Sec. III already describes both modes, so using one is a statement about which
    encoding of the principle the ladder runs, not a new principle. Run unlimited at the
    bottom of the ladder: if a count-mode cell proves where the dB cell does not, that is
    the tractable encoding, and N=6/N=8 -- where both prove -- is where the two can be
    compared on the routing they return.
    """
    jobs = []
    for f in factors:
        for c, over in (("utilitarian", {"utilNoiseMode": False}),
                        ("proportional", {"proximityMode": "count"})):
            for k in range(K):
                j = condition(SETUP_MAIN, c, f,
                              _k("enc", SETUP_MAIN["name"], c + "_count", f) + f"|p{k}",
                              perm=k)
                j["req"] = dict(j.get("req", {}), **over)
                jobs.append(j)
    return {"out": "results/encoding.jsonl", "par": 8, "wall_kill": NO_WALL_KILL,
            "checkpoint_s": 600, "K": K, "jobs": jobs}


def fleet_stretch():
    """The two sizes above the ladder, run only if Phase 2 clears early."""
    return _sweep(SETUP_MAIN, (2.25, 2.5), "results/fleet.jsonl", "fleet")


def fleet_default():
    """The five principles at the dashboard's default setup, three fleet sizes.

    Only needed when SETUP_MAIN is not the default: it is the one sentence in the
    paper that says what the default does, so the reader can place the chosen setup.
    """
    return _sweep(SETUP_DEFAULT, (0.5, 1.0, 1.5), "results/fleet_default.jsonl",
                  "fdef", conditions=PRINCIPLES)


# Session 5, Experiment 5: the exact (decibel) encodings of the two objective principles,
# run on SETUP_MAIN as their own conditions beside the ladder's count forms. The
# overrides equal the payload defaults and are sent anyway, so every row names its form.
DB_FORMS = {"utilitarian_db": ("utilitarian", {"utilNoiseMode": True}),
            "proportional_db": ("proportional", {"proximityMode": "noise"})}


def fleet_db(K=K_PERM):
    """Experiment 5: Utilitarian and Proportional in decibel form, on the ladder.

    Same setup, same keys scheme and same permutation seeds as the count-form ladder, so
    ordering k here is paired with ordering k there: the form comparison is per ordering.

    Lane 1 (N = 6, 8) must finish and runs first, small N first. Lane 2 (N = 14 ... 24)
    fills slots as lane 1 frees them and runs until the single harvest (harvest.py). It is
    ordering-major -- p0 at every N before p1 at any -- because with eight slots and cells
    that may not prove before the harvest, an N-major queue would leave N >= 16 with no
    incumbent at all (DECISIONS D30). Within each ordering it is still small N first.

    Heartbeats every 60 s rather than 600, so harvest.py sees each cell's phase fresh.
    """
    conds = tuple(DB_FORMS)
    jobs = []

    def add(f, c, k):
        j = condition(SETUP_MAIN, c, f, _k("fleet_db", SETUP_MAIN["name"], c, f) + f"|p{k}",
                      perm=k)
        j["timeout_ms"] = UNLIMITED_MS
        jobs.append(j)

    for f in (0.25, 0.5):
        for c in conds:
            for k in range(K):
                add(f, c, k)
    for k in range(K):
        for f in (0.75, 1.0, 1.25, 1.5):
            for c in conds:
                add(f, c, k)
    return {"out": "results/fleet_db.jsonl", "par": 8, "wall_kill": NO_WALL_KILL,
            "checkpoint_s": 60, "setup": SETUP_MAIN, "K": K, "jobs": jobs}


PLANS = {"fleet_db": fleet_db,
         "scaling": scaling, "ablation": ablation, "caps": caps,
         "prior_sets": prior_sets, "reps": reps, "grid4": grid4,
         "binding": binding, "longbudget": longbudget,
         "budgetfix": budgetfix, "propranking": propranking,
         "pilot": pilot, "fleet": fleet, "fleet_a": fleet_a, "fleet_b": fleet_b,
         "fleet_stretch": fleet_stretch, "fleet_default": fleet_default,
         "screen": screen, "slack_sweep": slack_sweep, "slack_probe": slack_probe,
         "cap_sweep": cap_sweep, "perm_sweep": perm_sweep,
         "screen3": screen3, "encoding_screen": encoding_screen}

if __name__ == "__main__":
    name = sys.argv[1]
    plan = PLANS[name]()
    path = os.path.join(HERE, "plans", f"{name}.json")
    json.dump(plan, open(path, "w"), indent=1)
    print(f"{name}: {len(plan['jobs'])} jobs -> {path}")
