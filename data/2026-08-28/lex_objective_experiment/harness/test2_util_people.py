"""Is the Utilitarian objective actually optimizing anything when People is on?

The honest test is not "did the solver report a number" -- it always does. It is
whether switching the objective OFF changes that number. So each config is solved
twice, once as the dashboard sends it and once with optimizeUtilitarian cleared,
and the objective is recomputed from the RETURNED ROUTING both times so the two are
directly comparable.

  objective ON < objective OFF   -> it is doing work
  objective ON == objective OFF  -> inert; the routing would be identical without it

Two distinct configs, because one flag cannot serve both meanings:
  Utilitarian + People -> utilNoiseMode=True,  weight 1.0, population-weighted dB
  Equal + People       -> utilNoiseMode=False, weight 0.3, population-weighted transit
"""
import cfg, client

def probe(label, port, principle, who):
    on  = cfg.build(principle, who, timeoutMs=1200000)
    off = cfg.build(principle, who, timeoutMs=1200000)
    off["optimizeUtilitarian"] = False
    noise_mode = on["utilNoiseMode"]
    metric = cfg.util_noise if noise_mode else cfg.transit_cost
    name   = "weighted dB" if noise_mode else "weighted transit"

    print(f"\n{label}  (utilNoiseMode={noise_mode}, weightUtilitarian={on['weightUtilitarian']}, T_max={on['T_max']})")
    out = {}
    for tag, req in (("objective ON ", on), ("objective OFF", off)):
        try: res, el = client.post(port, req)
        except Exception as e:
            print(f"  {tag}  CLIENT {type(e).__name__}: {e}"); return
        if client.fellback(res):
            print(f"  {tag}  PHASE-2 FELL BACK [{el:.0f}s] -- objective not applied"); return
        if res.get("status") != "sat":
            print(f"  {tag}  {res.get('status')} {res.get('reason','')} [{el:.0f}s]"); return
        v = metric(res, req)
        out[tag] = v
        rep = res.get("totalUtilNoise", res.get("totalTransit"))
        chk = "" if rep is None else f"  (solver reported {rep}"+(", matches)" if abs(rep-v)<0.01 else f", MISMATCH vs {v:.2f})")
        print(f"  {tag}  {name}={v:9.2f}  peak=+{client.peak(res):5.2f}dB  arr={cfg.arrivals(res,req):3d}  [{el:.0f}s]{chk}")
    if len(out) == 2:
        a, b = out["objective ON "], out["objective OFF"]
        if abs(a - b) < 1e-6:
            print(f"  --> INERT: identical {name} with the objective on and off.")
        elif a < b:
            print(f"  --> WORKING: objective improves {name} by {b-a:.2f} ({100*(b-a)/b:.1f}%).")
        else:
            print(f"  --> WRONG DIRECTION: objective made {name} WORSE by {a-b:.2f}.")

if __name__ == "__main__":
    import sys
    # One port per process so the lex and production arms run as concurrent jobs.
    # The solve lock is per SERVER PROCESS, so 5056 and 5057 genuinely parallelise;
    # only same-port requests queue.
    ports = [int(a) for a in sys.argv[1:]] or [5056, 5057]
    for port in ports:
        tag = "LEX" if port == 5056 else "PRODUCTION"
        print("", flush=True)
        print("=" * 66, flush=True)
        print(f"{tag} (port {port})", flush=True)
        print("=" * 66, flush=True)
        probe("Utilitarian + People", port, "utilitarian", "people")
        probe("Utilitarian + Communities", port, "utilitarian", "communities")
        probe("Equal + People", port, "equal", "people")
