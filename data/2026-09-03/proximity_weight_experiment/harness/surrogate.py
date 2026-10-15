"""An exact model of the phase-2 objective, searched by local search instead of Z3.

Why this is legitimate here, and where it stops being legitimate:

  * D = U = 30 dB. The loudest thing reachable on this map is 16 aircraft on a
    45 dB tile, +12.30 dB. So both hard constraints are vacuous for the
    Proportional payload and the feasible set is exactly "every aircraft walks
    from its start to its end in T-1 steps, sticky on arrival".
  * Given the walks, the objective is a pure function of them, and it is the
    SAME function optimize_objectives builds: same integer-scaled dB table, same
    _max_weighted_price normalization, same soft-T penalty and its N*(T-1)
    bound. This module imports those from the solver rather than reimplementing
    them.

So the model is exact and only the SEARCH is heuristic: local search can return
a local optimum where Z3 returns a global one. validate_surrogate.py checks it
against all 30 count-mode routings Z3 already produced, and any conclusion drawn
from here is re-run through Z3 before it is believed.

It buys roughly three orders of magnitude: ~1 s versus ~1000 s a configuration.
"""
import importlib.util as iu
import random
import schemes as sc

spec = iu.spec_from_file_location(
    "S", r"d:/Documents/EECS_199_Shoukry/proximity_noise_experiment/solver_server_dB_noise.py")
S = iu.module_from_spec(spec)
spec.loader.exec_module(S)

REQ = sc.mk.build()
ADJ, BASE, ADB, M = REQ["adjacency"], REQ["baseline"], REQ["aircraftDB"], 25
START, END, MULT = REQ["startPositions"], REQ["endPositions"], REQ["aircraftMultipliers"]
N = len(START)
MW = sum(MULT)


def enum_paths(src, dst, T):
    """All legal walks L[0..T-1] with L[0]=src, L[T-1]=dst, sticky on arrival.

    Returns (cells, t_arr) per path, where cells is the list of (t, station-1)
    the aircraft is ACTIVE on -- first move through first arrival inclusive,
    matching active[i][t] = moved[i][t] AND NOT arrived[i][t-1].
    """
    out = []

    def rec(path):
        t = len(path) - 1
        if path[-1] == dst:                      # sticky: pad and stop
            full = path + [dst] * (T - 1 - t)
            out.append(full)
            return
        if t == T - 1:
            return
        for nb in range(1, M + 1):
            if ADJ[path[-1] - 1][nb - 1]:
                rec(path + [nb])

    rec([src])
    res = []
    for p in out:
        if src == dst:
            continue
        t_fm = next((t for t in range(T) if p[t] != src), None)
        if t_fm is None:
            continue
        t_arr = next(t for t in range(T) if p[t] == dst)
        res.append(([(t, p[t] - 1) for t in range(t_fm, t_arr + 1)], t_arr))
    # dedupe on (active cells, arrival): two walks that differ only after arrival
    # are the same aircraft as far as both objective terms are concerned
    seen, uniq = set(), []
    for cells, ta in res:
        k = (tuple(cells), ta)
        if k not in seen:
            seen.add(k)
            uniq.append((cells, ta))
    return uniq


class Problem:
    def __init__(self, scheme, order, pop, T=5, w_prox=1.0, w_time=1.0, streams=None):
        """streams, if given, is (startPositions, endPositions, multipliers) --
        used to model the split-stream Admin toggle, where each direction is
        carried by two streams at 1/3 and 2/3 of the count rather than by one
        aircraft per flight. Defaults to the individual-mode payload."""
        self.T = T
        self.start, self.end, self.mult = streams if streams else (START, END, MULT)
        self.N = len(self.start)
        self.mw = sum(self.mult)
        pw, extra = sc.build(scheme, order, pop)
        self.int_pw = [round(w * 100) for w in pw]
        self.mode = extra.get("proximityMode", "noise")
        ref = extra.get("proximityNoiseRef")
        table = S.build_scaled_table(M, self.mw, BASE, ADB)
        self.D_count = S._compute_d_counts(M, self.mw, round(REQ["D"] * S.SCALE), table)
        if self.mode == "count":
            self.price = [list(range(self.mw + 1)) for _ in range(M)]
            max_prox = self.mw * T * max(self.int_pw)
        else:
            if ref is None:
                self.price = table
            else:
                row = [round(S.dB_increase(ref, n, ADB) * S.SCALE) for n in range(self.mw + 1)]
                self.price = [row] * M
            max_prox = S._max_weighted_price(self.price, self.int_pw, self.D_count, self.mw, M, T)
        # Exactly the coefficients optimize_objectives forms.
        self.c_prox = w_prox / max_prox
        self.c_time = w_time / (self.N * (T - 1))
        self.paths = [enum_paths(self.start[i], self.end[i], T) for i in range(self.N)]

    def cost(self, choice):
        cnt = [[0] * M for _ in range(self.T)]
        tp = 0
        for i, ci in enumerate(choice):
            cells, ta = self.paths[i][ci]
            tp += ta
            for t, m in cells:
                cnt[t][m] += self.mult[i]
        prox = sum(self.price[m][cnt[t][m]] * self.int_pw[m]
                   for t in range(self.T) for m in range(M) if cnt[t][m])
        return self.c_prox * prox + self.c_time * tp

    def occ(self, choice):
        o = [0] * M
        for i, ci in enumerate(choice):
            for _, m in self.paths[i][ci][0]:
                o[m] += self.mult[i]
        return o

    def solve(self, restarts=30, seed=0):
        """Best-response local search. Ties broken toward the lexicographically
        smallest occupancy vector so two runs that find equally good optima
        report the SAME routing -- otherwise 'distinct routings' would count
        tie-break noise as ranking sensitivity."""
        rng = random.Random(seed)
        N = self.N
        best, best_c, best_ch = None, float("inf"), None
        for r in range(restarts):
            ch = ([0] * N if r == 0 else [rng.randrange(len(self.paths[i])) for i in range(N)])
            cur = self.cost(ch)
            improved = True
            while improved:
                improved = False
                for i in rng.sample(range(N), N):
                    bi, bc = ch[i], cur
                    for k in range(len(self.paths[i])):
                        if k == ch[i]:
                            continue
                        old = ch[i]
                        ch[i] = k
                        c = self.cost(ch)
                        if c < bc - 1e-15:
                            bi, bc = k, c
                        ch[i] = old
                    if bi != ch[i]:
                        ch[i], cur, improved = bi, bc, True
            key = (round(cur, 12), tuple(self.occ(ch)))
            if best is None or key < best:
                best, best_c, best_ch = key, cur, list(ch)
        return {"cost": best[0], "occ": list(best[1]), "choice": best_ch}

    def counts(self, choice):
        """Per-timestep occupancy, which peak and dose need and the summed
        occupancy vector cannot give back."""
        cnt = [[0] * M for _ in range(self.T)]
        for i, ci in enumerate(choice):
            for t, m in self.paths[i][ci][0]:
                cnt[t][m] += self.mult[i]
        return cnt
