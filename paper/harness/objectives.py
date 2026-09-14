"""Each principle's own objective, evaluated on ANY condition's routing.

The solver reports the objective it optimised -- `protectedNoise` on a Prioritarian row,
`totalTransit` on a Utilitarian one, `proximityCost` on a Proportional one -- and reports
nothing at all on the baseline, which optimises none of them. That makes the one
comparison a reader most wants impossible from the stored fields alone: *how does the
baseline score on the thing this principle was trying to minimise?*

So the three objectives are re-derived here from `noiseMatrix`, `paths` and
`countMatrix`, which every row carries. Re-deriving an objective is exactly the kind of
step that quietly gets the definition wrong, so `main()` checks each reconstruction
against the solver's own reported value on every row that has one, and the page
generator refuses to use a reconstruction that does not reproduce it.

Definitions, read off solver_server_dB.optimize_objectives:

  protected noise   sum over the protected stations and ALL timesteps of the added dB.
                    A sum, not a peak -- metrics.py's `protected_peak` is a different
                    quantity and is not this objective.
  transit time      aircraft-timesteps between an aircraft's first move and its
                    arrival, summed over the fleet. Reported by the solver x100
                    (the aircraft multiplier scale).
  proximity cost    sum over tiles and timesteps of the occupancy count times that
                    tile's proximity weight, the weights rounded to hundredths the way
                    the integer encoding rounds them.

usage: python objectives.py        # reconstruction self-test against the solver
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RES = os.path.join(HERE, "results")
ROWS = os.path.join(RES, "fleet_main.jsonl")

# (key, label, units, "lower is better"). Equal and Sufficientarian are absent on
# purpose: their principle is a hard cap, not an objective, and there is no score to
# reconstruct -- what stands in for one is whether the cap binds.
OBJECTIVES = {
    "prioritarian": ("protected_noise", "protected-set noise", "dB, summed"),
    "utilitarian":  ("transit_time",    "fleet transit time",  "aircraft-timesteps"),
    "proportional": ("proximity_cost",  "proximity cost",      "weighted occupancy"),
}


def protected_noise(row, req, prot=None):
    """Sum of added dB over the protected stations, every timestep."""
    prot = prot or req.get("protectedStations") or []
    if not prot:
        return None
    nm = row["noiseMatrix"]
    T = len(nm[0])
    return round(sum(nm[p - 1][t] for p in prot for t in range(T)), 4)


def transit_time(row, req=None):
    """Aircraft-timesteps in transit: first move through arrival, summed over the fleet.

    An aircraft that never moves contributes nothing, which is the solver's rule too --
    `hm` is false until the location changes, and the transit indicator is gated on it.
    """
    tot = 0
    for p in row["paths"]:
        T = len(p)
        end = p[-1]
        mv = next((t for t in range(1, T) if p[t] != p[t - 1]), None)
        if mv is None:
            continue
        arr = T - 1
        while arr > 0 and p[arr - 1] == end:
            arr -= 1
        tot += max(0, arr - mv + 1)
    return tot


def proximity_cost(row, req):
    """Occupancy priced by the proximity weights, in the integer units the solver uses."""
    pw = req.get("proximityWeights")
    if not pw:
        return None
    ipw = [round(w * 100) for w in pw]
    cm = row["countMatrix"]
    T = len(cm[0])
    return round(sum(cm[m][t] * ipw[m] for m in range(len(cm)) for t in range(T)) / 100.0,
                 4)


def evaluate(row, req, prot=None, weights=None):
    """All three objectives on one routing, whichever condition produced it.

    `prot` and `weights` are passed in for conditions whose own request carries neither
    -- the baseline has no protected set, but the question is what the baseline does to
    Prioritarian's protected set, so the set has to come from Prioritarian's request.
    """
    r = dict(req)
    if prot and not r.get("protectedStations"):
        r["protectedStations"] = list(prot)
    if weights and not r.get("proximityWeights"):
        r["proximityWeights"] = list(weights)
    return {"protected_noise": protected_noise(row, r),
            "transit_time": transit_time(row),
            "proximity_cost": proximity_cost(row, r)}


def _rows():
    return [json.loads(l) for l in io.open(ROWS, encoding="utf-8")]


def reference(rows=None):
    """The protected set and proximity weights the study's own conditions were run with.

    Taken from the requests on disk rather than re-derived from plans.py: if the two
    ever disagreed, the figure would be drawn for a set the solver never saw.
    """
    import metrics as MX
    prot = weights = None
    for x in rows if rows is not None else _rows():
        req = MX._req_for(x)
        if prot is None and req.get("protectedStations"):
            prot = list(req["protectedStations"])
        if weights is None and req.get("proximityWeights"):
            weights = list(req["proximityWeights"])
        if prot and weights:
            break
    return prot, weights


def main():
    """Reproduce every objective the solver reported. Any mismatch fails the run."""
    import metrics as MX
    rows = _rows()
    checks = [("protectedNoise", "protected_noise", 1.0, 0.02),
              ("totalTransit",   "transit_time",    100.0, 1e-6),
              ("proximityCost",  "proximity_cost",  1.0, 1e-6)]
    fails = 0
    for field, key, scale, tol in checks:
        seen = bad = 0
        for x in rows:
            v = x.get(field)
            if v is None:
                continue
            seen += 1
            got = evaluate(x, MX._req_for(x))[key]
            if got is None or abs(got * scale - v) > tol:
                bad += 1
                if bad == 1:
                    print(f"  first mismatch: N={x['N']} perm={x['perm']} "
                          f"reported={v} rebuilt={got}")
        fails += bool(bad)
        print(f"  {'FAIL' if bad else 'ok  '}  {field}: {seen - bad}/{seen} reproduced")
    prot, weights = reference(rows)
    print(f"\nprotected set {prot}, {len(weights or [])} proximity weights")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
