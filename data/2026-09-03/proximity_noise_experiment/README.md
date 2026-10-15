# Proximity priced as weight x added noise

> **THIS EXPERIMENT SHIPPED on 2026-09-03.** `solver_server_dB.py` — production, port
> 5051 — now prices Proportional as `weight x added noise`. It is the default: a
> request that sends no `proximityMode` gets the dB term. `proximityMode: "count"`
> reproduces the old `weight x occupancy` behaviour, and `proximityNoiseRef` is there
> too; both replies carry `proximityMode` back so a stored result says which priced it.
> The lexicographic control in `../lex_objective_experiment/` was patched with the same
> script, so it has not drifted.
>
> The direction of this folder is therefore **inverted**, as it is for the lex
> experiment. `solver_server_dB_noise.py` no longer holds the experimental arm — it is
> a snapshot of the arm as it was measured, and it is now BEHIND production: it forked
> before the lexicographic objective and the best-so-far salvage landed, so do not
> deploy it or diff it as if it were current. Production is the live copy of this idea.
>
> **The decision the section below calls open has been made, and it was made against
> the numbers below rather than in ignorance of them.** Everything from here down is
> preserved as written before the decision. Read "not in production" as "was not, at
> the time of writing"; the measurements themselves still stand, including the ~28x
> runtime cost and the loss of ranking sensitivity, which are now things production
> does. `../proximity_weight_experiment/NOTES.md` diagnoses the ranking loss and
> measures the payload-only levers (`proximityNoiseRef` + half demand, `alpha`,
> `PROX_BASE`) that claw some of it back without touching the solver.
>
> ### One claim below DOES need re-reading: "never a louder peak"
>
> That was measured letting the noise runs finish. **At the dashboard's 600 s budget
> they do not finish**, and production — unlike this fork — salvages the incumbent and
> serves it as `optimality: "partial"` rather than reporting a timeout. Measured on the
> merged production solver, full demand N=16, T_max=6, default ranking, 600 s:
>
> | mode | peak | prox | optimality | wall |
> |---|---|---|---|---|
> | noise (the shipped default) | **+6.99 dB** | 378.08 | partial | 604 s |
> | noise, the SAME payload again | **+11.14 dB** | 436.61 | partial | 604 s |
> | noise, `proximityNoiseRef: 55` | +9.03 dB | 168.20 | partial | 604 s |
> | count | **+4.77 dB** | 367.56 | **optimal** | 67 s |
>
> The shipped default is 2.2-6.4 dB LOUDER than the term it replaced, and moves 4.15 dB
> between two runs of one input. At 25% demand the inversion repeats: count +3.01 dB
> optimal in 6 s against noise's +4.77 dB partial. **A partial dB answer is not a better
> answer, it is an arbitrary one.** The fork could not have seen this — with no salvage
> path it recorded these runs as outright fallbacks.
>
> Why the peak runs free: Proportional sends D = U = 30, which nothing on this map
> approaches, so the hard cap never binds and the peak is governed ENTIRELY by the
> objective. An unconverged objective means an uncontrolled peak. The salvaged routing
> is still verified feasible; feasible is just not the same as quiet here.
>
> So the tables further down describe what this term does **when it converges**. Getting
> that in a live session needs `timeoutMs` near 1800 s, or fix A from
> `../proximity_weight_experiment/NOTES.md` (`proximityNoiseRef` 45-60 at half demand,
> 62 s), or `proximityMode: "count"`.

## What the fork changes

`solver_server_dB_noise.py` is a copy of the production solver **as it stood on
2026-08-25** with three differences, plus a port change (5052, so both can run at once):

| | |
|---|---|
| objective | `Sum_t Sum_m dB_increase(m, count) * weight[m]` instead of `count * weight[m]` |
| `proximityMode` | `"noise"` (default here) or `"count"` (reproduces production exactly) |
| `proximityNoiseRef` | optional: price every tile off ONE ambient level instead of its own |
| normalization | `_max_weighted_price`, an exact knapsack DP, replaces the `sum(mult)*T*max_w` product |

## The case that was open before it shipped

*(Retitled from "Why it is not in production", which is no longer true. The argument
below is unchanged and is still the argument — it is what the decision was made
against, not what the decision refuted.)*

Short version: **the dB version gives a better answer, but it takes ~28x longer to get
there and the participants can no longer change it.**

That is a trade, not a defect. It has not shipped because the trade has not been
decided, not because the dB term is broken.

- **Better:** it never makes the loudest tile louder, and in 11 of 28 rankings it makes
  it 4.8-5.6 dB quieter. It never puts more traffic over quiet neighbourhoods.
- **Slower:** ~28x. 26 of 28 runs blow past the dashboard's 600 s budget.
- **Fixed:** it returns the SAME routing whatever the group ranks first. The ranking is
  the only lever Proportional gives participants, and this switches it off.

All of it comes from the 30-ranking sweep (`harness/sweep.py` -> `sweep.jsonl`; all 30
rankings, both pricings). None of it was visible in the single instance this section
originally reported.

### Runtime, 28 rankings where both pricings returned sat

| | occupancy (`count`) | added noise |
|---|---|---|
| median wall | **38 s** | **1029 s** |
| mean | 37 s | 1035 s |
| range | 17-47 s | 308-1556 s |
| over the dashboard's 600 s budget | 0 / 28 | **26 / 28** |

Per-ranking slowdown: **median 27.7x, mean 29.5x, range 8.1x to 65.6x.** The two
remaining rankings of the 30 (`population|ambient|distance|income` and
`distance|ambient|income|NOPOP`) had phase 2 fall back entirely under noise pricing
after ~1800 s, while count solved them in 34 s and 45 s.

CORRECTION: this section used to claim "6-12x slower". That came from dividing the
noise runs at slack 0 by the *count* run at slack **1** - different horizons, so the
comparison was never valid. Against its own matched slack-0 baseline the same two
numbers are 14.9x and 26.7x, and against the full sweep the answer is 27.7x median.
Do not requote 6-12x.

### What you gain: a better answer

Scored on the numbers people actually look at. Both routings, same 28 rankings.

**Peak added noise** - the dashboard's headline figure:

| what occupancy gives | what dB gives | how often |
|---|---|---|
| +4.77 dB | +4.77 dB | 17 rankings (same) |
| +9.54 dB | +4.77 dB | 2 rankings (**4.77 dB quieter**) |
| +10.41 dB | +4.77 dB | 9 rankings (**5.64 dB quieter**) |

Never worse, in any of the 28. Better in 11. Average gain 2.15 dB.

**Traffic over quiet (45 dB) neighbourhoods**, aircraft-timesteps out of 44:

| | what the 28 rankings produced |
|---|---|
| occupancy | 4 in fourteen rankings, 7 in one, 8 in two, 16 in eleven |
| added noise | **4 in all twenty-eight** |

4 is the floor - Community is a 45 dB endpoint for four aircraft, and an aircraft still
counts on the timestep it lands, so those four cannot be moved. dB pricing hits that
floor every time. Occupancy pricing sometimes puts four times as much there.

Neither objective optimizes peak directly, so both of these are side effects. But this
is NOT the arbitrary tie-break wobble documented in the workshop notes: wobble would
show spread on both sides, and the dB arm returned +4.77 dB with **zero** variance
across all 28 runs. It is systematic.

### What you lose: the participants stop being able to change it

The same table read the other way. Occupancy pricing produced four different burden
outcomes and three different peaks across the 30 rankings. dB pricing produced one of
each, every time.

The dB curve makes quiet tiles so expensive that the objective pins traffic to the floor
no matter how the group ranked income, ambient, distance and population. **The ranking is
the only lever Proportional gives participants, and this switches it off.**

There is also a cost on production's own metric. Score the dB routing the way production
scores things (occupancy x weight): it is **worse in 13 of 28 rankings and tied in the
other 15 - better in none**. When worse: +0.4% at best, +7.4% median, +17.3% at worst.
That is the arithmetic of the trade - the dB routing buys a quieter peak by accepting
more total weighted occupancy.

### So which is right?

This is a genuine values question, which is what the tool exists to surface:

- If the workshop is about **getting the best noise outcome**, dB pricing wins. It is
  quieter or equal every time, and it never loads quiet neighbourhoods more than it has
  to.
- If the workshop is about **participants exercising a choice and seeing it matter**,
  occupancy pricing wins, because under dB pricing their ranking changes nothing.

Nobody has decided. Do not read this file as saying the dB term failed - it did not. It
does its job well and costs 28x and the group's agency to do it.

NOT MEASURABLE from the saved sweep: how much better the dB routing is on its OWN
objective. `sweep.jsonl` stores occupancy summed over timesteps, and dB(count) is
non-linear per timestep, so the detail needed to score the occupancy routing under the dB
objective is gone. It is better by construction; the size of the gap would need a re-run.

### The earlier single-instance measurement, kept for context

Measured on the 5x5 dashboard's real Proportional payload (N=16, M=25, D=U=30,
default factor ranking, aircraft 45 dB):

| term | horizon | result | wall |
|---|---|---|---|
| count | slack 1 (T=6) | sat, peak +4.77 dB | 82 s |
| count | slack 0 (T=5) | sat, peak +4.77 dB | 36 s |
| noise A (per-station) | slack 0 | phase-2 TIMEOUT at 600 s | - |
| noise A | slack 0, 1800 s budget | sat, peak +4.77 dB | 960 s, then 536 s on a rerun |
| noise B (ref 55 dB) | slack 0 | phase-2 TIMEOUT at 600 s | - |
| noise A, 50% demand (N=8) | slack 1 | sat, peak +3.01 dB | 569 s |
| noise A, 25% demand (N=6) | slack 1 | sat, peak +3.01 dB | 378 s |

Note the 960 s / 536 s spread on identical input - Z3's search varies a lot at this
size, so a single timing is not a reliable ceiling. Two rows here have since been
contradicted by repeated measures and should not be quoted: the 82 s for count at
slack 1 was one sample, and a 3-rep run against production later gave 50 / 51 / 51 s;
the 36 s for count at slack 0 sits inside the sweep's 17-47 s range and is fine.

Routing comparison, count vs noise A at slack 0 (`harness/burden.py`, from saved paths):

    aircraft-timesteps by baseline tier
      45 dB tiles (n= 8): count=  4   noise A=  4
      55 dB tiles (n=12): count= 28   noise A= 28
      65 dB tiles (n= 5): count= 12   noise A= 12

Station-by-station identical. **One instance, one ranking** - and the sweep has since
answered the question that caveat left open. Across the 28 rankings where both
pricings solved, the routings are identical in **14** and differ in **14**. The
default ranking happens to be one of the identical ones, which is why this instance
showed nothing.

The predicted equity inversion DID show up, in exactly those 14 rankings. In every one
of them, count pricing put more burden on 45 dB tiles (7, 8 or 16 aircraft-timesteps)
and noise pricing pulled it back to the floor of 4, shifting it onto 55 dB tiles.
65 dB burden stayed at 12 in all 28 - the loud tiles are already saturated, so the
inversion shows up as quiet-to-middling rather than quiet-to-loud. The sentence that
used to sit here ("did NOT show up") was generalized from the one instance above and
is wrong.

## Why the noise term is so much slower

Three compounding reasons, in rough order of importance.

1. **The objective stops being linear.** `Sum(count * weight)` is a linear integer
   expression, which `z3.Optimize` handles with its LIA/simplex machinery. The dB
   version is 25 x 5 = 125 nested If-chains, each up to 16 branches deep - roughly
   2000 case-splits inside the objective. Branch-and-bound has to do case analysis
   where it previously did arithmetic.

2. **The objective stops being separable.** `Sum_t Sum_m count[t][m] * w[m]` equals
   `Sum_i mult_i * Sum_t w[tile_i(t)]` - each aircraft's cost depends only on its own
   path, so the optimum is just "every aircraft takes its cheapest weighted path" and
   aircraft never interact. `dB(count)` is a function of the SUM over aircraft, so
   moving one aircraft changes every other aircraft's marginal cost on that tile. The
   optimizer now reasons about joint occupancy instead of independent choices.

3. **Proportional's wide D makes the chains maximal.** Proportional sends D = U = 30,
   which nothing on this map approaches (the loudest reachable increase is 12.30 dB).
   So `_compute_d_counts` returns 16 for every station and every If-chain runs its full
   16 branches. A principle with a tight D (Equal/Sufficientarian at 5-10 dB) would get
   3-4 branch chains and the same term would be far cheaper. The cost is specific to
   the principle that uses the term.

Note the If-chains already exist in production - `_add_noise_constraints` builds them
for the D/U caps. Cheap there, because they are only *constrained* (2M+1 propagations
per timestep). Putting them in the *objective* is what costs.

## The double-counting concern (the mechanism, now observed)

The 5x5 dashboard prices ambient noise explicitly, as one of four participant-ranked
factors, worth at most 6.9x. Pricing added noise re-introduces ambient implicitly at
70x (one aircraft adds 3.01 dB at a 45 dB tile, 0.043 dB at a 65 dB tile), pointing the
same direction and unaffected by the participant's ranking. On paper that sorts all
five 65 dB tiles to the bottom of the price order - including Underdeveloped
Neighborhood and Industrial Center, both low-income, both deliberately made expensive
by the Income factor.

It did not happen in the single run measured above, because that ranking's OD pairs and
T=5 leave the routing very little freedom. The sweep found it does happen: in 14 of 28
rankings the baseline gradient pulled burden off 45 dB tiles regardless of what the
participants had ranked, and in ALL 28 the ranking lost the ability to move that burden
at all. This section is no longer a worry about what might happen - it is the mechanism
behind both results at the top of this file.

Note the same mechanism produces the gain and the loss. It moves traffic off quiet tiles
(good - that is the 4.8-5.6 dB peak improvement) and it does so with a force no ranking
can overcome (bad - that is why the lever stops working). You cannot keep one and drop
the other by tuning; they are the same effect seen from two sides.

`proximityNoiseRef` remains the way to isolate it: it keeps the concavity but removes
the baseline gradient. It has not been run across the sweep, only on the single
instance in the table above, so whether it restores ranking sensitivity is untested.

## Running it

    python harness/serve.py          # port 5052, reloader off
    python harness/run.py            # count vs noise A vs noise B
    python harness/sweep.py          # all 30 rankings x both pricings -> sweep.jsonl
    python harness/analyze.py        # summarize sweep.jsonl
    python harness/diag.py           # where the time cliff is
    python harness/burden.py         # offline: compare saved routings

`sweep.py` is resumable: it appends to `sweep.jsonl` and skips keys already recorded
there, so an interrupted run continues rather than restarting. It is also the only
harness script here that takes ~9 hours.

`harness/mkreq.py` reconstructs the dashboard's `buildSolveRequest()` for the
Proportional principle, so the payloads are the real ones, not synthetic.

## Open

- Sound speedups not yet tried: prune stations unreachable within T from the objective
  sum; tighten the If-chain length below D_count. Worth doing - a 28x speedup would
  remove one of the two costs entirely and leave a clean question: do you want the
  better answer or the working lever? Right now you are being asked to pay both.
- THE DECISION ITSELF. Nobody has chosen between "best noise outcome" (dB) and
  "participants can steer it" (occupancy). Everything else here is measurement; this
  is the only genuinely open question, and it is not a technical one.
- ANSWERED: "whether any ranking / map makes the two terms actually diverge" - yes,
  14 of 28 rankings on this map. See the sweep section above.
- Still open: whether removing `ambient` from the ranked factors (the frontend half of
  the change this fork exists to enable) restores any ranking sensitivity under noise
  pricing. The remaining factors - income, distance, population - do not track baseline
  directly, so it is not obviously hopeless, but the sweep above was run with ambient
  still in and cannot settle it.
- ~~`proximityMode` defaults to `"noise"` HERE because that is what this fork exists to
  test. Production has no such flag at all.~~ SUPERSEDED 2026-09-03: production now has
  the flag and defaults it to `"noise"` as well, so this fork and production agree on
  the default. What still differs is everything the fork is missing — the lexicographic
  objective and the best-so-far salvage.
