# UPDATE_RECORD.md — the change history of `solver_server_dB.py`

This repository was created as a clean structure with no prior history, so the
solver's original 26 commits are **not reachable from this branch**. This file is
therefore the record: every change to `solver_server_dB.py`, with its date, its
original commit hash, and what it did.

The hashes refer to the original repository
(`rcpsl/aircraft_dynamics_solver`). They are listed so any claim here can be checked
against the real commit.

---

## How this repository's own history relates to that record

The solver appears in four commits here, each a **replay** of a state that genuinely
existed and was tested before being committed:

| this repo | lines | the state it reproduces |
|---|---|---|
| `solver: dB variant as of 2026-07-19` | 1036 | `366a85d`, the last solver commit reachable from `main` |
| `solver: max/min U encoding, /cancel, reachability pre-check` | 1324 | `83804cc`, the tip of `perf/solver-db-constraint-reduction` |
| `solver: lexicographic objectives, phase-2 salvage, proximity-noise pricing` | 1751 | the working tree as of 2026-09-03 — **never committed anywhere before** |
| `solver: tied-routing enumeration` | 1897 | the working tree as of 2026-10-12 |

The **commit dates here are the date of the restructure**, not the dates the work
was done. The real dates are in this file. Authorship of the code is unchanged.

Two facts worth knowing about the original repository's state at the time of the
restructure:

- **Six solver commits were never merged to `main`.** `main`'s solver was still at
  `366a85d` (2026-07-19, 1036 lines) while
  `perf/solver-db-constraint-reduction` carried five more 2026-08-23 commits plus
  `9e0be66`, reaching 1324 lines. Anyone reading `main` alone had a two-month-stale
  solver.
- **573 lines were never committed at all.** Lexicographic objectives — production
  behaviour since 2026-08-27 — existed only in a working tree. So did the phase-2
  salvage and the proximity-noise pricing. The third replay commit above is the
  first time any of it is recorded.

---

## The record

### Pre-history: before the dB variant

The dB solver was forked from `solver_server.py`, which it does not share a file
with but does inherit its structure from. Relevant ancestry:

| date | commit | change |
|---|---|---|
| 2026-05-28 | `34df3ac` | solver visualizing webpage construction |
| 2026-06-05 | `c8cffb7` | `find_min_T`: algebraic pre-checks, incremental Z3 encoding, unsat-core early exit |
| 2026-06-25 | `3f62ece` | utilitarian transit-time optimization |
| 2026-06-25 | `5518a7d` | prioritarian optimization and normalized weighted objectives |
| 2026-07-06 | `41172c6` | proportional allocation optimization |
| 2026-07-07 | `2468d73` | soft T mode |
| 2026-07-07 | `109f750` | fix aircraft drifting after arrival in soft T mode |
| 2026-07-07 | `e3ca77c` | adjacent disparity constraint replaced by global all-pairs disparity |

### 2026-07-07 — the dB variant is created

| date | commit | change |
|---|---|---|
| 2026-07-07 | `de57bb9` | **`solver_server_dB.py` created**, on port 5051. The distinguishing idea: constraints are expressed in decibels rather than aircraft counts. |
| 2026-07-07 | `1762af2` | fix a normalization scale mismatch in `optimize_objectives` |
| 2026-07-07 | `8a58216` | `D` becomes an absolute dB level cap |
| 2026-07-07 | `bfa1510` | fix over-conservative pre-checks |
| 2026-07-07 | `c70ab69` | input validation, and the soft-T self-loop check — soft T requires every destination station to have a self-loop, since an arrived aircraft must be able to stay put while others finish |

### 2026-07-09 to 2026-07-16 — the noise model takes shape

| date | commit | change |
|---|---|---|
| 2026-07-09 | `9345e1e` | return `countMatrix` alongside `noiseMatrix` |
| 2026-07-10 | `52a5e58` | **the active-noise model**: an aircraft only produces noise in transit. `active[i][t] = moved[i][t] AND NOT arrived[i][t-1]`, so pre-departure aircraft are silent and the arrival timestep still counts. This is the definition every later noise figure depends on. |
| 2026-07-14 | `f47a7e5` | proportional allocation as a soft constraint |
| 2026-07-15 | `3e85059` | station-weighted transit cost in the utilitarian objective |
| 2026-07-15 | `969cf19` | `utilNoiseMode` — utilitarian as least total noise rather than least travel |
| 2026-07-15 | `9a2f39d` | `aircraftMultipliers`: one solver aircraft can represent several flights |
| 2026-07-15 | `d3c5880` | D/U constraints move to precomputed count-based lookup tables |
| 2026-07-16 | `0122b47` | harden against multiplier-driven constraint blowup and concurrent-request crashes |

*This is the version that produced `data/2026-07-17/`.*

### 2026-07-19 — D becomes an increase

| date | commit | change |
|---|---|---|
| 2026-07-19 | `366a85d` | **`D` caps the dB INCREASE, not the absolute level.** Also: phase-2 timeout handling, and `/progress` reporting the live phase. |

*This is the first solver state replayed in this repository, and the version that
produced the 2026-07-19 generation of `dB_target_sweeps`. It remained `main`'s
solver until the restructure.*

### 2026-07-30 — the constraint-count rewrite

| date | commit | change |
|---|---|---|
| 2026-07-30 | `9e0be66` | **the pairwise `U` table becomes a max/min encoding.** `U` had been an `Implies` over every ordered station pair and every count value — roughly 95% of all constraints in the model, and the reason 5x5-sized problems timed out. It is now two auxiliary integers and `2M+1` constraints per timestep, from the identity `max(dB) - min(dB) <= U`. Sound and complete. **~110,000 assertions down to ~2,089**, and the admission limit rose roughly 25x. |

*This is the version that produced the 2026-07-30 extension of `dB_target_sweeps`
and all of `dB45_collection`.*

### 2026-08-23 — robustness

| date | commit | change |
|---|---|---|
| 2026-08-23 | `5fc3565` | drop comments and dead code the `U` rewrite left stale |
| 2026-08-23 | `4db825f` | **`/cancel`**, so a running solve can be abandoned instead of holding the lock |
| 2026-08-23 | `62d8808` | a longer solve budget, overridable per request (`timeoutMs`) |
| 2026-08-23 | `499cb7b` | **both position-based `D` pre-checks were unsound** and are replaced by a D-admissible reachability BFS. The old ones could declare a solvable request infeasible. |
| 2026-08-23 | `83804cc` | the proportional principle becomes **proximity-weighted burden** (`optimizeProximity`), replacing the deleted `optimizeProportional` |

*Second replay commit. This was the tip of the committed history at restructure
time.*

### 2026-08-27 — lexicographic objectives *(uncommitted until the restructure)*

The principle and the arrival-time penalty had been folded into **one weighted
sum**, which let arrival time trade against fairness. Because the normalizing
divisors are loose by very different amounts, the time term outvoted the principle
roughly **31:1** on the measured payload — 68.8% of its normalized range against the
utilitarian term's 2.2%. Z3 was mostly minimizing arrival time while appearing to
optimize fairness.

They became two `opt.minimize` calls applied in call order under Z3's default
`priority='lex'`, so the time tier can only choose among answers already optimal for
the principle. `OBJECTIVE_MODE = "lex"`.

Measured before adoption: fairness exactly equal to the weighted scheme on
Proportional, Prioritarian, Equal and Sufficientarian; ~1.4x slower on Proportional,
~2x faster on Prioritarian. On Utilitarian + People the two diverge and lex reaches a
5.5-7.5% better noise value but did not prove optimality within 1800s.

Consequences recorded in the code:

- `weightTime` no longer sets a magnitude, only whether the tie-break runs at all
- with a single principle term live, **that term's weight cannot move the argmin** —
  scaling `weightProximity`/`weightPrioritarian`/`weightUtilitarian` alone is
  mathematically inert
- `weightTime: 0` is the one input where lex and weighted coincide

Evidence and the weighted control: `data/2026-08-28/lex_objective_experiment/`.

### 2026-08-27 onward — phase-2 salvage *(uncommitted until the restructure)*

A phase-2 timeout used to return phase 1's unweighted route, silently ignoring the
choices the group had just made. `_best_so_far` and `_model_is_feasible` recover the
best model found so far; `_principle_name` names the objective in the dashboard's own
words. The reply gained `optimality` (`"optimal"` / `"partial"` / `"none"`) and
`principleImposed`, so a caller can distinguish a proven optimum from a salvaged one
— and `principleImposed: true` means a warning need only report that arrival times
went unoptimized, which is not the participant's problem.

### 2026-09-03 — Proportional priced in decibels *(uncommitted until the restructure)*

Proportional prices burden as **weight x the dB increase** a station suffers, not
weight x occupancy. `proximityMode` defaults to `"noise"`; `"count"` reproduces the
old term and is roughly **28x cheaper** for Z3. `proximityNoiseRef` prices every
station off one reference baseline instead of its own. Replies echo `proximityMode`
so a stored result says which priced it. `_max_weighted_price` normalizes the term.

Measured over 30 rankings: never a louder peak, 4.8-5.6 dB quieter in 11 of 28.

Two consequences that are **not** bugs:

- dB is concave in the count, so the objective **concentrates** traffic (3 aircraft
  on a 45 dB tile cost 6.02 dB; three separate tiles cost 9.03)
- the increase depends on each station's own baseline, so one aircraft adds 3.010 dB
  at a 45 dB tile and 0.043 dB at a 65 dB one

The second has an open cost: it builds in an implicit ambient weight of about **0.88**
in rank-equivalent terms, against the **0.60** a participant can give their
top-ranked factor. dB pricing collapsed 30 participant rankings to **one** routing.
See `data/2026-09-03/proximity_weight_experiment/`. **Still open.**

*Third replay commit (1751 lines) is the combined state of these three changes. They
could not be split: of 20 diff hunks, several carry two or three of them in the same
lines and one carries all three, so separating them would have meant inventing
intermediate states that never existed and could not be tested.*

### 2026-10-12 — tied-routing enumeration

`enumerate` (0-50, default 0) returns several routings satisfying every hard
constraint, the first being the one `/solve` would have returned alone.
`enumerateDistinct` is `"counts"` (default) or `"paths"`; `enumerateAtOptimum`
(default true) pins each raw principle metric and the arrival penalty so the
alternatives tie on every term at once.

Why: Equal and Sufficientarian set **no objective**, so every routing inside the D/U
cap satisfies the principle equally and the single answer was settled by the
arrival-time tie-break and then Z3's search order. `alternativesStatus:
"exhausted"` is the reassuring outcome — no other routing fits, so nothing was
arbitrary.

Off by default, so a request that does not ask for it gets an unchanged reply and
client response caches are unaffected. An older server ignores the key and degrades
to the single answer.

*Fourth replay commit (1897 lines) — the current state.*

### 2026-10-13 — measurements, no code change

- **Relabelling:** `"paths"` permits relabellings of interchangeable aircraft
  (1,658,880 per routing at the 19-aircraft default) and the solver has **no
  symmetry-breaking constraint**, so they are reachable. Z3 returned **zero** at
  K=5/10/25/50. At K=50 `"paths"` did return 2 of 50 audibly identical routings by a
  different mechanism — distinct trajectory sets colliding on one count matrix —
  where `"counts"` returned 50 of 50 distinct. No measurable speed difference.
  Enumeration cost is mostly fixed: ~6s setup plus ~0.4s per routing.
- **`U` sweep:** `U`'s value is one constant in one constraint per timestep, so it
  never changes the model size (phase 2 was 3570 assertions in all 13 runs). `U=15`
  and `U=30` are **bit-identical** on this map — `U=15` never binds. Only `U=5`
  constrains anything, costing 3 arrival-timesteps, and `U=3` is undecidable in
  budget with `D` wide. Pairing `U` with an equally tight `D` removes the blow-up:
  at `U=5`, `D=30` took 341.7s / 508k conflicts, `D=10` 150.2s, `D=5` **59.0s /
  16.8k conflicts**. Always send `D` alongside `U`.

---

## Work deliberately not in this repository

**`experiment/solver-db-quiet-tier`** (original repo, 2026-10-06, two commits
`d0dfdac` and `b8fd525`) adds a **third lex tier** that minimizes the peak noise
among tied routings, on port 5093 (`quietTieBreak`). It was not adopted: the
front-end ranking in the dashboard achieves the same visible effect without
touching the solver. Measured: the `"peak"` variant was effectively free (17.5s),
the `"total"` variant cost 136.7s.

Note `b8fd525`'s commit message still attributes routing variation to `timeoutMs`,
which was **wrong** — see below.

---

## Current state and open items

`solver_server_dB.py`, 1897 lines, port 5051, `OBJECTIVE_MODE = "lex"`.

Known and unresolved:

1. **The served routing depends on request history, not just the request.** The same
   payload posted three times to one process returned +6.02, +8.45 and +6.99 dB,
   each correctly reported `"optimal"`. A fresh process reproduced the sequence
   exactly, so Z3 is deterministic; state accumulates in the process-global Z3
   context and shifts the search for later requests. The dashboard's front-end
   ranking reduces the visible effect but does not fix the cause. *(An earlier
   explanation blamed `timeoutMs`; that was wrong, and `b8fd525`'s message still
   carries it.)*
2. **The ambient gradient in Proportional** outweighs the participant ranking 1.46x.
   `proximityNoiseRef` exists to flatten it and the dashboard does not send it.
3. **`SCALE = 100` rounding can manufacture strict preferences.** A 65 dB tile's
   single-aircraft increase rounds 4.3214 down to 4 while the two-aircraft value
   rounds 8.6002 up to 9, which reverses concavity's true ordering. Observed making
   an aircraft wait a timestep for an apparent 0.01 dB gain that does not exist in
   exact arithmetic — and the arrival tier cannot override it, because lex only
   breaks exact ties in the integer objective.
4. **Equal and Sufficientarian are identical on the 5x5 map** by pigeonhole. Known,
   deliberately deferred.
