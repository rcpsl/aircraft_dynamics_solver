"""Do the OTHER principles' objectives also get outvoted by the soft-T penalty?

Equal and Sufficientarian set no objective at all - their fairness rule is a HARD
D/U cap - so the time penalty is the only objective term by construction. Only
Prioritarian has a soft objective to compare against Utilitarian/Proportional.

Port 5053, alongside the ranking sweep on 5052.
"""
import json, time, urllib.request
import mkreq as mk
PROT=[14,22,16]   # Lower-Income Urban, Mixed Urban, Underdeveloped -- all Low income

def post(req):
    t=time.monotonic()
    r=urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:5053/solve",
        json.dumps(req).encode(), {"Content-Type":"application/json"}), timeout=2000)
    return json.load(r), time.monotonic()-t

def show(label, req):
    print(f"-> {label}", flush=True)
    try: res,el=post(req)
    except Exception as e:
        print(f"   {label:40} CLIENT {type(e).__name__}\n", flush=True); return
    if res.get("status")=="sat" and "T_used" not in res:
        print(f"   {label:40} FELL BACK after {el:.0f}s\n", flush=True); return
    if res.get("status")!="sat":
        print(f"   {label:40} {res.get('status')} {res.get('reason','')} [{el:.0f}s]\n", flush=True); return
    peak=max((max(r) for r in res["noiseMatrix"]), default=0)
    extra=""
    if "protectedNoise" in res: extra=f" protectedNoise={res['protectedNoise']}"
    print(f"   {label:40} sat peak=+{peak:.2f}dB{extra} [{el:.0f}s]\n", flush=True)

def base():
    r=mk.build(T_max=mk.build()["T_max"]-1, timeoutMs=1800000)
    r.pop("proximityWeights"); r["optimizeProximity"]=False
    return r

if __name__=="__main__":
    # no soft objective at all -- D/U are hard caps, time penalty is alone
    r=base(); r["U"]=10; r["D"]=30
    show("Equal 10 dB (no objective)", r)
    r=base(); r["D"]=10; r["U"]=30
    show("Sufficientarian 10 dB (no objective)", r)

    # the one other principle WITH a soft objective
    r=base(); r["optimizePrioritarian"]=True; r["protectedStations"]=PROT
    show("Prioritarian, w_prior=1 (default)", r)

    # if its objective binds weakly like Utilitarian's, strengthening should hurt
    r=base(); r["optimizePrioritarian"]=True; r["protectedStations"]=PROT
    r["weightPrioritarian"]=8.0
    show("Prioritarian, w_prior=8", r)
