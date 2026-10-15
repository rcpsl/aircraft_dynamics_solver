# lex_objective_experiment

> **THIS EXPERIMENT SHIPPED on 2026-08-27.** `solver_server_dB.py` — production, port
> 5051 — now minimizes the chosen principle first and arrival time only as a tie-break.
> `OBJECTIVE_MODE` there reads `"lex"`.
>
> The direction of this folder is therefore **inverted**. It no longer holds the
> experimental arm; it holds the **control**: `solver_server_dB_weighted.py` on port
> 5056 is the older single-weighted-sum scheme, kept so every measurement below stays
> reproducible and so there is a no-code-change fallback if the adoption turns out to
> hurt in a live session. Everything below is the evidence that justified the switch,
> and is preserved as written.

The control differs from production in exactly **four places**: the header, the
`OBJECTIVE_MODE` constant, the `minimize()` block, and the port it binds to. Nothing
else — the whole API, the phase-2 messaging and the best-so-far salvage are identical,
so the dashboard can be pointed at either without knowing which it got and
`objectiveMode` in the reply says which answered.

**Do not let the two drift.** When shared behaviour changes, patch both with one
script, or the control stops being a control.

```
harness/serve_any.py <prod|weighted> <port>
```

`prod` loads production (lex); `weighted` loads the control. `lex` is still accepted as
an alias for `prod`, since that is what production now runs, so the old command lines in
the log files here still do what they say. The three hardcoded single-port launchers
(`serve.py`, `serve_prod.py`, `serve_prod_alt.py`) were deleted — one of them pointed at
the pre-rename filename and would now fail. Never bind 5051; another session usually owns
it. `test9_perf.py` used 5056/5057 for Proportional and 5058/5059 for Utilitarian, four
servers at once, so neither arm got the quiet machine.

Throughout the rest of this file, **"lex" means what production now does** and
**"production" means the weighted scheme that is now the control** — the names were
written while the experiment was still an experiment.

## The change that shipped: lexicographic objectives

```python
if objective_terms:
    opt.minimize(Sum(objective_terms))   # principle tier
if T_penalty is not None:
    opt.minimize(T_penalty)              # tie-break tier, strictly subordinate
```

Production folds `eff_w_time * T_penalty` into the same weighted sum as the
principle. Each term is divided by a theoretical max before weighting, and those
divisors are loose by very different amounts, so the nominal weights do not mean what
they say. Measured on the 5x5 map (`harness/out_test4_terms.txt`, Utilitarian +
People): the utilitarian noise term reached **2.2%** of its own normalized range
while the time penalty reached **68.8%** of its. Time outvoted the principle roughly
**31:1**.

(Earlier drafts of this file, the fork's header docstring and the memory note all
said 1.6% / ~80% / 50:1. Those predate `test4` and are wrong. 68.8% is also the
*highest* share the time term reached in any of the four configurations test4
measured — the fourth, Prioritarian + Communities, put it at 55.0% — so "~80%" was
never observed at all.)

Z3's `Optimize` defaults to `priority='lex'` and applies objectives in call order, so
splitting them makes the time tier choose only among routings that already achieve
the principle's optimum. It cannot cost a single unit of fairness.

The principle tier stays a *weighted sum* rather than splitting further, because the
People toggle sets `optimizeUtilitarian` alongside `optimizeProximity`/`Prioritarian`
and the 1.0-vs-0.3 trade between them is a deliberate dashboard choice. Only time is
demoted.

Consequences: `w_time` no longer sets a magnitude, only whether the tie-break runs at
all; `max_T_penalty` goes unused; and with a single principle term live its weight
becomes mathematically irrelevant — scaling it cannot move the argmin. That last one
is the sharpest available test that lex is actually in effect (`test1_lex.py`, §2).

### Status: completes on four of five principles; Utilitarian is the open question

`test5_api_shape.py`, both arms run concurrently so the times are like-for-like:

| principle | lex | production |
|---|---|---|
| Proportional | 190s, proven optimal | 138s, proven optimal |
| Prioritarian | **88s**, proven optimal | 170s, proven optimal |
| Equal | 45s | 43s |
| Sufficientarian | 47s | 53s |

Every probe **in the two sections above** returned `arrivalPenalty = 44` on both
arms — the same arrival sum production's weighted answer reaches — so on these
principles the tie-break tier does its job and lex is not paying for the split in
arrivals. This does **not** hold across all of `test5`: its §3 salvage probe, a
deliberately-starved 60s budget on Utilitarian + People, returned 63 on lex and 62 on
production. A partial result has not finished paying down its arrival sum.

On Prioritarian lex was faster in both runs that measured it (88s vs 170s here, 34s
vs 65s in `test1`). Proportional is the opposite and consistently so: lex was slower
by ~1.4× in all three independent measurements (190s vs 138s here, 70s vs 50s in
`test1`, and a 3-rep 71s vs 51s in `test9`). **Do not describe lex as "within noise
of production"** — an earlier draft of this file did, and three samples say
otherwise. The 31:1 normalization argument does not translate into a *catastrophic*
tractability penalty on the cheap principles, which is the defensible version of the
claim.

Utilitarian is the exception: across four attempts in two sessions lex has never
proved optimality on it, where production does so in **202–658s** (202s and 349s in
`test9`, 619s in `test2`, 658s in `test4`; and it reached a proven optimum inside a
240s budget in `test6`). But see `test9_perf.py`
below before reading that as a straight loss — lex's timed-out partial reaches a
*better* fairness value than production's proven optimum, and the salvage means that
partial is now what gets served.

### What `test1_lex.py` actually found

**§1 — fairness is exactly equal, not merely no-worse.** Every principle, both arms:

| principle | lex | production |
|---|---|---|
| Proportional | prox 367.56, arr 44 | prox 367.56, arr 44 |
| Prioritarian | prot 0.0, arr 44 | prot 0.0, arr 44 |
| Equal | arr 44 | arr 44 |
| Sufficientarian | arr 44 | arr 44 |

Lex never costs fairness — and on this payload never buys any either, because
production already reaches the same values. Peaks differ on **two** of the four, not
one: Prioritarian +4.77 (lex) vs +6.99 (production), and Sufficientarian +4.77 vs
+6.02. Both are the known arbitrary-peak drift, not a lex effect — the objectives are
identical and the peak is in none of them, so only the tie-break landing differs.

**§2 — the weight-invariance check does not discriminate.** It was billed as the
sharpest test that lex is in effect. It is not, on this payload:

| weightProximity | lex | production |
|---|---|---|
| 1.0 | prox 367.56, peak +4.77 | prox 367.56, peak +4.77 |
| 8.0 | prox 367.56, peak +4.77 | prox 367.56, peak +4.77 |

Lex is weight-invariant exactly as the theory says — but so is production, because
367.56 is reachable regardless of weighting. A discriminating version needs a payload
where the principle term and the time term genuinely trade. Don't re-run §2 as
written and expect a verdict.

**§3 — the time term is purely a tie-break here.** Production, Proportional:

| weightTime | peak | arrival sum | proximity |
|---|---|---|---|
| 1.0 | +4.77 | 44 | 367.56 |
| 8.0 | +4.77 | 44 | 367.56 |
| 0.0 | +6.02 | **63** | 367.56 |

Fairness is untouched in all three; only the arrival sum moves, and only when the term
is removed entirely. On Proportional, then, the time term really is only breaking ties,
and demoting it changes nothing. That does NOT generalize: on Utilitarian + People the
same demotion moves the fairness value by 5-8% (see `test9_perf.py`), because there the
two terms genuinely trade.

(`weightTime: 0` is the one input where the two solvers must agree by construction:
`eff_w_time == 0` means `T_penalty` is never built, so lex adds no second tier either.)

**Net, CORRECTED by `test9_perf.py` — indistinguishable on the CHEAP principles only.**
On Proportional, Prioritarian, Equal and Sufficientarian the two return the same objective
values and arrival sums, so lex buys a guarantee those payloads never exercise. On
**Utilitarian + People they diverge, and lex wins on fairness** — see the head-to-head
below.

### `test9_perf.py` — the head-to-head, repeated measures

Four arms as four processes against four servers, so neither solver gets the quiet
machine and the two configurations do not queue behind each other. Every earlier
timing here was a single sample under whatever load happened to be on the box, and
Z3's spread is wide enough that one sample decides nothing.

**Proportional** — 3 reps each:

| | lex | production |
|---|---|---|
| reps | 68s, 71s, 80s | 50s, 51s, 51s |
| median | **71s** | **51s** |
| proven optimal | 3/3 | 3/3 |
| proximityCost | 367.56 | 367.56 |
| arrivalPenalty | 44 | 44 |

Lex costs **1.39×** and returns a bit-identical result. Note also the spread:
production varied by 1s across three reps, lex by 12s.

**Utilitarian + People** — the configuration where they actually diverge:

| | lex | production |
|---|---|---|
| runtime | 1804s, 1803s (both hit the 1800s cap) | 202s, 349s |
| optimality | partial, 0/2 proven | proven optimal, 2/2 |
| totalUtilNoise | **37.554**, **36.756** | 39.727, 39.727 |
| arrivalPenalty | 58, 58 | 44, 44 |

**Both lex reps beat production's proven optimum on the principle's own metric** --
by 5.5% and 7.5%. Production returned the identical 39.727 twice, so its optimum is
stable and lex is genuinely reaching past it, not landing on noise. Not a contradiction — they optimize different things. Production
minimizes a weighted *sum* of noise and arrival time, and its optimum for that sits at
39.727 noise / 44 arrival. Lex minimizes noise *first*, so it trades 14 timesteps of
arrival promptness for 2.17 units of noise. Each is optimal for its own objective.

This is the first measured case of lex reaching something production structurally
cannot, and it is the honest case *for* the change: where the two optima coincide lex
is 1.4× slower for nothing, and where they do not, lex is the one that actually
prioritizes the principle.

Cost is real too: **at least** 6.6× slower, no proof of optimality, and 32% later
arrivals. "At least" matters — both lex reps were stopped by the 1800s cap, so 6.6×
is a lower bound against production's 275s median, not a measured ratio. Nobody has
run lex on this configuration to completion, so its true cost here is unknown.

Whether that trade is worth making is a values question, which is what the tool is
for.

### One more caveat on the original argument

The term-share measurement says time dominates the objective's **magnitude**, and that
still holds, but the on/off probe in `test2` shows production's principles are not
thereby inert: they improve their own metric by 41.8–48.7% (Utilitarian) and 13.5%
(Equal+People) at an *identical* arrival sum. Time decides how big the number is; the
principle still picks among the arrival-optimal routings.

## Shared with production

Both were developed here and then merged into `solver_server_dB.py`. They are not
lex features and nothing here depends on the lex change.

### Best-so-far salvage on phase-2 timeout

A timeout does not mean the search found nothing. Z3's `Optimize` keeps the best
solution it has reached and usually spends its last stretch only trying to *prove* it
optimal, so on timeout there is normally a model in hand that satisfies every hard
constraint and is merely unproven. Production used to throw it away and fall back to
phase 1's route with no objective applied at all.

Now `_best_so_far()` reads that incumbent, and the reply comes back
`optimality: "partial"` with a `notice` rather than `phase2Failed` with a `warning`.

`_best_so_far` reads every `L[i][t]` rather than trusting the model, because
`Optimize.model()` both raises when nothing was found and can hand back a model with
location variables unassigned. `_model_is_feasible()` then **verifies** the salvaged
model rather than trusting Z3 to only ever hold a satisfying incumbent: it replays
`opt.assertions()` into a fresh `Solver` with every `L[i][t]` pinned to the model's
value, and anything but `sat` — a timeout on the replay included — falls back instead
of serving. Pinning the positions makes the rest pure propagation, so it is nearly
free: 63s elapsed on a 60s budget with the guard, against 68–70s without it
(`out_t8_guard.txt`).

**The salvage is not monotonic in budget, and below ~120s it is worse than the phase-1
route it replaces.** `test6_salvage_value.py`, Utilitarian + People, utilNoise
recomputed from the returned paths so every row is scored the same way:

| budget | result | totalUtilNoise | vs phase 1 |
|---|---|---|---|
| 5s | no incumbent — phase 1's route | 82.56 | — |
| 30s | no incumbent — phase 1's route | 101.27 | — |
| 60s | partial | 105.55 | **+22.98 worse** |
| 120s | partial | 82.17 | −0.39 better |
| 240s | **optimal** | 39.73 | −42.84 better |

An earlier version of this table read 60s → 107.06, 180s → 50.79, 620s → 39.73 and
showed a clean monotone improvement. It was assembled from two different runs and
told the wrong story; the numbers above are one run, `out_t6_salvage.txt`.

Two things follow, and they pull in opposite directions. The phase-1 "baseline" is
**not** a baseline — the same payload gave 82.56 and 101.27 on two draws, so it is
essentially a random draw with respect to the objective and "the salvage is worse
than phase 1" is not a stable claim. But the salvage is still the right default,
because the dashboard's budget is 600s, far past the crossover. Do **not** add
compare-and-pick-the-better machinery on the strength of the short-budget rows:
scoring phase 1's route on the objective costs a second solve, and the thing it would
be compared against is noise.

### Phase-2 failure says what was dropped

- **Names the objective.** "the Proportional (proximity) objective", not "your
  fairness choices". With People on it says so — "total noise, weighted by
  population" — and when two terms are live it says both were lost.
- **Stops claiming a loss that did not happen.** Equal and Sufficientarian set no
  objective; their rule is the hard D/U cap that phase 1 enforces either way. The old
  message sent those users hunting for a problem that was not there.
- **Fixes a factual bug.** The old text quoted `T={T_for_phase2}` while returning
  phase 1's paths at the shorter `T_lower` — a horizon the returned route did not
  have. Verified: message said T=6, `len(paths[0])` was 5.

### One API, two solvers

Every phase-2 reply from either file now carries the same five fields, and
`objectiveMode` is the only one whose *value* differs:

| field | meaning |
|---|---|
| `objectiveMode` | `"weighted"` or `"lex"` — which solver answered |
| `optimality` | `"optimal"` proven / `"partial"` best-so-far / `"none"` phase 2 failed |
| `principleOptimized` | was there an objective term at all (False for Equal, Sufficientarian) |
| `phase2Failed` | did phase 2 produce nothing |
| `principleImposed` | does the routing honour what was asked for |

`arrivalPenalty` is the one conditional field: absent when the arrival term is off,
and on a phase-2 failure, where there is no phase-2 model to evaluate it against.

`principleOptimized` and `principleImposed` are close but not the same question, and
Equal is where they split: no objective was optimized, yet the routing does honour
the rule, because for Equal the rule *is* the hard cap. The dashboard uses
`principleImposed` alone to pick amber vs blue.

## Harness

| file | purpose |
|---|---|
| `cfg.py` | reproduces `buildSolveRequest()` for any (principle, who) pair |
| `client.py` | POST helper; `fellback()` detects the silent phase-2 fallback |
| `test1_lex.py` | lex vs production on 4 principles; weight-invariance; `weightTime` |
| `test2_util_people.py` | is the Utilitarian objective doing anything? on-vs-off |
| `test3_warning.py` | forces phase-2 failure, checks wording and flags |
| `test4_terms.py` | each term as a % of its own normalized range — who decides |
| `test5_api_shape.py` | the two solvers answer with the same fields; salvage fires |
| `test6_salvage_value.py` | is the salvaged route better than the phase-1 one it replaces |
| `test7_notice_severity.js` | `node test7_…` — pulls `notice()` out of the dashboard and checks the amber/blue rule against the solver's real message text |
| `test9_perf.py` | `python test9_perf.py <port> <proportional\|utilpeople> [reps]` — the repeated-measures head-to-head above |
| `cfg.py`, `mkreq.py` | payload builders; `mkreq` covers Proportional only, `cfg` covers all five principles and the People toggle |
| `serve_any.py` | `python serve_any.py <lex\|prod> <port>` |

There is no `test8`. `out_t8_guard.txt` is real output — it is the feasibility-guard
timing quoted in the salvage section — but the script that produced it was a throwaway
and was not kept. Re-derive it from `test5_api_shape.py` §3/§4 if the number needs
re-checking.

Every test takes the port as `argv[1]`, so the two arms run as concurrent processes.
The solve lock is per server *process*, so 5056 and 5057 genuinely parallelise; only
same-port requests queue.

`test2` is the load-bearing one: it recomputes the objective from the **returned
routing** in both arms, because the solver only reports the value when the objective
is switched on, and the whole question is what it looks like when switched off.

## Still not done

- ~~**The shipping decision.**~~ **Made 2026-08-27: lex is production.** The weighted
  scheme survives as the control on 5056. If Utilitarian's unproven results turn out to
  be a problem in a live room, switching back needs no code change — point the dashboard
  at 5056 and the reply's `objectiveMode` will say `"weighted"`.
- **Lex has still never completed a Utilitarian run.** 0 for 4 attempts, all capped.
  Its true cost there is unknown, only bounded below at ~6.6×. This is the one live risk
  in the adoption, and it is mitigated rather than solved: the salvage means the room
  gets a verified partial with the objective applied, not a failure.
- **People as its own tier.** Currently it trades against the principle at 0.3 inside
  the principle tier. Making it strictly subordinate is a one-line change, and it is
  lex-only by nature — there is no weighted-sum equivalent.
- **Added-noise proximity pricing (Q7).** Queued for *both* solvers, from
  `proximity_noise_experiment/`. Read that folder's README first — the 30-ranking
  sweep turned this into a decision, not a port. dB pricing gives a quieter answer
  (never a worse peak; 4.8–5.6 dB better in 11 of 28 rankings) but runs ~28× slower
  and returns the same routing no matter how the group ranks the factors. Someone has
  to choose between the better answer and the working lever before this is worth
  implementing.
- ~~**Frontend Q4 and Q5.**~~ **Both shipped 2026-08-27.** Q4: the solver's own
  diagnosis is now the `<summary>` line and the generic "no routing satisfies this rule"
  headline was demoted into the fold — `unsatMessage()` moves the text, it does not parse
  it. Q5: `cacheClear()` clears all three copies and is wired to an **Empty the cache**
  button in the Facilitator set-up panel. `CACHE_KEY` also went to `v3`, because the lex
  switch changes the routings themselves and a cached `v2` entry is the old scheme's
  answer to the same question.
- **Re-measuring `WORKSHOP_NOTES.md`** against the current solver. The known-stale
  timings are flagged in place there, and the closing table now describes the lex scheme,
  but nothing in that file has been re-timed against production-as-lex. The numbers in it
  are the weighted scheme's.
- **The published artifact is behind `WORKSHOP_NOTES.md`.** Update it via its URL rather
  than publishing a second copy.
