"""Is the slowdown caused by how HARD the objective binds, not by the dB term?

eff_w = w / max_normalization, so scaling the request weight is exactly equivalent
to loosening or tightening the divisor. That lets both directions be tested without
touching solver code:

  A  proximity, uniform w, weightProximity scaled DOWN  -> mimics utilitarian's loose
     bound. If this turns fast, binding strength is the cause.
  B  utilitarian, weightUtilitarian scaled UP           -> mimics an exact bound.
     If this turns slow, same conclusion from the other side.

Port 5054, alongside the sweep (5052) and the util batch (5053).
"""
import json, time, urllib.request
import mkreq as mk
from util_test import POP

def post(req):
    t=time.monotonic()
    r=urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:5054/solve",
        json.dumps(req).encode(), {"Content-Type":"application/json"}), timeout=2000)
    return json.load(r), time.monotonic()-t

def show(label, req):
    print(f"-> {label}", flush=True)
    try: res,el=post(req)
    except Exception as e:
        print(f"   {label:38} CLIENT {type(e).__name__}\n", flush=True); return
    if res.get("status")=="sat" and "T_used" not in res:
        print(f"   {label:38} FELL BACK after {el:.0f}s\n", flush=True); return
    if res.get("status")!="sat":
        print(f"   {label:38} {res.get('status')} [{el:.0f}s]\n", flush=True); return
    peak=max((max(r) for r in res["noiseMatrix"]), default=0)
    print(f"   {label:38} sat peak=+{peak:.2f}dB [{el:.0f}s]\n", flush=True)

def prox(w, wp):
    return mk.build(T_max=mk.build()["T_max"]-1, timeoutMs=1800000,
                    proximityWeights=w, weightProximity=wp)
def util(wu):
    r=mk.build(T_max=mk.build()["T_max"]-1, timeoutMs=1800000)
    r.pop("proximityWeights"); r["optimizeProximity"]=False
    r["optimizeUtilitarian"]=True; r["utilNoiseMode"]=True; r["weightUtilitarian"]=wu
    return r

if __name__=="__main__":
    U=[1.0]*25
    # A: weaken proximity toward utilitarian's effective strength (8x and 16x weaker)
    show("A1 proximity uniform, w_prox=0.125", prox(U, 0.125))
    show("A2 proximity uniform, w_prox=0.0625", prox(U, 0.0625))
    # B: strengthen utilitarian toward an exact-bound equivalent
    show("B1 utilitarian, w_util=8", util(8.0))
    show("B2 utilitarian, w_util=16", util(16.0))
