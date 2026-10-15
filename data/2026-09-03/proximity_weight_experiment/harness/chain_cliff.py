"""Run the cliff block once the replication block finishes."""
import os, subprocess, sys, time
while True:
    n = sum(1 for _ in open("final.jsonl")) if os.path.exists("final.jsonl") else 0
    if n >= 5:
        break
    time.sleep(20)
print(f"[{time.strftime('%H:%M:%S')}] replication complete, starting cliff block", flush=True)
subprocess.run([sys.executable, "runner.py", "plan_cliff.json"],
               stdout=open("cliff.log", "w"), stderr=subprocess.STDOUT)
print(f"[{time.strftime('%H:%M:%S')}] cliff block done", flush=True)
