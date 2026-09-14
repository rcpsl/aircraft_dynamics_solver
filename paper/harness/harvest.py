"""Harvest every unfinished cell of a sweep at ONE wall-clock horizon.

Z3 keeps no resumable state, so a stop is final: the salvage path returns the incumbent,
replayed against every hard constraint, and the search is gone. That is why the harvest
is a single, pre-announced moment and not a series of peeks.

Order matters, and each step exists because skipping it once cost an answer:
  1. HOLD        the runner stops launching (runner.held). A job launched after this
                 point could take the interrupt in phase 1 and return nothing (D12).
  2. wait        every running cell's heartbeat, written after HOLD, must report phase 2.
                 Phase 1 takes at most 12 s on this ladder, so this is quick.
  3. STOP_ALL    one interrupt per worker; each salvages and writes its row.
  4. wait        until no heartbeat file remains and the runner has exited.
  5. clean up    remove STOP_ALL and HOLD, so the next launch is not poisoned.

usage: python harvest.py <UTC time, e.g. 2026-09-15T00:00:00> <runner log path>
"""
import datetime as dt
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CK = os.path.join(HERE, "results", "checkpoints")


def log(msg):
    print(f"{dt.datetime.utcnow():%Y-%m-%dT%H:%M:%SZ}  {msg}", flush=True)


def heartbeats():
    out = {}
    for p in glob.glob(os.path.join(CK, "*.json")):
        try:
            out[p] = json.load(open(p, encoding="utf-8"))
        except Exception:
            out[p] = None
    return out


def runner_done(log_path):
    try:
        s = open(log_path, encoding="utf-8").read()
    except OSError:
        return False
    return "DONE in" in s or "not launched" in s


def main(when, log_path):
    t_h = dt.datetime.fromisoformat(when)
    log(f"harvest horizon {t_h:%Y-%m-%dT%H:%M:%SZ}; waiting")
    while dt.datetime.utcnow() < t_h:
        if runner_done(log_path):
            log("runner finished before the horizon; nothing to harvest")
            return 0
        time.sleep(30)

    open(os.path.join(CK, "HOLD"), "w").close()
    hold_at = time.time()
    log("HOLD placed; runner launches nothing from here")

    deadline = hold_at + 1800
    while True:
        time.sleep(15)
        if time.time() - hold_at < 120:
            continue
        hb = heartbeats()
        stale = [os.path.basename(p) for p, r in hb.items()
                 if r is None or r.get("elapsed_s", 0) < 60]
        phase1 = [os.path.basename(p) for p, r in hb.items()
                  if r and (r.get("progress") or {}).get("phase") != "phase2"]
        if not stale and not phase1:
            log(f"{len(hb)} running cell(s), all in phase 2")
            break
        if time.time() > deadline:
            log(f"still not all in phase 2 after 30 min: stale={stale} phase1={phase1}; "
                "harvesting anyway")
            break

    open(os.path.join(CK, "STOP_ALL"), "w").close()
    log("STOP_ALL placed")
    while heartbeats() or not runner_done(log_path):
        time.sleep(10)
    log("every worker returned and the runner exited")
    for s in ("STOP_ALL", "HOLD"):
        try:
            os.unlink(os.path.join(CK, s))
        except OSError:
            pass
    log("sentinels removed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
