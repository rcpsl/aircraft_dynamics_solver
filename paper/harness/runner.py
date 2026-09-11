"""Parallel job scheduler for the paper's solver experiments.

One OS process per solve: Z3's context is process-global, so in-process threads
cannot run two solves at once. Results append to a jsonl; completed keys are skipped
on restart, so a run can be stopped and resumed.

Two independent limits, deliberately:
  timeoutMs   Z3's own budget. Exceeding it is a real data point (this principle is
              intractable at this size), not a crash, and production reacts to it by
              serving phase 1's unweighted route -- which the worker records.
  wall_kill   a hard process kill, set above timeoutMs. Only fires when Z3 ignores
              its own budget (it can, inside a long simplex call), which would
              otherwise let one job hold a slot for hours.

usage: python runner.py <plan.json>
  plan: {"out": "results/x.jsonl", "par": 8, "wall_kill": 900, "jobs": [ {...} ]}
"""
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))

# Statuses that mean "this job produced no answer", so a resumed plan re-runs them.
UNANSWERED = {"NO_OUTPUT", "phase1_timeout", "phase1_stopped"}


def main(plan_path):
    plan = json.load(open(plan_path))
    out_path = os.path.join(HERE, plan["out"])
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    par = int(plan.get("par", 8))
    wall_kill = float(plan.get("wall_kill", 1200))

    done = set()
    if os.path.exists(out_path):
        for line in open(out_path, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            # These three carry NO answer and must never count as done, or restarting
            # the plan would silently drop those jobs:
            #   NO_OUTPUT       the worker was killed before writing anything
            #   phase1_timeout  feasibility was never decided
            #   phase1_stopped  a stop landed during phase 1, so likewise
            # Everything else IS an answer and is kept, including phase1_noise_cap /
            # _unreachable / _structural (proven infeasible, derived without search)
            # and a phase-2 stop, which leaves a verified feasible routing.
            if str(r.get("status", "")) not in UNANSWERED:
                done.add(r["key"])

    jobs = [j for j in plan["jobs"] if j["key"] not in done]
    print(f"{len(plan['jobs'])} jobs, {len(done)} already done, {len(jobs)} to run, par={par}",
          flush=True)

    running = []          # (proc, job, outfile, jobfile, t0)
    out_f = open(out_path, "a", encoding="utf-8")
    t_start = time.time()
    queue = list(jobs)
    completed = 0

    def reap(p):
        nonlocal completed
        proc, job, outfile, jobfile, t0 = p
        try:
            rec = json.load(open(outfile, encoding="utf-8"))
        except Exception:
            rec = {"key": job["key"], "cfg": job.get("cfg"),
                   "status": "NO_OUTPUT", "wall": round(time.time() - t0, 1)}
        rec["runner_wall"] = round(time.time() - t0, 1)
        out_f.write(json.dumps(rec) + "\n")
        out_f.flush()
        completed += 1
        print(f"[{completed}/{len(jobs)}] {rec['status']:<28} "
              f"{rec['runner_wall']:>7.1f}s  {job['key']}", flush=True)
        for f in (outfile, jobfile):
            try:
                os.unlink(f)
            except OSError:
                pass

    while queue or running:
        while queue and len(running) < par:
            job = queue.pop(0)
            # Contention is a property of the sweep, not of the job definition, so it
            # is stamped on here and travels out on the result row (worker: runner_par).
            job = dict(job, runner_par=par)
            if "checkpoint_s" not in job and plan.get("checkpoint_s"):
                job["checkpoint_s"] = plan["checkpoint_s"]
            jf = tempfile.NamedTemporaryFile("w", suffix=".job.json", delete=False,
                                             encoding="utf-8")
            json.dump(job, jf)
            jf.close()
            of = jf.name.replace(".job.json", ".out.json")
            proc = subprocess.Popen([sys.executable, os.path.join(HERE, "worker.py"),
                                     jf.name, of],
                                    cwd=HERE, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            running.append((proc, job, of, jf.name, time.time()))

        time.sleep(1.0)
        still = []
        for p in running:
            proc, job, outfile, jobfile, t0 = p
            if proc.poll() is not None:
                reap(p)
            elif time.time() - t0 > wall_kill:
                proc.kill()
                proc.wait()
                reap(p)
            else:
                still.append(p)
        running = still

    out_f.close()
    print(f"DONE in {time.time()-t_start:.0f}s -> {out_path}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
