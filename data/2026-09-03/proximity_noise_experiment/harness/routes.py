import mkreq as mk
from run import show
full=mk.build()["T_max"]
show("A slack0 1800s (save paths)", mk.build(T_max=full-1, timeoutMs=1800000), "paths_A.json")
