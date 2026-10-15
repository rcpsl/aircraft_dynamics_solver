"""Did the burden move to the already-loud tiles? Compare where each routing
actually puts its aircraft-timesteps, grouped by baseline tier."""
import json, sys, importlib.util as iu
sys.path.insert(0,".")
import mkreq as mk
spec=iu.spec_from_file_location("S", r"d:/Documents/EECS_199_Shoukry/proximity_noise_experiment/solver_server_dB_noise.py")
S=iu.module_from_spec(spec); spec.loader.exec_module(S)

req=mk.build(); M=25
base=req["baseline"]; W=req["proximityWeights"]
names=["Rural-Sub Outskirts","Sub Tech Campus","CYO 1","University","Exurban Commuter",
"Quiet Rural LowInc","Affluent Suburban","Working-Class Homeown","CYO 2","Greenbelt Edge",
"Airport","CYO 3","Popular Urban Shops","Lower-Inc Urban","International Dist",
"Underdeveloped","Retirement","Downtown","Historic Black","New High-Density",
"Retail & Ent Center","Mixed Urban","Gentrifying","CYO 4","Industrial Center"]

def occupancy(paths):
    T=len(paths[0]); N=len(paths)
    cnt,_=S._active_output_matrices(paths, req["startPositions"], req["endPositions"],
            N, M, T, base, req["aircraftDB"], multipliers=req["aircraftMultipliers"])
    return [sum(cnt[m]) for m in range(M)]   # aircraft-timesteps per station

runs={}
for lbl,f in (("count","paths_count_slack0.json"),("noise A","paths_A.json")):
    try: runs[lbl]=occupancy(json.load(open(f)))
    except FileNotFoundError: print(f"(missing {f})")
if len(runs)<2: sys.exit()

print(f"{'':26}{'base':>5}{'weight':>8}", *[f"{k:>10}" for k in runs])
print("-"*70)
for m in sorted(range(M), key=lambda m:-abs(runs['noise A'][m]-runs['count'][m]))[:10]:
    print(f"{names[m][:25]:26}{base[m]:5}{W[m]:8.1f}", *[f"{runs[k][m]:>10}" for k in runs])
print("\n=== aircraft-timesteps by baseline tier ===")
for b in (45,55,65):
    idx=[m for m in range(M) if base[m]==b]
    tot={k:sum(runs[k][m] for m in idx) for k in runs}
    line=" ".join(f"{k}={tot[k]:>4}" for k in tot)
    print(f"  {b} dB tiles (n={len(idx):2}): {line}")
print("\n=== the two low-income 65 dB tiles I flagged ===")
for m in (15,24):
    print(f"  {names[m]:22} w={W[m]:6.1f}  " + "  ".join(f"{k}={runs[k][m]}" for k in runs))
