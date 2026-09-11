"""Run ONE solve in its own process and write a JSON result line.

Calls the PRODUCTION solver's two phases directly rather than going through Flask.
Z3's Context is process-global and solver_server_dB serializes every solve behind
_solve_lock, so one Flask process can only ever run one solve; the paper needs many
in parallel, and a port pool would buy nothing that a process per job does not.

The call sequence mirrors _solve_impl's soft-T path exactly:
    find_min_T  ->  optimize_objectives at T_for_phase2 = T_max
including the dashboard's T_max_too_small retry (dashboard :1032), which raises
T_max to the solver's true minimum plus the same slack and tries once more.

usage: python worker.py <job.json> <out.json>
"""
import importlib.util as iu
import json
import math
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SOLVER = os.path.join(os.path.dirname(HERE), "..", "solver_server_dB.py")
SOLVER = os.path.abspath(SOLVER)
CHECKPOINTS = os.path.join(HERE, "results", "checkpoints")


def load_solver():
    spec = iu.spec_from_file_location("SOLVER_DB", SOLVER)
    S = iu.module_from_spec(spec)
    spec.loader.exec_module(S)
    return S


class Checkpointer(threading.Thread):
    """Heartbeat for a solve that may run for days, plus a way to stop one safely.

    Two jobs, and they are separate on purpose.

    HEARTBEAT. Every `period` seconds this writes results/checkpoints/<key>.json:
    elapsed wall time, which phase is running, and the solver's own progress dict.
    That is a known lower bound on effort for a cell that is still going when the
    next session starts, and it is written without touching Z3 at all.

    STOP. The incumbent itself is NOT read from here. Z3's context is process-global
    and, as solver_server_dB says at its _solve_lock, reading it from a second thread
    while check() is running corrupts the AST state. The one cross-thread call Z3
    documents as safe is interrupt(), and the solver is already built around it: an
    interrupted phase-2 check returns unknown, which sends the solver down its own
    _best_so_far path, where the incumbent is salvaged AND replayed against every
    hard constraint by _model_is_feasible before it is returned. So to capture an
    incumbent, this thread drops one interrupt and lets the production salvage path
    produce it -- a verified feasible routing, recorded as `partial` like any other
    unproven answer, rather than an unverified model scraped out from under a
    running search.

    Stopping is requested by creating either file:
        results/checkpoints/<key>.STOP     one job
        results/checkpoints/STOP_ALL       every job now running
    Exactly one interrupt is delivered, and only while Z3 is inside a check, because
    an interrupt landing between checks stays on the context and would kill the
    salvage replay instead (solver_server_dB._drain_interrupt).
    """

    def __init__(self, S, key, period=600.0):
        super().__init__(daemon=True)
        self.S = S
        self.key = str(key)
        self.period = period
        self.t0 = time.monotonic()
        self.stop_evt = threading.Event()
        self.interrupted = False
        self.stop_reason = None
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in self.key)
        os.makedirs(CHECKPOINTS, exist_ok=True)
        self.path = os.path.join(CHECKPOINTS, safe + ".json")
        self.stop_file = os.path.join(CHECKPOINTS, safe + ".STOP")
        self.stop_all = os.path.join(CHECKPOINTS, "STOP_ALL")

    def _snapshot(self):
        try:
            with self.S._progress_lock:
                return dict(self.S._progress)
        except Exception:
            return {}

    def write(self, **extra):
        rec = {"key": self.key, "pid": os.getpid(),
               "elapsed_s": round(time.monotonic() - self.t0, 1),
               "wrote_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "progress": self._snapshot()}
        rec.update(extra)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=1)
        os.replace(tmp, self.path)

    def _requested(self):
        for p in (self.stop_file, self.stop_all):
            if os.path.exists(p):
                return os.path.basename(p)
        return None

    def _interrupt_once(self):
        # Only while a check is actually in flight: see the class docstring.
        for _ in range(600):
            if self.stop_evt.is_set():
                return
            try:
                in_check = self.S._in_check
            except Exception:
                in_check = True
            if in_check:
                try:
                    self.S.main_ctx().interrupt()
                    self.interrupted = True
                except Exception:
                    pass
                return
            time.sleep(0.5)

    def run(self):
        last = 0.0
        while not self.stop_evt.wait(2.0):
            why = self._requested()
            if why and not self.interrupted:
                self.stop_reason = why
                self.write(stop_requested=why)
                self._interrupt_once()
                continue
            now = time.monotonic() - self.t0
            if now - last >= self.period:
                last = now
                try:
                    self.write()
                except OSError:
                    pass

    def finish(self):
        self.stop_evt.set()
        try:
            os.unlink(self.path)
        except OSError:
            pass


def _energy_add(base, levels):
    """Combine a baseline and a list of added-noise contributions in energy space."""
    tot = 10 ** (base / 10)
    for L in levels:
        tot += 10 ** (L / 10)
    return 10 * math.log10(tot)


def _matrices(res):
    """The two matrices the solver returns and the older rows dropped.

    analyze.py can rebuild occupancy from `paths`, but only over the active-noise
    window it re-derives itself; countMatrix and noiseMatrix are what the solver
    actually constrained. Storing them lets metrics.py be checked against the
    solver rather than against a second implementation of the same window, and
    they are the only source for per-timestep noise, which `paths` alone cannot
    give without redoing the dB arithmetic.
    """
    out = {}
    for k in ("countMatrix", "noiseMatrix"):
        v = res.get(k)
        if v is not None:
            out[k] = v
    return out


def derive_metrics(res, req):
    """Metrics the solver does not report but the paper needs.

    All are read off the returned noiseMatrix / countMatrix / paths, which
    _active_output_matrices builds from the same active-noise window Z3 constrained,
    so nothing here re-models the physics.
    """
    noise = res.get("noiseMatrix") or []
    counts = res.get("countMatrix") or []
    paths = res.get("paths") or []
    M = req["M"]
    T = res.get("T", len(noise[0]) if noise else 0)

    # Per-station worst added dB over the horizon: the quantity D caps, and the one
    # the dashboard shows as a community's "added noise".
    per_station_peak = [max(row) if row else 0.0 for row in noise]
    peak = max(per_station_peak) if per_station_peak else 0.0

    # Per-timestep spread, which is what U caps (max - min across stations at one t).
    spread_by_t = [max(noise[m][t] for m in range(M)) - min(noise[m][t] for m in range(M))
                   for t in range(T)] if noise else []
    peak_spread = max(spread_by_t) if spread_by_t else 0.0

    # Total exposure: sum of added dB over every station-timestep. This is exactly
    # the quantity the Utilitarian objective minimizes (unweighted variant).
    total_added = sum(sum(row) for row in noise)

    # Aircraft-timesteps aloft, and trip length in hops, read off the paths rather
    # than from totalTransit (whose units are raw-scaled; see the UNITS WARNING in
    # optimize_objectives).
    trips = []
    for i, p in enumerate(paths):
        s0, e0 = req["startPositions"][i], req["endPositions"][i]
        if s0 == e0:
            trips.append(0)
            continue
        t_fm = next((t for t in range(len(p)) if p[t] != s0), None)
        if t_fm is None:
            trips.append(0)
            continue
        t_arr = next((t for t in range(len(p)) if p[t] == e0), len(p) - 1)
        trips.append(t_arr - t_fm + 1)

    # Shortest-path floor, for "how much longer than necessary".
    adj = req["adjacency"]
    floors = []
    for i in range(len(paths)):
        floors.append(_bfs(adj, req["startPositions"][i], req["endPositions"][i], M))

    occupied = sum(1 for m in range(M) if per_station_peak[m] > 0)

    return {
        "peakAddedDB": round(peak, 4),
        "peakSpreadDB": round(peak_spread, 4),
        "totalAddedDB": round(total_added, 4),
        "perStationPeakDB": [round(v, 4) for v in per_station_peak],
        "stationsTouched": occupied,
        "tripHops": trips,
        "tripFloorHops": floors,
        "totalTripHops": sum(trips),
        "totalFloorHops": sum(f for f in floors if f != float('inf')),
        "maxCount": max((max(r) for r in counts), default=0),
    }


def _bfs(adj, src, dst, M):
    from collections import deque
    if src == dst:
        return 0
    seen = [False] * (M + 1)
    seen[src] = True
    q = deque([(src, 0)])
    while q:
        n, d = q.popleft()
        for nb in range(1, M + 1):
            if nb != n and adj[n - 1][nb - 1] == 1 and not seen[nb]:
                if nb == dst:
                    return d + 1
                seen[nb] = True
                q.append((nb, d + 1))
    return float('inf')


def run(job):
    sys.path.insert(0, HERE)
    import payload as P

    S = load_solver()
    req = P.build_request(**job["cfg"])
    req.update(job.get("req", {}))

    # The server clamps any requested budget to SOLVE_TIMEOUT_CAP_MS (30 min), because
    # a workshop must not be able to wedge its own solve lock for hours. That ceiling is
    # a user-experience decision, not a property of the problem, so for the paper it is
    # raised here when a job asks for more. The solver code under test is untouched;
    # only this module-level constant moves, and only in this worker process.
    want = int(job.get("timeout_ms", req.get("timeoutMs", 600000)))
    if want > S.SOLVE_TIMEOUT_CAP_MS:
        S.SOLVE_TIMEOUT_CAP_MS = want
    S._set_timeout(want)
    out_budget_s = want // 1000

    hard_T = bool(req.get("hardT", False))
    slack = req["T_max"] - P.chebyshev_t_lower(req["startPositions"], req["endPositions"])

    out = {"key": job["key"], "cfg": job["cfg"], "N": req["N"],
           "D": req["D"], "U": req["U"], "T_max_requested": req["T_max"],
           "budget_s": out_budget_s,
           # Solve times are only comparable within one sweep, and only at a stated
           # level of contention, so the parallelism the row was measured under
           # travels with the row rather than living in a plan file.
           "runner_par": job.get("runner_par"),
           "slack": slack,
           # The screen queues many setups into one file, and `cfg` only carries the
           # knobs that moved; the setup dict makes each row self-describing.
           "setup": job.get("setup"),
           "perm": job.get("perm"),
           "probe": job.get("probe", False)}

    ck = Checkpointer(S, job["key"], period=float(job.get("checkpoint_s", 600)))
    ck.start()

    t0 = time.monotonic()
    try:
        r1 = S.find_min_T(req["N"], req["M"], req["D"], req["U"], req["adjacency"],
                          req["startPositions"], req["endPositions"], req["baseline"],
                          req["aircraftDB"], multipliers=req["aircraftMultipliers"])
    finally:
        out["t_phase1"] = round(time.monotonic() - t0, 2)
        if ck.interrupted:
            out["stoppedEarly"] = ck.stop_reason
    if ck.interrupted:
        # An interrupt inside phase 1 cannot be salvaged: there is no incumbent to
        # verify, only an undecided feasibility question.
        ck.finish()
        out["status"] = "phase1_stopped"
        out["wall"] = round(time.monotonic() - t0, 2)
        return out

    if r1["status"] != "sat":
        ck.finish()
        out["status"] = "phase1_" + r1.get("reason", "unsat")
        out["detail"] = r1.get("detail", "")
        out["wall"] = round(time.monotonic() - t0, 2)
        return out

    out["T_min"] = r1["T"]

    # Dashboard :1032 — a T_max below the true minimum is retried, not failed.
    T_max = req["T_max"]
    if T_max < r1["T"]:
        out["T_max_retried"] = True
        T_max = r1["T"] + slack
    out["T_max_used"] = T_max

    should_opt = (req["optimizeUtilitarian"] or req["optimizePrioritarian"]
                  or req["optimizeProximity"] or not hard_T)
    if not should_opt:
        ck.finish()
        out["status"] = "sat_phase1_only"
        out["wall"] = round(time.monotonic() - t0, 2)
        out.update(derive_metrics(r1, req))
        out.update(_matrices(r1))
        return out

    T2 = r1["T"] if hard_T else T_max
    t1 = time.monotonic()
    try:
        r2 = S.optimize_objectives(
            req["N"], T2, req["M"], req["D"], req["U"], req["adjacency"],
            req["startPositions"], req["endPositions"],
            req["optimizeUtilitarian"], req["optimizePrioritarian"], req["optimizeProximity"],
            req.get("protectedStations", []), req.get("proximityWeights"),
            req["weightUtilitarian"], req["weightPrioritarian"], req["weightProximity"],
            not hard_T, req["weightTime"],
            req.get("stationTransitWeights"),
            req["utilNoiseMode"],
            req["aircraftMultipliers"],
            req["baseline"], req["aircraftDB"],
            proximity_mode=req.get("proximityMode", "noise"),
            proximity_noise_ref=req.get("proximityNoiseRef"),
        )
    except ValueError as e:
        ck.finish()
        out["status"] = "phase2_error"
        out["detail"] = str(e)
        out["t_phase2"] = round(time.monotonic() - t1, 2)
        out["wall"] = round(time.monotonic() - t0, 2)
        return out
    out["t_phase2"] = round(time.monotonic() - t1, 2)
    out["wall"] = round(time.monotonic() - t0, 2)
    if ck.interrupted:
        out["stoppedEarly"] = ck.stop_reason
    ck.finish()

    if r2["status"] == "phase2_failed":
        # Production falls back to phase 1's UNWEIGHTED route here. Record that
        # explicitly: such a run is not an answer to the fairness question asked.
        out["status"] = "phase2_failed_" + r2["reason"]
        out["fellBackToPhase1"] = True
        out.update(derive_metrics(r1, req))
        out.update(_matrices(r1))
        return out

    out["status"] = "sat"
    for k in ("optimality", "principleOptimized", "objectiveMode", "T_used",
              "totalUtilNoise", "totalTransit", "protectedNoise", "proximityCost",
              "proximityMode", "arrivalPenalty"):
        if k in r2:
            out[k] = r2[k]
    out.update(derive_metrics(r2, req))
    out.update(_matrices(r2))
    if job.get("keep_paths", True):
        out["paths"] = r2["paths"]
    return out


def main():
    job = json.load(open(sys.argv[1]))
    try:
        res = run(job)
    except Exception as e:
        import traceback
        res = {"key": job.get("key"), "cfg": job.get("cfg"), "status": "worker_error",
               "detail": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-2000:]}
    json.dump(res, open(sys.argv[2], "w"))


if __name__ == "__main__":
    main()
