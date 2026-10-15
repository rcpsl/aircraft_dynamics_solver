"""Where is the cliff for mode A? Is it merely slow, or out of reach?"""
import mkreq as mk
from run import show
full=mk.build()["T_max"]
# 1. the server's hard cap on the per-phase budget -- merely slow, or not?
show("A slack0, 1800s budget", mk.build(T_max=full-1, timeoutMs=1800000))
# 2. does it scale down? N is the only knob that is not fixed by the map.
for f,lbl in ((0.5,"50% demand"),(0.25,"25% demand")):
    r=mk.build(demand=f); r["T_max"]=mk.build(demand=f)["T_max"]
    show(f"A {lbl} (N={r['N']}), slack1", r)
