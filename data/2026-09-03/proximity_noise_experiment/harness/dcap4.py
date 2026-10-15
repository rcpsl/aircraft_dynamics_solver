"""D=4 dB: the case where more TIME is the right fix, not fewer flights.

At D=4 a 45 dB tile admits exactly one aircraft (+3.01 dB) but not two (+4.77 dB).
Community is a 45 dB tile and is the destination for four aircraft, so they have to
land on four DIFFERENT timesteps. That is a constraint no per-aircraft pre-check can
see -- it is an interaction between aircraft -- so T_lower comes out optimistic and
phase 1 has to walk the horizon up to find the real minimum.
"""
import json, time, urllib.request
import mkreq as mk
URL="http://127.0.0.1:5055/solve"

def post(req):
    t=time.monotonic()
    r=urllib.request.urlopen(urllib.request.Request(URL,
        json.dumps(req).encode(), {"Content-Type":"application/json"}), timeout=2400)
    return json.load(r), time.monotonic()-t

def show(label, req):
    print(f"-> {label}  (D={req['D']}, T_max={req['T_max']})", flush=True)
    try: res,el=post(req)
    except Exception as e:
        print(f"   CLIENT {type(e).__name__}: {e}\n", flush=True); return None
    st=res.get("status")
    if st!="sat":
        print(f"   {st.upper()}  reason={res.get('reason')}  [{el:.0f}s]", flush=True)
        print(f"   detail: {res.get('detail','')}\n", flush=True)
        return res
    peak=max((max(r) for r in res["noiseMatrix"]), default=0)
    arr=[next((t for t,v in enumerate(p) if v==req["endPositions"][i]), None)
         for i,p in enumerate(res["paths"])]
    com=5   # station 5 = Community (row-major index 4, 1-indexed)
    into_com=sorted(a for i,a in enumerate(arr) if req["endPositions"][i]==com)
    print(f"   SAT  T={res.get('T_used')}  T_min={res.get('T_min')}  peak=+{peak:.2f}dB  [{el:.0f}s]", flush=True)
    print(f"   arrivals into Community (needs 4 distinct steps): {into_com}\n", flush=True)
    return res

def cap(D, T):
    r=mk.build(T_max=T, timeoutMs=1200000)
    r.pop("proximityWeights"); r["optimizeProximity"]=False
    r["D"]=D; r["U"]=30
    return r

if __name__=="__main__":
    ends=mk.build()["endPositions"]
    print(f"Community (station 5) is the destination for "
          f"{sum(1 for e in ends if e==5)} of {len(ends)} aircraft, "
          f"and at D=4 it holds 1 at a time.\n", flush=True)
    show("D=4, dashboard horizon (slack 1)", cap(4, 6))
    show("D=4, horizon 7", cap(4, 7))
    show("D=4, horizon 8 (what the retry would send)", cap(4, 8))
    show("D=3, for contrast -- no horizon can fix it", cap(3, 8))
