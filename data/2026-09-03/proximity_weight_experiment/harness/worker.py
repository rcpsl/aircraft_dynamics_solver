"""Run ONE solve in its own process and print a JSON result line.

Calls the solver's two phases directly instead of going through Flask: the
scheduler needs many concurrent solves and one Flask process can only run one
(_solve_lock), so HTTP would mean managing a port pool for no benefit. The call
sequence below mirrors _solve_impl's soft-T path exactly -- find_min_T, then
optimize_objectives at T_for_phase2 = T_max -- and validate.py checks it
reproduces sweep.jsonl's saved routings before any of it is trusted.

usage: python worker.py <job.json> <out.json>
"""
import importlib.util as iu
import json, sys, time

SOLVER = r"d:/Documents/EECS_199_Shoukry/proximity_noise_experiment/solver_server_dB_noise.py"


def load_solver():
    spec = iu.spec_from_file_location("S", SOLVER)
    S = iu.module_from_spec(spec)
    spec.loader.exec_module(S)
    return S


def run(job):
    import schemes as sc
    S = load_solver()
    order, pop = job["order"], job["pop"]
    pw, extra = sc.build(job["scheme"], order, pop)

    req = sc.mk.build(order=tuple(order), T_max=job["T_max"], **extra)
    req["proximityWeights"] = pw
    # Optional second dial, off by default so jobs written before it existed behave
    # identically: how loudly the proximity term speaks against the soft-T penalty.
    req["weightProximity"] = float(job.get("w_prox", req["weightProximity"]))
    # D is a payload field too. Proportional sends D=30 while the loudest
    # reachable tile on this map is +12.30 dB, so the cap is vacuous and every
    # objective If-chain runs its full 16 branches. Tightening it is the only
    # payload-only lever on chain length, hence worth timing.
    req["D"] = float(job.get("D", req["D"]))
    # Free-form payload overrides, so tractability levers that are ordinary request
    # fields (weightTime, hardT) can be timed without another worker flag each.
    req.update(job.get("req", {}))
    hard_T = bool(req.get("hardT", False))
    S._set_timeout(job["timeout_ms"])

    t0 = time.monotonic()
    r1 = S.find_min_T(req["N"], req["M"], req["D"], req["U"], req["adjacency"],
                      req["startPositions"], req["endPositions"], req["baseline"],
                      req["aircraftDB"], multipliers=req["aircraftMultipliers"])
    t_p1 = time.monotonic() - t0
    if r1["status"] != "sat":
        return {"status": "phase1_" + r1["status"], "wall": round(time.monotonic() - t0, 1)}
    if job["T_max"] < r1["T"]:
        return {"status": "T_max_too_small", "T_min": r1["T"]}

    # Hard T fixes phase 2 at phase 1's minimum and drops the soft-T penalty and
    # the sticky-arrival constraints, exactly as _solve_impl does.
    T2 = r1["T"] if hard_T else job["T_max"]
    r2 = S.optimize_objectives(
        req["N"], T2, req["M"], req["D"], req["U"], req["adjacency"],
        req["startPositions"], req["endPositions"],
        req["optimizeUtilitarian"], req["optimizePrioritarian"], req["optimizeProximity"],
        [], pw,
        req["weightUtilitarian"], req["weightPrioritarian"], req["weightProximity"],
        not hard_T, req["weightTime"],
        None, req["utilNoiseMode"], req["aircraftMultipliers"],
        req["baseline"], req["aircraftDB"],
        proximity_mode=extra.get("proximityMode", "noise"),
        proximity_noise_ref=extra.get("proximityNoiseRef"),
    )
    wall = time.monotonic() - t0
    if r2["status"] != "sat":
        return {"status": "phase2_" + r2.get("reason", "failed"), "wall": round(wall, 1),
                "phase1_wall": round(t_p1, 1)}

    cnt, _ = S._active_output_matrices(
        r2["paths"], req["startPositions"], req["endPositions"], req["N"], 25,
        T2, req["baseline"], req["aircraftDB"],
        multipliers=req["aircraftMultipliers"])
    occ = [sum(cnt[m]) for m in range(25)]
    tier = {str(b): sum(occ[m] for m in range(25) if req["baseline"][m] == b) for b in (45, 55, 65)}
    peak = round(max((max(r) for r in r2["noiseMatrix"]), default=0.0), 3)
    # Score the routing under the OTHER pricings too, so schemes can be compared on a
    # common yardstick instead of each on its own (incomparably normalized) objective.
    occ_cost = sum(occ[m] * pw[m] for m in range(25))
    w0 = sc.weights_for(order, pop)
    occ_cost_w0 = sum(occ[m] * w0[m] for m in range(25))
    return {"status": "sat", "wall": round(wall, 1), "phase1_wall": round(t_p1, 1),
            "T": r2["T_used"], "T_min": r1["T"], "occ": occ, "tier": tier, "peak": peak,
            "prox": r2.get("proximityCost"), "occCost": round(occ_cost, 2),
            "occCostW0": round(occ_cost_w0, 2),
            "paths": r2["paths"]}


if __name__ == "__main__":
    job = json.load(open(sys.argv[1]))
    try:
        out = run(job)
    except Exception as e:
        out = {"status": "EXC " + type(e).__name__, "detail": str(e)[:300]}
    json.dump(out, open(sys.argv[2], "w"))
