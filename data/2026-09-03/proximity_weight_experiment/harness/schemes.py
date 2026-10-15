"""Candidate proximityWeights schemes.

Every scheme here is client-side: it changes only the ranking -> proximityWeights
mapping and (for the ref family) the existing proximityNoiseRef request field.
solver_server_dB_noise.py is NOT modified by anything in this folder.

Vocabulary
----------
w0[m]  the dashboard's current weight, PROX_BASE**(sum of rank_k * score_k(m))
g[m]   dB_increase(baseline[m], 1, 45) -- what ONE aircraft adds at tile m.
       3.010 dB at a 45 dB tile, 0.414 at 55, 0.043 at 65: a 70x implicit
       gradient that the participant's ranking never sees.

Under noise pricing the tile price is w[m] * dB(count). At count 1 that is
w[m]*g[m], so the current scheme prices every 45 dB tile ~70x above every 65 dB
tile before the ranking says anything -- which is why all eight 45 dB tiles sit
at the top of the price order under all 30 rankings.

alpha family: w = w0 / g**alpha.  alpha=0 is today's behaviour, alpha=1 cancels
the gradient exactly at count 1 (price == w0, same ordering the participant
asked for) while keeping each tile's own dB concavity.

ref family: weights untouched, proximityNoiseRef=R prices every tile off one
baseline. That removes the gradient completely AND makes the concavity uniform.
Note R also sets how curved the shared price row is: dB(45,n)=10log10(1+n) is
strongly concave, dB(65,n)=10log10(1+n/100) is nearly linear, so ref=65 should
behave close to count mode and ref=45 keeps the strongest 'stacking is cheap'
incentive.

gamma family: ref=45 (uniform strong concavity) with the gradient deliberately
re-introduced at a chosen strength, w = w0 * g**gamma. Lets the ambient gradient
be a tuned design choice rather than a 70x side effect of the dB curve.
"""
import math, sys
sys.path.insert(0, r"d:/Documents/EECS_199_Shoukry/proximity_noise_experiment/harness")
import mkreq as mk

BASELINE = mk.build()["baseline"]
AIRCRAFT_DB = 45.0
M = 25


def dbinc(b, n, a=AIRCRAFT_DB):
    if n <= 0:
        return 0.0
    return 10 * math.log10(10 ** (b / 10.0) + n * 10 ** (a / 10.0)) - b


G1 = [dbinc(BASELINE[m], 1) for m in range(M)]


def _geomean(xs):
    import math
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


# Cache: geometric mean of a tile's own dB increase over occupancies 1..K.
_GEO = {}


def geo_divisor(K):
    """Why the GEOMETRIC mean, and not the n=1 value the alpha family uses.

    Keeping per-tile dB pricing means the price of tile m at occupancy n is
    w[m] * dB(baseline[m], n). What makes the ranking work is that price being
    w0[m] * f(n) for ONE shared f -- then the participant weight is the only
    thing that varies tile-to-tile and it decides. With per-tile curves that is
    not exactly achievable, so fit it: choose w[m] minimising the squared log
    error between w[m]*dB(baseline[m], n) and w0[m]*f(n) over n = 1..K.

    Setting the derivative to zero gives, after the shared-f terms cancel as a
    constant,
        w[m]  proportional to  w0[m] / geomean(dB(baseline[m], n) for n in 1..K)

    alpha:1.0 is the K=1 case -- it matches the shared curve at exactly one
    aircraft and drifts everywhere else, which is why it over-corrects. Larger K
    trades exactness at one aircraft for a better fit across the occupancies that
    actually occur.
    """
    if K not in _GEO:
        _GEO[K] = [_geomean([dbinc(BASELINE[m], n) for n in range(1, K + 1)])
                   for m in range(M)]
    return _GEO[K]


def _rescale(w):
    """Scale the vector so its max matches the current scheme's max.

    Cosmetic by construction: eff_w_prox = w_prox / max_proximity and
    max_proximity is linear in int_pw (the knapsack DP sums w*row), so a common
    factor cancels out of the objective exactly. Done anyway to keep int_pw in
    the same numeric range across schemes, so nothing differs by P_SCALE
    rounding or by the 1e7 weight guard.
    """
    mx = max(w)
    return w if mx <= 0 else [x * (90.6 / mx) for x in w]


def weights_for(order, pop):
    o = list(order) if pop else [f for f in order if f != "population"]
    return mk.weights(o)



def weights_base(order, pop, B):
    """The dashboard's weight formula with PROX_BASE swapped from 5 to B.

    Identical to raising every weight to the power ln(B)/ln(5), because
    B**x == (5**x)**(ln B / ln 5) -- so this stretches the spread between tiles
    without reordering any of them. Recomputed from the scores rather than
    exponentiating w0, to avoid compounding mkreq's 4-decimal rounding.

    The point of trying it: the implicit ambient gradient is a FIXED ~70x, so a
    wide enough weight spread could in principle outrun it. The catch is that
    `ambient` is itself one of the four ranked factors, so stretching the weights
    stretches the part of them that already agrees with the gradient too.
    """
    o = list(order) if pop else [f for f in order if f != "population"]
    rw = mk.RANKW if len(o) == 4 else mk.RANKW_NOPOP
    wts = dict(zip(o, rw))
    out = []
    for i, (b, pop_a, inc, _) in enumerate(mk.rows):
        bb = b if b is not None else 55
        sc_ = {"income": mk.INC.get(inc, mk.S / 2),
               "ambient": max(0, min(1, (65 - bb) / 20)) * mk.S,
               "distance": mk.ring(i),
               "population": mk.POP.get(pop_a, mk.S / 2)}
        out.append(B ** sum(wts.get(k, 0) * v for k, v in sc_.items()))
    return out


def build(scheme, order, pop):
    """-> (proximityWeights, extra request fields)"""
    w0 = weights_for(order, pop)
    fam, _, arg = scheme.partition(":")

    if fam == "base":                       # today's behaviour, noise pricing
        return w0, {}
    if fam == "count":                      # today's behaviour, occupancy pricing
        return w0, {"proximityMode": "count"}
    if fam == "ref":                        # weights untouched, one shared dB curve
        return w0, {"proximityNoiseRef": float(arg)}
    if fam == "alpha":                      # cancel the implicit gradient
        a = float(arg)
        return _rescale([w0[m] / (G1[m] ** a) for m in range(M)]), {}
    if fam == "alphak":                     # cancel at an expected occupancy of k
        k = int(arg)
        gk = [dbinc(BASELINE[m], k) / k for m in range(M)]
        return _rescale([w0[m] / gk[m] for m in range(M)]), {}
    if fam == "pow":                        # the ranking formula on a bigger base
        return weights_base(order, pop, float(arg)), {}
    if fam == "powref":                     # bigger base AND the shared curve
        B, R = arg.split("_")
        return weights_base(order, pop, float(B)), {"proximityNoiseRef": float(R)}
    if fam == "powa":                       # bigger base AND a partial alpha correction
        B, a = arg.split("_")
        wb = weights_base(order, pop, float(B))
        return _rescale([wb[m] / (G1[m] ** float(a)) for m in range(M)]), {}
    if fam == "geo":                        # least-squares fit to a shared curve shape
        K = int(arg)
        gk = geo_divisor(K)
        return _rescale([w0[m] / gk[m] for m in range(M)]), {}
    if fam == "geoa":                       # the same fit, applied only fractionally
        K, a = arg.split("_")
        gk = geo_divisor(int(K))
        return _rescale([w0[m] / (gk[m] ** float(a)) for m in range(M)]), {}
    if fam == "gamma":                       # uniform curve + a chosen gradient
        gm = float(arg)
        return _rescale([w0[m] * (G1[m] ** gm) for m in range(M)]), {"proximityNoiseRef": 45.0}
    raise ValueError(f"unknown scheme {scheme!r}")
