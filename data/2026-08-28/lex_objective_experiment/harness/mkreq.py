"""Reproduce buildSolveRequest() from the 5x5 dashboard for the Proportional principle."""
import json, math
S=3; BASE=5; M=25
rows=[(45,'Medium','Medium',None),(55,'Low','High',None),(None,None,None,None),(55,'High','Low',None),
(45,'Medium','Medium','Community'),(45,'Low','Low',None),(45,'Medium','High',None),(45,'Medium','Low',None),
(None,None,None,None),(45,'Low','Medium',None),(65,'Medium','Low','Airport'),(None,None,None,None),
(55,'Medium','High',None),(45,'High','Low',None),(55,'Medium','Medium',None),(65,'Medium','Low',None),
(45,'Low','Medium',None),(65,'High','High','Downtown'),(55,'Medium','Medium',None),(65,'High','Medium',None),
(55,'High','High',None),(55,'High','Low',None),(55,'Medium','Medium',None),(None,None,None,None),
(65,'Low','Low',None)]
INC={'Low':S,'Medium':S/2,'High':0}; POP={'Low':0,'Medium':S/2,'High':S}
RANKW=[0.40,0.30,0.20,0.10]
RANKW_NOPOP=[0.45,0.35,0.20]
vps=[i for i,r in enumerate(rows) if r[3]]
def ring(i):
    r,c=divmod(i,5); return min(abs(r-vr)+abs(c-vc) for vr,vc in [divmod(v,5) for v in vps])
def weights(order):
    # Mirrors activePropOrder(): with Population switched off it is dropped from the
    # order entirely and the remaining three share 0.45/0.35/0.20, not 0.40/0.30/0.20.
    rw = RANKW if len(order)==4 else RANKW_NOPOP
    w=dict(zip(order,rw)); out=[]
    for i,(b,pop,ic,_) in enumerate(rows):
        bb=b if b is not None else 55
        sc={'income':INC.get(ic,S/2),'ambient':max(0,min(1,(65-bb)/20))*S,
            'distance':ring(i),'population':POP.get(pop,S/2)}
        out.append(round(BASE**sum(w.get(k,0)*v for k,v in sc.items()),4))
    return out
def adjacency():
    A=[[0]*M for _ in range(M)]
    for a in range(M):
        ca,ra=a%5,a//5
        for b in range(M):
            cb,rb=b%5,b//5
            if max(abs(ca-cb),abs(ra-rb))<=1: A[a][b]=1
    return A
def streams(f=1.0):
    # individual mode, demand [4,2,2], both directions -> N=16 at f=1
    air=next(i for i,r in enumerate(rows) if r[3]=='Airport')
    dtn=next(i for i,r in enumerate(rows) if r[3]=='Downtown')
    com=next(i for i,r in enumerate(rows) if r[3]=='Community')
    pairs=[(dtn,air),(com,dtn),(com,air)]
    dem=[max(1,round(c*f)) for c in (4,2,2)]
    s,e,m=[],[],[]
    for (a,b),c in zip(pairs,dem):
        for _ in range(c): s.append(a+1); e.append(b+1); m.append(1)
        for _ in range(c): s.append(b+1); e.append(a+1); m.append(1)
    return s,e,m
def cheb(s,e):
    return max(max(abs((s[i]-1)%5-(e[i]-1)%5), abs((s[i]-1)//5-(e[i]-1)//5)) for i in range(len(s)))+1
def build(order=('income','ambient','distance','population'), demand=1.0, **extra):
    s,e,m=streams(demand)
    req={"N":len(s),"M":M,"D":30,"U":30,"adjacency":adjacency(),
         "startPositions":s,"endPositions":e,"aircraftMultipliers":m,
         "baseline":[(r[0] if r[0] is not None else 55) for r in rows],
         "aircraftDB":45,"hardT":False,
         "optimizeUtilitarian":False,"optimizePrioritarian":False,"optimizeProximity":True,
         "weightUtilitarian":0.3,"weightPrioritarian":1.0,"weightProximity":1.0,"weightTime":1.0,
         "utilNoiseMode":False,"proximityWeights":weights(list(order)),
         "T_max":cheb(s,e)+1,"timeoutMs":600000}
    req.update(extra); return req
if __name__=="__main__":
    import sys
    print(json.dumps(build()))
