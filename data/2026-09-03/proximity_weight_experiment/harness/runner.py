"""Parallel job scheduler for the weight-scheme sweeps.

One OS process per solve (Z3's context is process-global, so in-process threads
cannot run two solves at once). Results append to a jsonl; completed keys are
skipped on restart, so a run can be stopped and resumed.

Two independent limits, on purpose:
  timeout_ms  Z3's own budget. Exceeding it returns phase2_timeout -- a real
              data point (the scheme is intractable at this size), not a crash.
  wall_kill   a hard process kill, set above timeout_ms. Only fires if Z3
              ignores its budget (it can, inside a long simplex call), which
              would otherwise let one job hold a slot for hours.

usage: python runner.py <plan.json>
  plan: {"out": "...jsonl", "par": 12, "jobs": [ {...}, ... ]}
"""
import json, os, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))


def key(j):
    # w_prox is appended only when it is not the default 1.0, so keys written
    # before that dial existed still match and stay resumable.
    wp = float(j.get("w_prox", 1.0))
    tail = "" if wp == 1.0 else f"|wp{wp:g}"
    if "D" in j:
        tail += f"|D{float(j['D']):g}"
    # Only scalars go in the key: a payload override can carry whole
    # startPositions/multipliers lists, and embedding those would make the key
    # unreadable and unstable. Non-scalars contribute their name alone, so such a
    # job must also carry a scalar flag (e.g. split=True) if two variants of it
    # need to be told apart.
    for k, v in sorted(j.get("req", {}).items()):
        tail += f"|{k}={v}" if isinstance(v, (int, float, bool, str)) else f"|{k}"
    return (f"{j['scheme']}|{'-'.join(j['order'])}|{'P' if j['pop'] else 'NOPOP'}"
            f"|T{j['T_max']}{tail}")


def main(plan_path):
    plan = json.load(open(plan_path))
    out_path = os.path.join(HERE, plan["out"])
    par = plan.get("par", 12)
    done = set()
    if os.path.exists(out_path):
        for line in open(out_path):
            try:
                r = json.loads(line)
                if not r["status"].startswith("NO_OUTPUT"):
                    done.add(r["key"])
            except Exception:
                pass
    jobs = [j for j in plan["jobs"] if key(j) not in done]
    print(f"[runner] {len(plan['jobs'])} jobs, {len(done)} already done, {len(jobs)} to run, par={par}",
          flush=True)

    running = []   # (proc, job, jf, of, t0)
    t_start = time.time()
    finished = 0
    while jobs or running:
        while jobs and len(running) < par:
            j = jobs.pop(0)
            jf = tempfile.mktemp(suffix=".job.json")
            of = tempfile.mktemp(suffix=".out.json")
            json.dump(j, open(jf, "w"))
            p = subprocess.Popen([sys.executable, os.path.join(HERE, "worker.py"), jf, of],
                                 cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            running.append([p, j, jf, of, time.monotonic()])
            print(f"[start] {key(j)}", flush=True)
        time.sleep(2)
        for slot in running[:]:
            p, j, jf, of, t0 = slot
            el = time.monotonic() - t0
            killed = False
            if p.poll() is None:
                if el > j.get("wall_kill", 2400):
                    p.kill()
                    killed = True
                else:
                    continue
            p.wait()
            # The payload overrides are recorded too. Without them a saved row cannot
            # be reproduced -- a reduced-demand or split-stream run looks identical to
            # a full-demand one, and a checker comparing against the default payload
            # silently compares the wrong thing.
            rec = {"key": key(j), "scheme": j["scheme"], "order": j["order"], "pop": j["pop"],
                   "T_max": j["T_max"], "elapsed": round(el, 1)}
            if "req" in j:
                rec["req"] = j["req"]
            if "D" in j:
                rec["D"] = j["D"]
            if "w_prox" in j:
                rec["w_prox"] = j["w_prox"]
            if killed:
                rec["status"] = "WALL_KILL"
            elif os.path.exists(of):
                rec.update(json.load(open(of)))
            else:
                # A worker killed from OUTSIDE (stopping the runner, a reboot) lands
                # here too, and such a row would otherwise be replayed as "done" on
                # the next resume and silently drop that job from the sweep. Tagged
                # so it can be purged; see the NO_OUTPUT filter in report.py.
                err = (p.stderr.read() or b"").decode(errors="replace")[-300:]
                rec["status"] = f"NO_OUTPUT rc={p.returncode}"
                rec["detail"] = err
            with open(out_path, "a") as f:
                f.write(json.dumps(rec) + "\n")
            finished += 1
            print(f"[done ] {rec['key']:58} {rec['status']:16} {rec['elapsed']:7.0f}s "
                  f"tier={rec.get('tier')} peak={rec.get('peak')} "
                  f"({finished} done, {len(jobs)} queued, {int(time.time()-t_start)}s elapsed)",
                  flush=True)
            for f_ in (jf, of):
                try:
                    os.remove(f_)
                except OSError:
                    pass
            running.remove(slot)
    print(f"[runner] all done in {int(time.time()-t_start)}s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
