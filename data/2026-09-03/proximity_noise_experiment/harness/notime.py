"""Does dropping the soft-T penalty from the objective actually change anything?

No solver edit needed to find out: eff_w_time = w_time / max_T_penalty, so sending
weightTime=0 already removes the term from objective_terms. This runs PRODUCTION
(port 5055) and compares w_time=1 against w_time=0 at three horizons.

Two things are being measured:
  1. monotonicity in T -- active[i][t] is False once an aircraft has arrived, so a
     longer horizon should never cost more. If that holds, an outer loop over T has
     nothing to search: the best T is always the largest one offered.
  2. what is left to optimize -- Equal has no objective at all and Prioritarian's
     sits at 0, so with the time term gone Z3 minimizes nothing and returns an
     arbitrary feasible route.
"""
import json, time, urllib.request
import mkreq as mk
PROT=[14,22,16]
URL="http://127.0.0.1:5055/solve"

def post(req):
    t=time.monotonic()
    r=urllib.request.urlopen(urllib.request.Request(URL,
        json.dumps(req).encode(), {"Content-Type":"application/json"}), timeout=2400)
    return json.load(r), time.monotonic()-t

def arrivals(res, req):
    """First timestep each aircraft is on its destination, summed. This is exactly
    what T_penalty scores, so it says whether removing the term let aircraft dawdle."""
    tot=0
    for i,p in enumerate(res["paths"]):
        end=req["endPositions"][i]
        tot+=next((t for t,v in enumerate(p) if v==end), len(p)-1)
    return tot

def show(label, req):
    print(f"-> {label}", flush=True)
    try: res,el=post(req)
    except Exception as e:
        print(f"   {label:38} CLIENT {type(e).__name__}: {e}\n", flush=True); return None
    if res.get("status")=="sat" and "T_used" not in res:
        print(f"   {label:38} FELL BACK after {el:.0f}s -- weights ignored\n", flush=True); return res
    if res.get("status")!="sat":
        print(f"   {label:38} {res.get('status')} {res.get('reason','')} [{el:.0f}s]\n", flush=True); return res
    peak=max((max(r) for r in res["noiseMatrix"]), default=0)
    bits=[f"T={res['T_used']}", f"peak=+{peak:.2f}dB", f"arrSum={arrivals(res,req)}"]
    if "proximityCost"  in res: bits.append(f"prox={res['proximityCost']}")
    if "protectedNoise" in res: bits.append(f"protNoise={res['protectedNoise']}")
    print(f"   {label:38} sat  {'  '.join(bits)}  [{el:.0f}s]\n", flush=True)
    return res

def prop(T, wt):
    return mk.build(T_max=T, weightTime=wt, timeoutMs=2000000)

if __name__=="__main__":
    full=mk.build()["T_max"]          # chebyshev + slack 1, what the dashboard sends
    lo=full-1                          # slack 0
    print(f"=== dashboard horizons: slack0 T={lo}, slack1 T={full} ===\n", flush=True)

    show(f"Proportional T={lo}  w_time=1 (today)", prop(lo, 1.0))
    show(f"Proportional T={lo}  w_time=0 (plan)",  prop(lo, 0.0))
    show(f"Proportional T={full} w_time=1",        prop(full, 1.0))
    show(f"Proportional T={full} w_time=0",        prop(full, 0.0))
    show(f"Proportional T={full+1} w_time=0",      prop(full+1, 0.0))

    # what remains once the time term is gone, for the principles that never had
    # a working objective of their own
    def bare(T, wt):
        r=mk.build(T_max=T, weightTime=wt, timeoutMs=2000000)
        r.pop("proximityWeights"); r["optimizeProximity"]=False
        return r
    r=bare(lo,0.0); r["U"]=10; r["D"]=30
    show(f"Equal 10dB T={lo} w_time=0", r)
    r=bare(lo,0.0); r["optimizePrioritarian"]=True; r["protectedStations"]=PROT
    show(f"Prioritarian T={lo} w_time=0", r)
