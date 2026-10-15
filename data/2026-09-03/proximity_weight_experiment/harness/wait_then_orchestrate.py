"""Wait for the T=5 surrogate sweep to write its last row, then orchestrate."""
import os, subprocess, sys, time
TARGET = 3360
while True:
    n = sum(1 for _ in open("surr.jsonl")) if os.path.exists("surr.jsonl") else 0
    if n >= TARGET:
        break
    time.sleep(20)
print(f"[{time.strftime('%H:%M:%S')}] surr.jsonl complete at {n} rows", flush=True)
subprocess.run([sys.executable, "orchestrate.py"])
