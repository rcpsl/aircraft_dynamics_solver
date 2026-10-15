import json, sys, time, urllib.request, urllib.error
import mkreq as mk

def post(req):
    t=time.monotonic()
    r=urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:5052/solve",
        json.dumps(req).encode(), {"Content-Type":"application/json"}), timeout=1900)
    return json.load(r), time.monotonic()-t

def show(label, req, save=None):
    print(f"-> {label}  (T_max={req['T_max']}) ...", flush=True)
    try: res,el=post(req)
    except urllib.error.HTTPError as e:
        print(f"   {label:28} HTTP {e.code}: {e.read().decode()[:200]}\n", flush=True); return None
    except Exception as e:
        print(f"   {label:28} CLIENT {type(e).__name__}: {e}\n", flush=True); return None
    st=res.get("status")
    # A phase-2 timeout comes back status=sat with a warning and NO T_used: the
    # route is phase 1's unweighted one. That is the case worth catching loudest.
    if st=="sat" and "T_used" not in res:
        print(f"   {label:28} PHASE-2 FELL BACK after {el:.0f}s -- route ignores the weights", flush=True)
        print(f"   {' ':28} {res.get('warning','(no warning)')[:150]}\n", flush=True)
        return res
    if st!="sat":
        print(f"   {label:28} {st} {res.get('reason','')} {str(res.get('detail',''))[:80]}  [{el:.0f}s]\n", flush=True)
        return res
    peak=max((max(r) for r in res.get("noiseMatrix") or []), default=0.0)
    print(f"   {label:28} sat T={res['T_used']} peak=+{peak:.2f}dB "
          f"prox={res.get('proximityCost')} mode={res.get('proximityMode')} [{el:.0f}s]\n", flush=True)
    if save: json.dump(res["paths"], open(save,"w"))
    return res

if __name__=="__main__":
    full=mk.build()["T_max"]
    print(f"=== dashboard horizon for Proportional is T_max={full} (chebyshev+slack 1) ===\n", flush=True)
    show("count (today's term)", mk.build(proximityMode="count"), "paths_count.json")
    show("noise A, slack 0", mk.build(T_max=full-1), "paths_A_slack0.json")
    show("noise B ref 55, slack 0", mk.build(T_max=full-1, proximityNoiseRef=55), "paths_B_slack0.json")
    show("count, slack 0", mk.build(proximityMode="count", T_max=full-1), "paths_count_slack0.json")
