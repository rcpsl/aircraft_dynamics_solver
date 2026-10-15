"""Do the two solvers now answer with the SAME API, and does the salvage work?

Run one arm per process: `python test5_api_shape.py 5057` (production) and
`python test5_api_shape.py 5056` (lex). The solve lock is per server process, so
the two ports genuinely parallelise.

Three things to establish:

  1. Shape parity. Every reply from either solver carries objectiveMode,
     optimality, principleOptimized, phase2Failed and principleImposed, and the
     only field whose VALUE may differ is objectiveMode. A frontend can then be
     pointed at whichever solver is working without knowing which it got.
  2. principleOptimized tells Equal/Sufficientarian apart from the rest. They set
     no objective at all, so a proven-optimal reply from them means something
     different from a proven-optimal Proportional reply, and the flag is the only
     way to see it.
  3. The best-so-far salvage. Given a deliberately tiny timeout on a payload known
     to need ~10 minutes, phase 2 must come back optimality="partial" with the
     objective applied -- NOT phase2Failed with phase 1's unoptimized route. This
     is the whole point of the change: a slow solve should cost optimality, not
     the principle.
"""
import sys, cfg, client

SHAPE = ("objectiveMode", "optimality", "principleOptimized",
         "phase2Failed", "principleImposed")


def probe(label, port, req, expect_optimality=None, expect_principle=None):
    try:
        res, el = client.post(port, req)
    except Exception as e:
        print("  %-34s CLIENT %s: %s" % (label, type(e).__name__, e), flush=True)
        return

    missing = [k for k in SHAPE if k not in res]
    bits = []
    for k in SHAPE:
        if k in res:
            bits.append("%s=%s" % (k, res[k]))
    if "arrivalPenalty" in res:
        bits.append("arrivalPenalty=%s" % res["arrivalPenalty"])

    verdict = []
    if missing:
        verdict.append("MISSING " + ",".join(missing))
    if expect_optimality and res.get("optimality") != expect_optimality:
        verdict.append("WANTED optimality=%s" % expect_optimality)
    if expect_principle is not None and res.get("principleOptimized") != expect_principle:
        verdict.append("WANTED principleOptimized=%s" % expect_principle)
    tag = "FAIL: " + "; ".join(verdict) if verdict else "ok"

    print("  %-34s [%5.0fs] %s" % (label, el, tag), flush=True)
    print("      " + "  ".join(bits), flush=True)
    for k in ("warning", "notice"):
        if k in res:
            print("      %s: %s" % (k.upper(), res[k]), flush=True)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5057
    print("=== port %d ===" % port, flush=True)

    print("\n--- 1. a principle that IS optimized, proven ---", flush=True)
    probe("proportional", port, cfg.build("proportional", timeoutMs=900000),
          expect_optimality="optimal", expect_principle=True)
    probe("prioritarian", port, cfg.build("prioritarian", timeoutMs=900000),
          expect_optimality="optimal", expect_principle=True)

    print("\n--- 2. principles with NO objective term ---", flush=True)
    print("    principleOptimized must be False, principleImposed still True",
          flush=True)
    probe("equal", port, cfg.build("equal", timeoutMs=900000),
          expect_optimality="optimal", expect_principle=False)
    probe("sufficientarian", port, cfg.build("sufficientarian", timeoutMs=900000),
          expect_optimality="optimal", expect_principle=False)

    print("\n--- 3. salvage: 60s on a payload that needs ~10min ---", flush=True)
    print("    partial + the objective applied, NOT a fallback to phase 1",
          flush=True)
    probe("utilitarian+people @60s", port,
          cfg.build("utilitarian", who="people", timeoutMs=60000),
          expect_optimality="partial", expect_principle=True)

    print("\n--- 4. the floor: 5s, too short to reach ANY solution ---", flush=True)
    print("    the salvage must not invent one -- this still fails, and still says so",
          flush=True)
    probe("utilitarian+people @5s", port,
          cfg.build("utilitarian", who="people", timeoutMs=5000),
          expect_optimality="none", expect_principle=False)
