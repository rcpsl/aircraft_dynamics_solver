"""Re-run every solve that never reached a usable verdict, with a long budget.

The 600 s production budget exists so a workshop is not left waiting; it is not a
property of the problem, and a row that hit it tells us about the clock rather than
about the principle. This scans the recorded results for such rows and rebuilds them
with a four-hour budget.

Rescued statuses:
  phase2_failed_timeout  Z3 found no incumbent at all -- the served route ignores the
                         principle, so the row is not a datum about it.
  phase1_timeout         even feasibility was not settled.
  NO_OUTPUT              the runner killed the worker on wall_kill.
  worker_error           a crash worth seeing again.

A row that came back `partial` is NOT rescued by default: it has the objective applied
and is verified feasible, so it is a real answer. Pass --partials to include those too,
which is what turns an unproven comparison into a proven one.

usage: python rescue.py [--partials] [--hours H]      writes plans/rescue.json
"""
import glob
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BAD_PREFIXES = ("phase2_failed", "phase1_timeout", "NO_OUTPUT", "worker_error")


def main():
    hours = 4.0
    include_partial = "--partials" in sys.argv
    if "--hours" in sys.argv:
        hours = float(sys.argv[sys.argv.index("--hours") + 1])

    # Recover the original job definitions: results rows carry `cfg` but not the
    # free-form `req` overrides, which live only in the plan that produced them.
    plans = {}
    for p in glob.glob(os.path.join(HERE, "plans", "*.json")):
        if os.path.basename(p) == "rescue.json":
            continue
        try:
            for j in json.load(open(p, encoding="utf-8"))["jobs"]:
                plans[j["key"]] = j
        except Exception:
            pass

    jobs, seen, reasons = [], set(), {}
    for f in sorted(glob.glob(os.path.join(HERE, "results", "*.jsonl"))):
        if os.path.basename(f) == "rescue.jsonl":
            continue
        for line in io.open(f, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            st = str(r.get("status", ""))
            bad = st.startswith(BAD_PREFIXES)
            if include_partial and r.get("optimality") == "partial":
                bad = True
            if not bad or r["key"] in seen:
                continue
            src = plans.get(r["key"])
            if src is None:
                continue
            seen.add(r["key"])
            reasons[r["key"]] = st if st.startswith(BAD_PREFIXES) else "partial"
            job = dict(src)
            job["key"] = "rescue|" + r["key"]
            job["timeout_ms"] = int(hours * 3600 * 1000)
            jobs.append(job)

    out = {"out": "results/rescue.jsonl", "par": 6,
           "wall_kill": hours * 3600 + 1200, "jobs": jobs}
    path = os.path.join(HERE, "plans", "rescue.json")
    json.dump(out, open(path, "w"), indent=1)
    print(f"{len(jobs)} job(s) to rescue at {hours} h each -> {path}")
    for k in sorted(reasons):
        print(f"   {reasons[k]:24s} {k}")


if __name__ == "__main__":
    main()
