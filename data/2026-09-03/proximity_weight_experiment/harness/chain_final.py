"""Run the replication block once the demand block finishes."""
import json, os, subprocess, sys, time
while True:
    n = sum(1 for _ in open("demand.jsonl")) if os.path.exists("demand.jsonl") else 0
    if n >= 6:
        break
    time.sleep(20)
print(f"[{time.strftime('%H:%M:%S')}] demand complete, starting replication", flush=True)
subprocess.run([sys.executable, "runner.py", "plan_final.json"],
               stdout=open("final.log", "w"), stderr=subprocess.STDOUT)
print(f"[{time.strftime('%H:%M:%S')}] replication done", flush=True)
