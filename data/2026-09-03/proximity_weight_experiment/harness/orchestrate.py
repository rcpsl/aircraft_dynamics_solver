"""Run the remaining blocks strictly one at a time.

The shell version of this used `pgrep -f` to wait for the previous block. Git
Bash's pgrep does not see native Windows python processes, so every guard
returned "not running", all four blocks started at once, and two identical
surr_t6 runs wrote the same file. subprocess.run blocks properly; no guard
needed.

Order matters: the surrogate blocks run first and the Z3 timing block runs LAST
and ALONE, because its whole output is wall clock and background load would
make it meaningless.
"""
import subprocess, sys, time

BLOCKS = [
    ("surr_t6  (slack 1, the dashboard's real horizon)",
     [sys.executable, "surr_t6.py", "surr_t6.jsonl", "30"], "surr_t6.log"),
    ("ties     (how degenerate is each scheme's optimum)",
     [sys.executable, "ties.py"], "ties.log"),
    ("timing   (Z3, alone, 900s cap)",
     [sys.executable, "runner.py", "plan_timing.json"], "timing.log"),
]

for name, cmd, log in BLOCKS:
    print(f"[{time.strftime('%H:%M:%S')}] START {name}", flush=True)
    t = time.monotonic()
    with open(log, "w") as f:
        rc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT).returncode
    print(f"[{time.strftime('%H:%M:%S')}] DONE  {name}  rc={rc} "
          f"({time.monotonic()-t:.0f}s)", flush=True)
print("all blocks complete", flush=True)
