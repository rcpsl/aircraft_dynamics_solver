"""Summarize sweep.jsonl: which rankings make count and noise disagree, and how."""
import json, os, sys
import mkreq as mk
NAMES=["Rural-Sub Outskirts","Sub Tech Campus","CYO 1","University","Exurban Commuter",
"Quiet Rural LowInc","Affluent Suburban","Working-Class Homeown","CYO 2","Greenbelt Edge",
"Airport","CYO 3","Popular Urban Shops","Lower-Inc Urban","International Dist",
"Underdeveloped","Retirement","Downtown","Historic Black","New High-Density",
"Retail & Ent Center","Mixed Urban","Gentrifying","CYO 4","Industrial Center"]
BASE=mk.build()["baseline"]

def wvec(r):
    return mk.weights(r["order"] if r["pop"] else [f for f in r["order"] if f!="population"])

recs=[json.loads(l) for l in open("sweep.jsonl")] if os.path.exists("sweep.jsonl") else []
if not recs: sys.exit("no results yet")

ok=[r for r in recs if r["count"].get("occ") and r["noise"].get("occ")]
div=[r for r in ok if not r["identical_routing"]]
bad=[r for r in recs if r not in ok]
print(f"{len(recs)} rankings solved | {len(ok)} comparable | "
      f"{len(ok)-len(div)} identical | {len(div)} DIVERGED | {len(bad)} unusable")
if bad:
    for r in bad: print(f"  unusable: {r['key']} count={r['count']['status']} noise={r['noise']['status']}")

cw=[r["count"]["wall"] for r in ok]; nw=[r["noise"]["wall"] for r in ok]
if cw: print(f"wall: count {min(cw)}-{max(cw)}s (mean {sum(cw)//len(cw)}s) | "
             f"noise {min(nw)}-{max(nw)}s (mean {sum(nw)//len(nw)}s) | "
             f"noise is {sum(nw)/sum(cw):.0f}x slower")

# does the burden move quiet -> loud, as the baseline gradient predicts?
print("\n=== burden shift by baseline tier (noise minus count, aircraft-timesteps) ===")
for r in div:
    d={b:r["noise"]["tier"][b]-r["count"]["tier"][b] for b in ("45","55","65")}
    print(f"  {r['key']:46} 45dB:{d['45']:+3}  55dB:{d['55']:+3}  65dB:{d['65']:+3}")
if div:
    tot={b:sum(r["noise"]["tier"][b]-r["count"]["tier"][b] for r in div) for b in ("45","55","65")}
    print(f"  {'TOTAL across diverged rankings':46} 45dB:{tot['45']:+3}  55dB:{tot['55']:+3}  65dB:{tot['65']:+3}")

# the decisive test: did noise override the participant's own price ordering?
print("\n=== per-divergence detail (weight = what the ranking asked for) ===")
for r in div:
    w=wvec(r); c,n=r["count"],r["noise"]
    print(f"\n  {r['key']}   peak c={c.get('peak')} n={n.get('peak')}   "
          f"wall c={c['wall']}s n={n['wall']}s")
    moved=[m for m in range(25) if c["occ"][m]!=n["occ"][m]]
    print(f"    {'station':26}{'base':>5}{'weight':>8}{'count':>7}{'noise':>7}  verdict")
    for m in moved:
        delta=n["occ"][m]-c["occ"][m]
        # noise moving traffic ONTO a tile the ranking priced as EXPENSIVE (or off a
        # cheap one) is the baseline gradient overriding the participant.
        v=""
        others=[x for x in moved if (n["occ"][x]-c["occ"][x])*delta<0]
        if others:
            o=others[0]
            if delta>0 and w[m]>w[o] and BASE[m]>BASE[o]: v="<- gained despite costing more"
            if delta<0 and w[m]<w[o] and BASE[m]<BASE[o]: v="<- shed despite being cheaper"
        print(f"    {NAMES[m][:25]:26}{BASE[m]:5}{w[m]:8.1f}{c['occ'][m]:7}{n['occ'][m]:7}  {v}")
