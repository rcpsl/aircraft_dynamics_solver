"""Run the demand block once the timing block is finished."""
import json, os, subprocess, sys, time
while True:
    n = sum(1 for _ in open("timing.jsonl")) if os.path.exists("timing.jsonl") else 0
    if n >= 15:
        break
    time.sleep(20)
print(f"[{time.strftime('%H:%M:%S')}] timing complete, starting demand block", flush=True)
subprocess.run([sys.executable, "runner.py", "plan_demand.json"],
               stdout=open("demand.log", "w"), stderr=subprocess.STDOUT)
print(f"[{time.strftime('%H:%M:%S')}] demand block done", flush=True)
