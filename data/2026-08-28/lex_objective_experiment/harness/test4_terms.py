"""Which term actually decides the route when People is on?

Each objective term is divided by a theoretical max before being weighted, so the
number that matters is not the weight but weight x (value / max) -- how much of its
own normalized range the term actually spans. A term pinned near 0% of its range
cannot outvote one sitting at 80%, whatever its nominal weight says.

Recomputed offline from the returned routing using the solver's own divisors, so
this works whether or not the term was switched on.
"""
import cfg, client

SCALE = W_SCALE = 100

def terms(res, req):
    N, M, T = req["N"], req["M"], res.get("T_used") or res["T"]
    mult = req["aircraftMultipliers"]
    tw   = req.get("stationTransitWeights")
    max_tw = max(round(w * W_SCALE) for w in tw) if tw else W_SCALE

    out = {}
    if req.get("optimizePrioritarian"):
        prot = req["protectedStations"]
        val  = sum(res["noiseMatrix"][p - 1][t] for p in prot for t in range(T))
        # max_protected_dB / SCALE, in real dB
        mx = len(prot) * T * max(max(r) for r in res["noiseMatrix"]) if val else None
        out["prioritarian"] = (req["weightPrioritarian"], val, mx)
    if req.get("optimizeUtilitarian"):
        if req.get("utilNoiseMode"):
            val = cfg.util_noise(res, req)
            mx  = M * T * max(max(r) for r in res["noiseMatrix"]) * (max_tw / W_SCALE if tw else 1)
        else:
            val = cfg.transit_cost(res, req)
            mx  = sum(mult) * (T - 1) * max(1, max_tw) / W_SCALE
        out["utilitarian/People"] = (req["weightUtilitarian"], val, mx)
    tpen = sum(next((t for t, v in enumerate(p) if v == req["endPositions"][i]), T - 1)
               for i, p in enumerate(res["paths"]))
    out["time penalty"] = (req.get("weightTime", 1.0), tpen, N * (T - 1))
    return out

def show(label, port, req):
    res, el = client.post(port, req)
    if client.fellback(res) or res.get("status") != "sat":
        print(f"{label}: no weighted result"); return
    print(f"\n{label}  [{el:.0f}s]  peak=+{client.peak(res):.2f}dB")
    print(f"  {'term':22} {'weight':>7} {'value':>11} {'max':>11} {'% of range':>11} {'pull':>9}")
    rows = []
    for name, (w, val, mx) in terms(res, req).items():
        if not mx: print(f"  {name:22} {w:7} {val:11.2f}  (no max)"); continue
        frac = val / mx
        rows.append((name, w, val, mx, frac, w * frac))
    tot = sum(r[5] for r in rows) or 1
    for name, w, val, mx, frac, pull in rows:
        print(f"  {name:22} {w:7} {val:11.2f} {mx:11.2f} {100*frac:10.1f}% {100*pull/tot:8.1f}%")

if __name__ == "__main__":
    for principle, who in (("prioritarian", "people"), ("prioritarian", "communities"),
                           ("utilitarian", "people"), ("equal", "people")):
        req = cfg.build(principle, who, timeoutMs=1200000)
        show(f"{principle} + {who}  (PRODUCTION)", 5057, req)
