"""Is the salvaged incumbent actually BETTER than the phase-1 route it replaces?

The best-so-far salvage is only worth having if a partially-optimized route beats
the unoptimized one. That is not automatic: Z3's first incumbent can be arbitrary,
and a route with an objective "applied" but barely progressed could in principle
score worse on that objective than the plain feasible route phase 1 hands back.

So this scores BOTH on the same metric, recomputed from the returned paths rather
than trusted from the solver's own reporting, and prints them side by side. A short
budget where the salvage loses would be an argument for a floor -- keep the salvage
only past some elapsed fraction -- rather than for dropping it.

Usage: python test6_salvage_value.py [port]
"""
import sys, cfg, client

REQ = lambda ms: cfg.build("utilitarian", who="people", timeoutMs=ms)


def score(label, port, ms):
    req = REQ(ms)
    try:
        res, el = client.post(port, req)
    except Exception as e:
        print("  %-22s CLIENT %s: %s" % (label, type(e).__name__, e), flush=True)
        return None
    if res.get("status") != "sat":
        print("  %-22s %s" % (label, res.get("status")), flush=True)
        return None
    # Recomputed from the paths, so the phase-1 fallback (which reports no
    # totalUtilNoise of its own) and the phase-2 result are measured the same way.
    v = cfg.util_noise(res, req)
    print("  %-22s optimality=%-8s utilNoise=%8.2f  [%3.0fs]"
          % (label, res.get("optimality"), v, el), flush=True)
    return v


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5057
    print("=== salvage value, port %d ===" % port, flush=True)
    print("  payload: Utilitarian + People, which solves to proven-optimal in ~620s",
          flush=True)
    print("", flush=True)
    fallback = score("5s -> phase-1 route", port, 5000)
    for ms in (30000, 60000, 120000, 240000):
        v = score("%ds -> salvaged" % (ms // 1000), port, ms)
        if v is not None and fallback is not None:
            better = "BETTER" if v < fallback else "WORSE than phase 1"
            print("      vs phase 1: %+.2f  %s" % (v - fallback, better), flush=True)
