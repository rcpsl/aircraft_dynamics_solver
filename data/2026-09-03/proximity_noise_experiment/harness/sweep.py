"""Every ranking, both pricings: do count and noise agree?

24 permutations of the four factors, plus 6 with Population switched off (three
factors at 0.45/0.35/0.20). Each is solved twice, once per proximityMode.

Runs at slack 0 (T=5), not the dashboard's slack 1. Justified: count mode returned an
identical routing, peak and proximityCost at both horizons, and slack 0 is roughly
half the wall clock -- which matters across 60 solves. Noise runs get the 1800s
server cap so they cannot fall back to phase 1 and be mistaken for agreement.

Resumable: results append to sweep.jsonl and completed keys are skipped on restart.
"""
import json, os, itertools, time, urllib.request, urllib.error
import mkreq as mk

FACTORS=['income','ambient','distance','population']
OUT='sweep.jsonl'

def configs():
    for p in itertools.permutations(FACTORS):
        yield {"order":list(p), "pop":True}
    for p in itertools.permutations([f for f in FACTORS if f!='population']):
        yield {"order":list(p), "pop":False}

def post(req, timeout):
    t=time.monotonic()
    r=urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:5052/solve",
        json.dumps(req).encode(), {"Content-Type":"application/json"}), timeout=timeout)
    return json.load(r), time.monotonic()-t

def tiers(paths, req):
    import importlib.util as iu
    spec=iu.spec_from_file_location("S",
        r"d:/Documents/EECS_199_Shoukry/proximity_noise_experiment/solver_server_dB_noise.py")
    S=iu.module_from_spec(spec); spec.loader.exec_module(S)
    T=len(paths[0])
    cnt,_=S._active_output_matrices(paths, req["startPositions"], req["endPositions"],
        len(paths), 25, T, req["baseline"], req["aircraftDB"],
        multipliers=req["aircraftMultipliers"])
    occ=[sum(cnt[m]) for m in range(25)]
    return occ, {b:sum(occ[m] for m in range(25) if req["baseline"][m]==b) for b in (45,55,65)}

def run(cfg, mode):
    full=mk.build()["T_max"]
    kw={"T_max":full-1, "proximityMode":mode}
    if mode=="noise": kw["timeoutMs"]=1800000
    req=mk.build(order=tuple(cfg["order"]), **kw)
    if not cfg["pop"]:
        req["proximityWeights"]=mk.weights([f for f in cfg["order"] if f!='population'])
    try:
        res,el=post(req, 2000)
    except Exception as e:
        return {"status":f"CLIENT {type(e).__name__}", "detail":str(e)[:120]}
    rec={"status":res.get("status"), "wall":round(el)}
    if res.get("status")=="sat" and "T_used" not in res:
        rec["status"]="phase2_fell_back"; return rec
    if res.get("status")!="sat": return rec
    occ,tier=tiers(res["paths"], req)
    rec.update({"T":res["T_used"], "occ":occ, "tier":{str(k):v for k,v in tier.items()},
                "prox":res.get("proximityCost"),
                "peak":round(max((max(r) for r in res["noiseMatrix"]), default=0),3)})
    return rec

if __name__=="__main__":
    done=set()
    if os.path.exists(OUT):
        for line in open(OUT):
            try: done.add(json.loads(line)["key"])
            except Exception: pass
    cfgs=list(configs())
    print(f"{len(cfgs)} rankings x 2 modes = {2*len(cfgs)} solves; {len(done)} already done", flush=True)
    for i,cfg in enumerate(cfgs,1):
        key="|".join(cfg["order"])+("" if cfg["pop"] else "|NOPOP")
        if key in done:
            print(f"[{i:2}/{len(cfgs)}] skip {key}", flush=True); continue
        rec={"key":key, "order":cfg["order"], "pop":cfg["pop"]}
        for mode in ("count","noise"):
            rec[mode]=run(cfg, mode)
            print(f"[{i:2}/{len(cfgs)}] {key:46} {mode:5} "
                  f"{rec[mode]['status']:16} {rec[mode].get('wall','?')}s "
                  f"tier={rec[mode].get('tier')}", flush=True)
        same = (rec["count"].get("occ") is not None
                and rec["count"].get("occ")==rec["noise"].get("occ"))
        rec["identical_routing"]=same
        print(f"[{i:2}/{len(cfgs)}] {key:46} -> identical={same}\n", flush=True)
        with open(OUT,"a") as f: f.write(json.dumps(rec)+"\n")
