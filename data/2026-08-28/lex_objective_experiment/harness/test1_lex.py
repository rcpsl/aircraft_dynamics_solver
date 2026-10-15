"""Does the lexicographic form work, and does it cost anything?

Run one ARM per process -- `python test1_lex.py 5056` (lex) and `python test1_lex.py
5057` (production) concurrently. The solve lock is per SERVER PROCESS, so the two
ports genuinely parallelise; only same-port requests queue.

Four things to establish:

  1. Fairness never gets worse. The principle tier is optimized first, so its value
     must be <= production's weighted-sum value on every principle. If lex is EVER
     worse, the change is wrong.
  2. The tie-break still runs. Equal and Sufficientarian have no objective at all;
     under a plain "drop the time term" change they returned an arbitrary route
     (peak +8.45 dB vs +6.02). Under lex the second tier should still pin them.
  3. Weight-invariance. With one principle term active, lex makes its weight
     mathematically irrelevant -- scaling it cannot move the argmin. Under the old
     weighted sum it mattered enormously (8x turned 199s into a timeout). This is
     the sharpest single test that lex is actually in effect.
"""
import cfg, client

def run(label, port, req, note=""):
    try: res, el = client.post(port, req)
    except Exception as e:
        print(f"  {label:38} CLIENT {type(e).__name__}: {e}", flush=True); return None
    if client.fellback(res):
        print(f"  {label:38} PHASE-2 FELL BACK [{el:.0f}s]", flush=True); return res
    if res.get("status") != "sat":
        print(f"  {label:38} {res.get('status')} {res.get('reason','')} [{el:.0f}s]", flush=True); return res
    bits = [f"peak=+{client.peak(res):5.2f}dB", f"arr={cfg.arrivals(res,req):3d}"]
    for k, tag in (("proximityCost","prox"), ("protectedNoise","prot"),
                   ("totalUtilNoise","utilNoise"), ("totalTransit","transit")):
        if k in res: bits.append(f"{tag}={res[k]}")
    if "arrivalPenalty" in res: bits.append(f"Tpen={res['arrivalPenalty']}")
    print(f"  {label:38} {'  '.join(bits)}  [{el:.0f}s]{note}", flush=True)
    return res

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5056
    tag = "LEX" if port == 5056 else "PRODUCTION"
    print(f"=== {tag} (port {port}) ===", flush=True)

    print("", flush=True)
    print("--- 1. fairness value per principle ---", flush=True)
    for principle in ("proportional", "prioritarian", "equal", "sufficientarian"):
        run(principle, port, cfg.build(principle, timeoutMs=1200000))

    print("", flush=True)
    print("--- 2. principle weight 1.0 vs 8.0 ---", flush=True)
    print("    under lex this CANNOT change the answer; under a weighted sum it can", flush=True)
    for w in (1.0, 8.0):
        run(f"weightProximity={w}", port,
            cfg.build("proportional", timeoutMs=1200000, weightProximity=w))

    print("", flush=True)
    print("--- 3. weightTime 1.0 / 8.0 / 0.0 ---", flush=True)
    for wt in (1.0, 8.0, 0.0):
        run(f"weightTime={wt}", port,
            cfg.build("proportional", timeoutMs=1200000, weightTime=wt))

