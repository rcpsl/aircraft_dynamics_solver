"""Run the remaining plans in sequence, waiting for each to finish.

A shell-based chain does NOT work here: Git Bash's `pgrep -f` cannot see native
Windows python processes, so any "wait for the previous block" guard fires
immediately and every block runs at once. subprocess.run blocks properly.

`reps` is run LAST and alone (par 1 in its plan) because it measures run-to-run
timing variance, which is meaningless under contention from other sweeps.

usage: python orchestrate.py
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SEQ = ["caps", "prior_sets", "ablation", "reps"]

for name in SEQ:
    plan = os.path.join(HERE, "plans", f"{name}.json")
    log = os.path.join(HERE, "results", f"{name}.log")
    print(f"=== {name} starting {time.strftime('%H:%M:%S')} ===", flush=True)
    with open(log, "w", encoding="utf-8") as fh:
        rc = subprocess.run([sys.executable, os.path.join(HERE, "runner.py"), plan],
                            cwd=HERE, stdout=fh, stderr=subprocess.STDOUT).returncode
    print(f"=== {name} done rc={rc} {time.strftime('%H:%M:%S')} ===", flush=True)

print("ALL PLANS COMPLETE", flush=True)
