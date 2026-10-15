# Restoring the participant ranking under dB-priced proximity

`proximity_noise_experiment/solver_server_dB_noise.py` prices proximity as
`weight x dB_increase` and, as its own README records, that switches off the
participant ranking: all 28 rankings that solve return ONE routing. This folder
asks whether the ranking can be brought back **without touching the solver** —
by changing only the `proximityWeights` vector the client sends, plus the
already-supported `proximityNoiseRef` field.

Nothing here modifies a solver file. `solver_server_dB_noise.py` and
`solver_server_dB.py` are both untouched.

## The diagnosis, and where the fork's README is imprecise

Re-derived from `proximity_noise_experiment/harness/sweep.jsonl`, not quoted:
28 of 30 rankings comparable, **1 distinct occupancy vector under noise pricing
against 5 under count**, median slowdown 27.7x, 26/28 over the 600 s budget.
Every headline number in that README checks out.

Its *explanation* does not, quite. It says the dB curve "pins traffic to the
floor no matter how the group ranked", implying the ranking has stopped
mattering to the price. It has not:

| | |
|---|---|
| distinct tile price orderings across the 30 rankings, noise pricing | **25** |
| median leverage the ranking has on one tile's weight | **4.3x** |
| median price ratio, 45 dB tiles vs 65 dB tiles, noise pricing | **160x** |
| the same ratio under count pricing | **2.3x** |

The ranking still reorders tiles *inside* a baseline tier. What it can never do
is reorder *across* tiers, because one aircraft adds 3.010 dB at a 45 dB tile
and 0.043 dB at a 65 dB tile. 160 >> 4.3, so the tier ordering is fixed before
the participants say anything, and the routing only ever sees the tier ordering.

Put in the dashboard's own units, this is a double-count with a measurable size.
Tile weights are `5**(sum of rank_weight * score)`. Fitting the dB curve's
implicit gradient to the same form:

| tile baseline | dB curve multiplies price by | equivalent rank weight on `ambient` |
|---|---|---|
| 45 dB | 69.7x | **0.88** |
| 55 dB | 9.6x | **0.94** |

The largest ambient rank weight a participant can choose is **0.40** (0.45 with
Population switched off). So the dB curve applies an ambient preference roughly
**2.2x stronger than the strongest choice available to the group**, in addition
to whatever they chose, and unconditionally. That is the whole failure, and it
is a number, not a vibe.

## Two dials, both client-side

**The weight dial.** `alpha:a` sends `w = w0 / g[m]**a`, where `g[m]` is the
tile's own per-aircraft dB increase. `a=0` is today. `a=1` cancels the implicit
gradient exactly: the price of the first aircraft becomes `w0` again, the
ordering the participant asked for, while each tile keeps its own dB concavity.
`ref:R` instead leaves the weights alone and sets `proximityNoiseRef=R`, pricing
every tile off one baseline — which removes the gradient AND makes the concavity
uniform. R sets the curvature: `dB(45,n)=10log10(1+n)` is strongly concave,
`dB(65,n)` is nearly linear, so `ref:65` should behave close to count pricing.

**The strength dial.** `weightProximity`. At slack 0 the soft-T penalty sits at
44 for every routing, which is exactly the sum of the 16 shortest-path hop
counts — its floor. Since it outvotes proximity 11-14:1 per unit of normalized
range, it behaves as a hard constraint "every aircraft takes a shortest path",
and proximity only breaks ties among those. Raising `weightProximity` is what
would let a ranking BUY A DETOUR rather than merely choose between equal-length
routes.

Measured shares at the returned solution, count mode (`shares.py`):
proximity reaches **5-6%** of its normalized range, the soft-T penalty **68.75%**.
So proximity is heavily outvoted even in the pricing that "works" — the same
pathology `[[objective-binding-strength]]` records for the utilitarian term.

## Method

`solver_server_dB_noise.py` is driven directly (`worker.py`) rather than over
HTTP, because Flask serializes solves behind `_solve_lock` and this needed many
at once. Checked against the Flask path on three saved `sweep.jsonl` runs:
identical occupancy vectors, identical peaks, wall clock 36/38/38 s vs
37/38/39 s.

**The surrogate** (`surrogate.py`) is what makes large sweeps possible. D = U =
30 dB and the loudest reachable tile is +12.30 dB, so both hard constraints are
vacuous for this payload and the feasible set is just "each aircraft walks start
to end, sticky on arrival". Given the walks, the objective is a pure function of
them — and it is the solver's own function: the module imports
`build_scaled_table`, `_max_weighted_price` and `_compute_d_counts` rather than
reimplementing them. The model is therefore exact; only the search (best-response
local search with restarts) is heuristic.

Validated against every Z3 routing that exists:

| | |
|---|---|
| count mode, 30 rankings | 29 identical, 1 tie (surrogate cost <= Z3's), 0 worse |
| noise mode, 28 rankings | **28 identical, 0 different** |

~1 s per configuration against ~1000 s for Z3. Everything the surrogate finds is
treated as a screen and put back through Z3 before it is believed — and the
surrogate says nothing at all about runtime, which is half the decision.

## What the sweeps found

30 rankings (24 permutations of the four factors, plus 6 with Population off),
slack 0, `weightProximity=1`. `routings` is distinct occupancy vectors — the
agreed success metric. Z3 reference points: noise pricing 1, count pricing 5.

| scheme | routings | quiet-tile traffic (median) | total dose (median) | note |
|---|---|---|---|---|
| `base` (today) | **1** | 4 | 19.7 | the lever is dead |
| `alpha:0.1-0.2` | 1 | 4 | 19.7 | too little correction to matter |
| `alpha:0.3-0.5` | 2 | 4 | 19.7 | |
| `alpha:0.6-0.7` | **3** | 4 | 19.7 | |
| `alpha:0.8-0.9` | 4 | 14 | 27.1 | noise advantage starting to go |
| `alpha:1.0` | 5 | 16 | 31.1 | full cancellation — worse than count |
| `alpha:1.2-1.4` | 3 | 16 | 31.1 | over-corrected; diversity falls again |
| `ref:45` … `ref:60` | **4** | 4 | 19.7 | **no weight change at all** |
| `ref:65` | 6 | 5 | 22.4 | identical to count, as predicted |
| `count` | 6 | 5 | 22.4 | today's tractable fallback |
| `alphak:2-4` | 4 | 14 | 27.1 | |

`ref:65` matching `count` exactly is the sanity check that the whole framing is
right: `dB(65,n) = 10log10(1+n/100)` is nearly linear, so pricing every tile off
65 dB reduces the noise term to occupancy. The families meet where they should.

### Why `ref` beats `alpha` at equal correction

With `ref:R` the price factorizes: `price(m,n) = w0[m] * f(n)` for one shared
`f`. The participant's weights therefore apply undistorted at every occupancy
level, and the only thing the dB curve still does is discount stacking.

`alpha:1.0` also cancels the gradient at n=1, but with per-tile curves
`price(m,n) = (w0[m]/g[m]) * dB(baseline[m], n)`, and the SHAPE differs by tile:
`dB` is strongly concave at 45 dB and nearly linear at 65 dB. Stacking on a
quiet tile therefore becomes disproportionately cheap, which is exactly what the
numbers show — quiet-tile traffic goes to 16 and total dose to 31.1, worse than
count on both. Cancelling the gradient tile-by-tile trades one distortion for
another; moving to a shared curve removes it.

### The restored lever is meaningful, not noise

Grouping the 30 rankings by the routing they produce (`meaning.py`), `ref:55`:

| rankings | routing | who ranked what first |
|---|---|---|
| 16 | 4/28/12, peak 4.771 | **all 8 ambient-first**, 5 distance, 3 income |
| 11 | 16/16/12, peak 10.414 | **all 6 population-first**, 3 distance, 2 income |
| 2 | 6/26/12, peak 4.771 | income |
| 1 | 16/16/12, peak 10.414 | income |

Every ranking that puts ambient noise first gets the quiet routing; every one
that puts population first gets the loud one. That is the response structure
`count` produces (15 / 10 / 2 / 1 / 1 / 1 over six routings), recovered under dB
pricing.

### Paired against today's two options

Per-ranking, not median — a scheme that ignores the ranking posts a good median
by overriding everyone, so medians flatter `base` specifically:

| | total dose | peak added dB |
|---|---|---|
| `alpha:0.6` vs `count` | **better 13, tied 17, worse 0** | tied 28, worse 2 |
| `ref:55` vs `count` | better 5, tied 25, worse 0 | tied 28, worse 2 |
| `alpha:1.0` vs `count` | better 2, tied 13, worse 15 | worse 16 |
| `ref:55` vs `base` | tied 16, worse 14 | tied 18, worse 12 |
| `alpha:0.6` vs `base` | tied 18, worse 12 | tied 18, worse 12 |

The rows against `base` are not a defect. `base` is quieter because it overrides
the group; the 12-14 rankings where a corrected scheme is louder are the
rankings whose groups asked for something other than protecting quiet tiles.
Restoring a lever necessarily restores the ability to pull it the other way.

### The strength dial does nothing at these settings

`weightProximity` 1 and 3 give byte-identical results for every scheme. The
soft-T penalty is at its floor of 44 either way, so it still acts as a hard
"take a shortest path" constraint and no detour is bought. (Note
`weightProximity` is a third payload field, beyond the weights-plus-
`proximityNoiseRef` scope agreed for this work — recorded as a measurement, not
proposed as a change.)

### Three controls that make the mechanism hard to argue with

**`ref:65` lands on `count`.** `dB(65,n) = 10log10(1+n/100)` is nearly linear,
so pricing every tile off 65 dB should reduce the noise term to occupancy — and
it does: 6 routings, quiet 5, dose 22.4, the same three numbers `count` gives.
It agrees with `count` on 23 of 30 rankings rather than all 30, and the residual
is a known bug, not a mystery: `build_scaled_table` rounds to integer centi-dB,
which at baseline 65 gives the row [0,4,9,13,17,21] whose marginals run
4,5,4,4,4 — non-monotone, so rounding manufactures a little false convexity.

**The `gamma` family runs the experiment backwards.** `gamma:g` starts from
`ref:45` (gradient removed) and deliberately puts a gradient back at strength
`g`. Routings fall monotonically as it goes in: `gamma:0.25` → 2,
`gamma:0.5` → 1, `gamma:0.75` → 1. Adding the gradient back kills the lever
again, at the strength the mechanism predicts.

**Over-correction is also bad.** Past `alpha:1.0` diversity *falls*:
1.1 → 4, 1.2-1.4 → 3, with quiet-tile traffic stuck at 16 and dose at 31.1.
Inverting the gradient is not better than cancelling it.

### The reference level does not matter to the answer

`ref:45`, `ref:50`, `ref:55` and `ref:60` return **identical routings on all 30
rankings**. Only `ref:65` breaks away (to `count`'s behaviour). So R is free
anywhere in 45-60 and can be chosen purely on tractability.

`ref:55` agrees with `count` on 25 of 30 rankings — it is close to "count's
answer, with the dB stacking discount still applied", which is what the
factorization `price = w0[m] * f(n)` predicts.

### The strength dial, revisited: it helps `ref` but not `base`

`weightProximity` 1 and 3 are identical everywhere. By 10 the term is finally
strong enough to buy detours, and by 30 the best result in the whole sweep
appears:

| scheme | `weightProximity` | routings | quiet | dose |
|---|---|---|---|---|
| `count` | any | 6 | 5 | 22.4 |
| `base` | 1 | 1 | 4 | 19.7 |
| `base` | 30 | **still 1** | 4 | 16.8 |
| `ref:45`-`ref:60` | 1 | 4 | 4 | 19.7 |
| `ref:45` | 30 | **5** | 4 | **16.8** |

So the two dials are genuinely independent. Strength alone cannot revive the
lever — `base` stays at one routing however loudly the term speaks, because the
gradient is inside the term, not outside it. But once the gradient is gone,
strength buys both a fifth routing and a quarter less total noise than `count`.
Note the `ref:45`-`ref:60` equivalence breaks at this setting (5/4/4/4), so R
stops being free once strength is raised.

`weightProximity` is a third payload field, outside the weights-plus-
`proximityNoiseRef` scope agreed for this work, and its Z3 cost is untested.
Recorded as the most promising thing to test next, not as a recommendation.

### It holds at the dashboard's real horizon

Everything above runs at slack 0 (T=5). The dashboard sends slack 1 (T=6), and
that could have mattered a lot: at slack 0 the soft-T penalty is pinned at its
floor of 44 for every routing and cannot discriminate, so proximity is the only
live term. At slack 1 aircraft can arrive late, the penalty varies, and it
outvotes proximity 11-14:1 — so a scheme that restores the ranking at slack 0
could have been overridden at the horizon the workshop actually uses.

It is not. 300 configurations at T=6, `weightProximity=1`:

| scheme | routings | quiet med | dose med | vs T=5 |
|---|---|---|---|---|
| `base` | 1 | 4 | 19.7 | identical |
| `alpha:0.5` | 2 | 4 | 19.7 | identical |
| `alpha:0.6` / `alpha:0.7` | 3 | 4 | 19.7 | identical |
| `alpha:1.0` | 5 | 16 | 31.1 | identical |
| `ref:45` / `ref:55` / `ref:60` | **4** | **4** | **19.7** | identical |
| `ref:65` | 6 | 5 | 22.4 | identical |
| `count` | 6 | 6 | 23.2 | quiet 5 -> 6, dose 22.4 -> 23.2 |

Every corrected scheme is unchanged. The only thing slack 1 moves is `count`,
slightly for the worse — which widens the gap in `ref`'s favour rather than
narrowing it.

### The routings are not tie-break wobble

The surrogate canonicalizes ties, but Z3 does not — it returns whichever optimum
its search reaches first. If a scheme's optimum were highly degenerate, the map a
group sees would be arbitrary among many equally-good answers, and the workshop
notes already flag tie-break wobble as a real phenomenon in this tool. So the
degeneracy was measured directly (`ties.py`, 100 restarts, optima collected):

| scheme | unique optimum | median tied | worst |
|---|---|---|---|
| `base` | 30/30 | 1 | 1 |
| `alpha:0.6` | 30/30 | 1 | 1 |
| `count` | 28/30 | 1 | 4 |
| `ref:55` | 28/30 | 1 | 2 |

Counts are lower bounds (only optima the restarts reached are seen), but the
picture is clear: these optima are essentially unique, so the distinct-routing
counts measure genuine ranking response and a group will get a stable answer.

## The responsiveness ceiling

Worth knowing before reading any of the above as a shortfall: **no scheme
anywhere in the 3360-configuration sweep produced more than 6 distinct routings
from the 30 rankings.** Only `count` and `ref:65` reach 6, at every strength
setting. Eleven distinct routings appear across the whole sweep, but no single
scheme reaches more than six of them.

The ceiling is the map, not the pricing. Three OD pairs on a 5x5 grid, with the
soft-T penalty forcing shortest paths, simply do not admit many distinct optima.
So the participant ranking is a coarse instrument here at the best of times —
30 orderings collapse to at most 6 outcomes — and "restoring the lever" means
getting from 1 back toward 6, not toward 30.

## Files

    schemes.py            the candidate weight vectors; the only place a scheme is defined
    screen.py             free price-landscape pre-screen (no solver)
    surrogate.py          exact model of the phase-2 objective, local-search solved
    validate_surrogate.py surrogate vs every Z3 routing that exists
    surrogate_sweep.py    28 schemes x 30 rankings x 4 strengths, T=5   -> surr.jsonl
    surr_t6.py            10 schemes x 30 rankings at the dashboard's T=6 -> surr_t6.jsonl
    ties.py               how degenerate is each scheme's optimum       -> ties.jsonl
    worker.py             one Z3 solve, calling the solver's two phases directly
    runner.py             parallel scheduler, resumable, per-job wall kill
    orchestrate.py        runs the blocks strictly one at a time
    plan_*.py             job plans
    surr_report.py meaning.py paired.py score.py shares.py timing_report.py   analysis

    python surrogate_sweep.py surr.jsonl 60     # ~1 h, 3360 configurations
    python surr_report.py surr.jsonl            # the headline table
    python runner.py plan_timing.json           # Z3 timing, run this one ALONE

## The runtime wall — and it is the gradient that was holding it up

Z3 timings, run alone at par=8, 900 s cap. 900 s because the decision threshold
is the dashboard's 600 s budget, so anything past it fails with margin.

| configuration | wall | under 600 s |
|---|---|---|
| `count` + split streams | 16 s | yes |
| `count` | 26 s | yes |
| `base` — today's dB pricing | **582 s** | just |
| `ref:65` | >900 s | no |
| `ref:55` | >900 s | no |
| `alpha:0.6` | >900 s | no |
| `ref:55` + `weightTime=0` | >900 s | no |
| `ref:55` + `hardT` | >900 s | no |
| `ref:55` + `D=7` | >900 s | no |
| `ref:55` + `D=7` + `weightTime=0` | >900 s | no |

Two things here, and the second is the important one.

**`ref:65` is the isolation experiment.** Its routing IS `count`'s. Same answer,
26 s versus >900 s. So the ~30x is the dB If-chains in the objective and nothing
about the weights — no reweighting can touch it.

**Correcting the gradient makes the solve HARDER, not easier.** `base` came in
at 582 s; every gradient-corrected scheme blew past 900 s. That is the mechanism
`[[objective-binding-strength]]` already records, seen from a new side:
coefficient spread helps Z3, near-uniform weights create equal-cost plateaus
that are expensive to prove optimal. Cancelling the gradient compresses the tier
separation from 160x to 2.3x — which is exactly the point of the fix, and
exactly what removes the pruning that was making the search finish.

So the tension is not "better answer vs working lever, pick one" as the fork's
README frames it. It is tighter than that: **the 160x gradient is simultaneously
what kills the lever and what makes the problem tractable.** One parameter,
three consequences, and they cannot be separated by reweighting.

Note `base` at 582 s against `sweep.jsonl`'s 1029 s median for the same ranking.
Z3's run-to-run variance at this size is ~2x and is documented; single timings
here are indicative, not precise. The >900 s results are robust anyway — they
are not a 1.7x miss, they are a wall.

### Levers that did NOT work — do not retry these

- `weightTime=0` — the soft-T penalty is a constant 44 at slack 0, so dropping
  it removes a term that was discriminating nothing. It did not help.
- `hardT=true` — drops the penalty and the sticky-arrival implications, but
  enlarges the search space (an arrived aircraft may wander at no noise cost).
  Net: no help.
- `D=7` — shortens the If-chains on 45 dB tiles from 16 branches to 4. It cannot
  shorten them on 55 or 65 dB tiles, which hold all 16 aircraft under any
  plausible D, and that turns out to be where the cost is.
- All of the above combined.

## The lever that does work: split streams

The Admin `streamMode` toggle carries each direction with two streams at 1/3 and
2/3 of the count instead of one aircraft per flight — demand [4,2,2] becomes
N=12 with multipliers 1,3 / 1,1 / 1,1, same total traffic, four fewer location
variables for the optimizer.

| configuration | individual (N=16) | split (N=12) |
|---|---|---|
| `count` | 26 s | **16 s** |
| `alpha:0.6` | >900 s | **350 s** |

350 s is inside the dashboard's 600 s budget. This is the only lever tried that
moved a gradient-corrected scheme across it — after `weightTime=0`, `hardT`,
`D=7` and their combinations all failed.

**And it costs nothing in what the fix was for.** 300 configurations re-swept
with split streams give routing counts identical to individual mode at every
scheme: `base` 1, `alpha:0.5` 2, `alpha:0.6` 3, `ref:45`/`ref:55`/`ref:60` **4**,
`alpha:1.0` 5, `count`/`ref:65` 6 — with the same quiet-tile medians and the same
doses. The only column that moves is `count`'s dose, 22.4 -> 21.1, in its favour.

Carry the caveat: split mode is a coarser physical model, not just a cheaper
encoding. The multiplier-3 stream puts three aircraft on one tile simultaneously
and cannot spread them, which is what made D=5 unsat at a 45 dB destination
([[heavy-stream-destination-trap]]). At Proportional's D=30 that is not in play,
but a future tighter D would bring it back.

## Demand is the lever that actually works

Halving demand ([4,2,2] -> [2,1,1], N=16 -> N=8) makes every corrected scheme
tractable with a large margin, where split streams only rescued `alpha:0.6`:

| scheme | N=16 | N=12 (split) | N=8 (demand x0.5) | N=6 (x0.25) |
|---|---|---|---|---|
| `count` | 26 s | 16 s | — | — |
| `base` | 582 s | — | 74 s | 38 s |
| `alpha:0.6` | >900 s | **350 s** | **48 s** | 52 s |
| `ref:55` | >900 s | >900 s | **62 s** | 56 s |

And the ranking still responds at N=8 — 420 more surrogate configurations:

| scheme | routings | quiet med | dose med |
|---|---|---|---|
| `base` | 1 | 2 | 11.6 |
| `alpha:0.6` | 2 | 2 | 11.6 |
| `ref:45` / `ref:55` / `ref:60` | **4** | **2** | **11.6** |
| `count` | 6 | 2 | 13.0 |

`ref` holds all four routings at half demand while `alpha:0.6` drops from three
to two — the opposite of how they rank on tractability at full demand. So the
two packages below are genuinely different, not two spellings of one answer.

Halving demand is a modelling decision, not an optimization trick: the workshop
would be routing eight aircraft instead of sixteen, and peak added noise falls
from 4.77 dB to 3.01 dB because there is simply less traffic. That has to be an
explicit choice, not something slipped in for solver speed.

## Suggestions

Ranked. All three are payload-only; `solver_server_dB_noise.py` is untouched.

### A. `proximityNoiseRef` at half demand — best overall

    proximityNoiseRef: 55      # any value in 45-60 gives the identical routing
    demand factor:     0.5     # [4,2,2] -> [2,1,1], N=8

- **4 of the 6 routings** the map admits, against 1 today.
- Noise quality equal to today's dB pricing (quiet 2, dose 11.6) and better than
  `count` (13.0).
- **62 s.** A 10x margin under the 600 s budget — far outside Z3's ~2x variance,
  so this one does not rest on a single lucky timing.
- No weight-formula change at all. One request field plus an Admin setting.
- **The cost is modelling 8 aircraft instead of 16**, and peak added noise falls
  4.77 -> 3.01 dB simply because there is less traffic. That is a workshop
  decision about what scenario to present, and it should be made deliberately.

### B. `alpha:0.6` with split streams, at full demand — MARGINAL

    proximityWeights: w0[m] / dB_increase(baseline[m], 1, 45) ** 0.6
    streamMode:       'split'      # N=12, multipliers 1,3 / 1,1 / 1,1

- 3 of 6 routings. Quiet-tile traffic 4 and dose 19.7 — the best noise numbers
  available at full demand, better than `count`'s 22.4 on 13 of 30 rankings and
  worse on none.
- Keeps all 16 aircraft, so the scenario is unchanged.
- **But it does not reliably fit the budget.** Replicated across three rankings:
  **350 s, 512 s, 528 s.** The 350 s that made this look promising was the
  fastest of the three. Two of three sit above 500 s, and with ~2x run-to-run
  variance a 600 s budget will sometimes be missed. Treat this as "usually
  fits, sometimes does not", which for a live workshop means the phase-2
  fallback warning has to be in good shape.

Also tested and rejected here: `ref:55` + split (>900 s on all three rankings —
split rescues `alpha` but not `ref`), and `ref:45` + split + `weightProximity=30`,
the best-on-paper combination, which also fails at >900 s.

### C. Switch Proportional to `count` and drop the dB term

- 6 of 6 routings, 16-26 s, nothing to tune.
- Costs the dB quality: dose 22.4 against 19.7, quiet 5 against 4.
- This is the honest baseline A and B have to beat, and for a workshop that
  values a responsive lever over a marginally quieter map, it may simply win.

### Do not

- **`alpha` >= 1.0.** Full cancellation is worse than `count` on dose (15 of 30)
  and peak (16 of 30). Over-correction past 1.0 also *reduces* routings.
- **`weightTime=0`, `hardT`, `D=7`,** or any combination. All measured, none
  helped; the cost is not where they act.

### The best-on-paper option is out

`weightProximity=30` with `ref:45` is the best pair of numbers anywhere in the
3360-configuration sweep — 5 of 6 routings, dose 16.8, a quarter below `count`.
It was untested when this section was drafted. It has since been run, with split
streams to give it the best chance, and it **times out past 900 s**. Not
available.

## Corrections owed to the existing write-ups

- `proximity_noise_experiment/README.md` and `[[proximity-noise-experiment]]`
  both explain the invariance as the dB curve pinning traffic "no matter how the
  group ranked". The ranking does still reorder tiles inside a baseline tier
  (25 distinct price orderings over the 30 rankings); what it cannot do is
  reorder across tiers. The number that matters is the 160x vs 4.3x comparison,
  and neither document has it.
- Both frame the trade as "better answer vs working lever". It is tighter: the
  same 160x gradient causes the invariance AND supplies the coefficient spread
  that makes the solve finish. Correcting it costs tractability directly —
  `base` 582 s against >900 s for every corrected scheme at full demand.
- The README's open question "whether `proximityNoiseRef` restores ranking
  sensitivity — untested" is now answered: yes, 4 of 6 routings, at both
  horizons, at full and half demand.

## Where the alpha dial runs out

With split streams, full demand, the dashboard's default ranking:

| alpha | routings | quiet-tile traffic | wall |
|---|---|---|---|
| 0.5 | 2 | 4 | 368 s |
| 0.6 | 3 | 4 | 350 / 512 / 528 s (three rankings) |
| **0.7** | **3** | **4** | **452 s** |
| 0.8 | 4 | 14 | 690 s |
| 0.9 | 4 | 16 | >900 s |
| 1.0 | 5 | 16 | >900 s |

Two limits, and they land in the same place. Noise quality holds all the way to
alpha 0.7 and collapses at 0.8 (quiet-tile traffic 4 -> 14, dose 19.7 -> 27.1).
The 600 s budget also breaks at 0.8. **So there is no setting of alpha that buys
the fourth routing without paying both costs at once** — which makes 0.7 the end
of the usable range rather than an arbitrary stopping point.

alpha 0.6 and 0.7 are indistinguishable on routings and quality, and their
timings (350-528 s vs 452 s) overlap inside Z3's variance. Prefer **0.7**: same
answer, and it is the largest correction that still holds quality.

## If you want to keep per-tile added noise

`ref` works by replacing each tile's own dB curve with a shared one. If the added
dB a community actually experiences is the burden you want priced, that is a real
objection, and the question becomes how far the ranking can be restored while every
tile keeps its own curve. Answer: **`alpha:0.7`, 3 of 6 routings, quality fully
intact.**

    proximityWeights[m] = w0[m] / dB_increase(baseline[m], 1, 45) ** 0.7

| | alpha:0.7 | base (today) | ref:55 |
|---|---|---|---|
| routings of 6 | **3** | 1 | 4 |
| quiet-tile traffic | 4 | 4 | 4 |
| dose | 19.7 | 19.7 | 19.7 |
| Z3, half demand | **144 s / 278 s** | 74 s | 62 s |
| Z3, full demand + split | 452 s (marginal) | 582 s | >900 s |

At 0.7 roughly 8x of the original 70x ambient gradient is left standing and the rest
of the decision goes to the participants. At half demand the window widens: 0.7, 0.75
and 0.8 all give 3 routings at full quality, where at full demand anything >= 0.75
costs the noise advantage.

### Why it stops at 3, and why that is structural

The distortion is not one number per tile, it is a different curve SHAPE per tile —
dB climbs steeply then flattens at 45 dB and is nearly linear at 65. A weight is one
number per tile, and one number cannot cancel a shape; it can only be exact at one
occupancy and drift elsewhere. `alpha:1.0` is exact at one aircraft, which is why it
over-corrects as soon as two or three share a tile.

So the natural generalization was built and tested: **`geo:K`**, the least-squares fit
of each tile's curve to a shared shape over occupancies 1..K. Working the normal
equations through, the answer is to divide by the GEOMETRIC mean of the tile's dB
increase over that range, and `alpha:1.0` is the K=1 case.

It does not escape the dial:

| scheme | routings | quiet | dose |
|---|---|---|---|
| `geo:2` | 5 | 16 | 31.1 |
| `geo:3` | 4 | 15 | 29.1 |
| `geo:4`, `geo:6` | 4 | 14 | 27.1 |
| `alpha:0.75`, `alpha:0.8` | 4 | 14 | 27.1 |
| `geoa:3_0.7` (fit applied at 70%) | 3 | 4 | 19.7 |

Every variant lands on the same trade-off line as high alpha — the 4th routing is
bought by pushing quiet-tile traffic 4 -> 14-16, never for free. `geo` is a
reparameterization of the one-dimensional dial, not a second axis. 780 configurations,
full and half demand (`surr_keepdb.jsonl`).

**So the choice is a values choice, not a tuning problem.** Price the dB each community
actually experiences and take 3 of 6; or treat the weights as the whole statement of who
deserves protection, let the dB curve supply only the stacking discount, and take 4.

## Widening the ranking's own spread (PROX_BASE) — the second knob

Raising the dashboard's `PROX_BASE` from 5 to B is exactly raising every weight to
the power ln(B)/ln(5): no tile is reordered, the gaps between them stretch. Today's
weights span 56x; base 10 spans 316x, base 25 spans 3125x, base 125 spans 175000x.
All stay under the solver's 1e7 weight guard.

**It is the safe knob.** alpha distorts how price grows with occupancy, which is why
quality collapses past 0.7. A base change is a per-tile constant — identical at one
aircraft and at four — so it cannot distort the dB curve at all. Confirmed: dose 19.7
and quiet-tile traffic 4 for EVERY member of the pow family at full demand, and 11.6 / 2
at half. It never costs quality, at any base.

**But alone it is weak.** Full demand: base 10 gives **1** routing (no change at all),
base 25 gives 2, base 125 gives 3. The reason is that `ambient` is one of the four
ranked factors, so the weights already contain a term agreeing with the implicit
gradient — stretching them amplifies both sides of the argument at once.

**Combined with a partial alpha it reaches ref's routing count while keeping per-tile
dB pricing:**

| half demand, per-tile dB kept | routings | quiet | dose | Z3 |
|---|---|---|---|---|
| `base` (today) | 1 | 2 | 11.6 | 74 s |
| `alpha:0.7` | 3 | 2 | 11.6 | 144 / 278 s |
| `pow:125` | 2 | 2 | 11.6 | 92 / 98 s |
| **`powa:25_0.7`** | **4** | **2** | **11.6** | **120 / 134 / 162 s** |
| `ref:55` (shared curve) | 4 | 2 | 11.6 | 62 s |

### CORRECTION to the section above

The previous section concluded that keeping per-tile dB caps you at 3 routings and that
the gap to 4 is structural. **That is wrong.** It is capped at 3 if the weight formula is
the only thing changed AT ITS CURRENT BASE. Widen the spread as well and 4 is reachable
with per-tile pricing and full quality (`powa:25_0.7`, and `powa:10_0.7` at full demand).
The "one number cannot cancel a curve shape" argument still holds — it explains why the
alpha and geo families share one dial — but it does not bound what a SECOND, independent
knob can reach, and the geo experiment was not evidence about that.

### Spread also helps tractability — the only change measured that does

Every other fix here destroyed coefficient spread to restore the ranking, and paid for it
in Z3 time. This one adds spread:

| scheme | full demand | split N=12 | half demand |
|---|---|---|---|
| `base` | 582 s | — | 74 s |
| `ref:55` | >900 s | >900 s | 62 s |
| `alpha:0.6` | >900 s | 350-528 s | 48 s |
| `pow:25` | 744 s | — | — |
| `pow:125` | **632 s** | **376 s** | **92 / 98 s** |
| `powa:10_0.7` | >900 s | >900 s | 146 / 164 s |
| `powa:25_0.7` | — | — | **120 / 134 / 162 s** |

`pow:125` at 632 s at FULL demand is the only gradient-affecting scheme that comes near
`base`'s 582 s; the ref and alpha families are all past 900 s there. Consistent with
[[objective-binding-strength]]: spread is what Z3 prunes with.

### The caveat that is not technical

A base change alters what the weights MEAN. At base 25 a community the group ranked
"protect hard" becomes thousands of times more expensive than one they did not, rather
than tens. Same four factors, same 0.40/0.30/0.20/0.10 shares, same ordering — but a far
more emphatic statement of preference, and one nobody in the workshop chose. It belongs in
the same category as halving demand: a design decision to be made deliberately.

Sweeps: `surr_pow.jsonl` (720 configs), timings `pow.jsonl` / `pow2.jsonl`.
