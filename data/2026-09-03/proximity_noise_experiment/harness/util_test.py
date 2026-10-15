"""Why is Utilitarian's dB objective fast when Proximity's is slow?

Both minimize Sum_t Sum_m dB_increase(m,count) * weight[m] over the whole grid --
structurally the SAME expression, same If-chains, same D=U=30. The only difference
is the weight vector. Utilitarian's weights are uniform (or 1/2/3 with People on);
Proportional's ranked weights span 56x.

Hypothesis: the coefficient SPREAD, not the dB term, is what costs. Runs 3 and 4
test it directly by feeding the proximity objective utilitarian-shaped weights.

Port 5053 so this does not queue behind the ranking sweep on 5052. Absolute timings
are mildly inflated by that parallel load; the comparison BETWEEN these runs is not.
"""
import json, time, urllib.request
import mkreq as mk

POPW={'Low':1,'Medium':2,'High':3}
POP=[POPW.get(r[2] if False else r[1], 2) if r[1] else 2 for r in mk.rows]

def post(req):
    t=time.monotonic()
    r=urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:5053/solve",
        json.dumps(req).encode(), {"Content-Type":"application/json"}), timeout=2000)
    return json.load(r), time.monotonic()-t

def show(label, req):
    ipw=[round(w*100) for w in req.get("proximityWeights",[])] or \
        [round(w*100) for w in req.get("stationTransitWeights",[])] or [100]
    spread=max(ipw)/min(ipw)
    print(f"-> {label}   int coefficients {min(ipw)}..{max(ipw)}  spread {spread:.0f}x", flush=True)
    try: res,el=post(req)
    except Exception as e:
        print(f"   {label:34} CLIENT {type(e).__name__}: {str(e)[:90]}\n", flush=True); return
    if res.get("status")=="sat" and "T_used" not in res:
        print(f"   {label:34} FELL BACK after {el:.0f}s\n", flush=True); return
    if res.get("status")!="sat":
        print(f"   {label:34} {res.get('status')} {res.get('reason','')} [{el:.0f}s]\n", flush=True); return
    peak=max((max(r) for r in res["noiseMatrix"]), default=0)
    print(f"   {label:34} sat T={res['T_used']} peak=+{peak:.2f}dB [{el:.0f}s]\n", flush=True)

def base_req(**kw):
    r=mk.build(T_max=mk.build()["T_max"]-1, timeoutMs=1800000, **kw)
    return r

if __name__=="__main__":
    # 1-2: real Utilitarian, the configuration the dashboard sends
    r=base_req(); r.pop("proximityWeights"); r["optimizeProximity"]=False
    r["optimizeUtilitarian"]=True; r["utilNoiseMode"]=True; r["weightUtilitarian"]=1.0
    show("1 utilitarian, People OFF", r)

    r=base_req(); r.pop("proximityWeights"); r["optimizeProximity"]=False
    r["optimizeUtilitarian"]=True; r["utilNoiseMode"]=True; r["weightUtilitarian"]=1.0
    r["stationTransitWeights"]=[float(p) for p in POP]
    show("2 utilitarian, People ON (1/2/3)", r)

    # 3-4: the SAME proximity dB objective, but with utilitarian-shaped weights
    show("3 proximity noise, uniform w=1", base_req(proximityWeights=[1.0]*25))
    show("4 proximity noise, w=1/2/3", base_req(proximityWeights=[float(p) for p in POP]))

    # 5: control -- the real ranked weights
    show("5 proximity noise, ranked (real)", base_req())
