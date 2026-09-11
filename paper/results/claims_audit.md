# Claims audit

Every load-bearing claim inherited from `5x5_realtime_solver/WORKSHOP_NOTES.md`, the
solver source comments, or the project memory, checked against a fresh measurement.
Rows marked **CORRECTED** are ones where the inherited claim is wrong or imprecise and
the paper must not repeat it.

Evidence: `paper/harness/results/*.jsonl`, `paper/results/analytic_checks.md`,
`paper/results/summary.md`. Solver under test: `solver_server_dB.py` at commit
`f231cb9`, unmodified.

---

## 1. "Equal and Sufficientarian return identical routings on this map"

**CORRECTED.** They do not. They return *different* routings that are *equally optimal*.

Measured (`results/scaling.jsonl`, who = Communities, limit 10 dB):

| N | same paths? | Equal peak dB | Suff peak dB | Equal arrival | Suff arrival |
|---|---|---|---|---|---|
| 6 | yes | 3.01 | 3.01 | 18 | 18 |
| 8 | yes | 3.01 | 3.01 | 22 | 22 |
| 14 | **no** | 6.02 | 6.02 | 40 | 40 |
| 16 | **no** | 6.99 | 6.02 | 44 | 44 |
| 22 | **no** | 6.02 | 6.02 | 62 | 62 |
| 24 | **no** | **10.00** | **6.02** | 66 | 66 |
| 30 | **no** | 10.00 | 10.00 | 149 | 147 |

The arrival penalty --- the *only* thing either configuration optimises --- is identical
at every $N \le 24$. So the two are solving the same problem and reaching the same
optimal value, while the routing shown to the user differs, and the headline peak-noise
number differs by up to **3.98 dB** (at $N=24$). That is a larger and more troubling
claim than the original: it is not that the principles coincide, it is that the
difference a participant sees between them is manufactured entirely by solver
tie-breaking.

**Why they coincide, exactly.** The original explanation appeals to a pigeonhole
argument ("with fewer aircraft than stations some station is always empty, so the
minimum increase is 0"). The pigeonhole step is not needed. Since $\delta_m \ge 0$
everywhere, $\max_m \delta_m - \min_m \delta_m \le \max_m \delta_m$ unconditionally, so
a routing satisfying $D \le \ell$ automatically satisfies $U \le \ell$. The dashboard
sends Equal $(D,U) = (\ell,\ell)$ and Sufficientarian $(D,U) = (\ell,30)$; both reduce
to the single constraint $\max_{m,t}\delta_m \le \ell$. The feasible sets are equal as
sets, for any fleet size, with no assumption about occupancy.

The pigeonhole condition governs something different --- whether the dashboard *sends*
$D$ for Equal at all. Above $N = 25$ it stops doing so, Equal becomes $U \le \ell$
alone, and its feasible set becomes strictly LARGER than Sufficientarian's.

**SUPERSEDED, see C2 below.** An earlier version of this entry read the $N=30$ row
(arrival 149 vs 147) as the two principles diverging for the first time. Both those
rows are `partial` -- two searches stopped at different points. The proven $N=32$ pair,
where the payloads differ by more, comes back **identical at 88**. Equal's larger
feasible set buys it nothing, because the arrival-minimising routing already satisfies
the tighter constraint.

## 2. "Some station is always empty, so min added noise is 0"

**CONFIRMED, and stronger than stated.** 196 of 196 returned routings have
`peakAddedDB == peakSpreadDB` to floating-point exactness, i.e. at the timestep of
worst noise there is always at least one community at exactly zero added noise. This
holds at $N=30$ and $N=32$, above the 25-station pigeonhole threshold, because aircraft
are only *active* during their flight window and soft-T staggering keeps them from all
being airborne at once.

Consequence for the paper: the disparity cap $U$ never binds as a *disparity* cap in any
measured run. It always binds as an absolute cap.

## 3. "Prioritarian's objective contributes nothing --- it evaluates to exactly 0"

**CONFIRMED, and the mechanism is now pinned down.** Two independent tests.

*Does the protected set matter?* (`prior_sets.jsonl`) Two sets were tried: the three
loudest non-vertiport communities, matching the source document's "regions that
presently and historically bear the greatest burden"; and a contrast set placed
deliberately **on** the natural flight corridors. `protectedNoise` is **0.00 for both
sets at every fleet size tested** ($N = 8,16,24,32$). So the zero is not an artefact of
choosing communities that happen to be out of the way.

*Is the zero earned or free?* (`ablation.jsonl`) Running the identical payload with
`optimizePrioritarian` cleared:

| N | protected noise ON | OFF | arrival ON/OFF | paths differ? |
|---|---|---|---|---|
| 8 | 0.00 | 0.00 | 22 / 22 | yes |
| 16 | 0.00 | 0.00 | 44 / 44 | yes |

The protected communities receive zero added noise **whether or not the objective is
switched on**, and the arrival penalty --- the only other live term --- is identical.
The ON and OFF runs are therefore *interchangeable optima*: each is feasible and
optimal for the other's problem. The objective is inert.

The routings nevertheless differ, and the peak noise with them: at $N=8$ the run with
the objective ON has a peak of \SI{6.02}{\dB} against \SI{3.01}{\dB} with it OFF. Since
both are optimal for both problems, that \SI{3.01}{\dB} is pure solver tie-break --- and
it happens to make the *principled* run look worse. This is the sharpest single piece of
evidence for Sec. IV-G.

**A caveat the paper states, now with evidence.** Inertness here is a property of *this
map*, on which routings avoiding the protected communities are freely available. It is
not a claim that Prioritarian is inert in general --- and the grid4 instance below
confirms this directly: halving the routing freedom makes the objective bind (0.129 dB
off vs 0.00 on, at identical arrival).

## 4. Capacity table: "at D=3 a 45 dB tile holds 0 aircraft; at D=5 it holds 2"

**CONFIRMED** analytically and against the solver's own `_compute_d_counts`
(`analytic_checks.md`). Closed form:
$\kappa = \lfloor (10^{D/10}-1)/10^{(\alpha-b)/10} \rfloor$.

**CORRECTED in one detail.** The workshop table reads `16` for several cells (D=4 at
65 dBA, D=5 at 55 and 65 dBA, D=10 at 55 dBA). Those are not capacities, they are the
fleet size: `_compute_d_counts` never searches past the number of aircraft it is given.
True capacities are 151, 21, 216 and 90 respectively.

Also found: centi-decibel rounding makes the cap very slightly *permissive* at large
counts --- $\delta_{65}(901) = 10.0043$ dB rounds to exactly 1000 centi-dB and passes
$D=10$, whose exact capacity is 900. Always in the permissive direction, and unreachable
at any fleet size in this paper ($N \le 32$), so no result is affected.

## 5. "One aircraft adds 3.01 dB at 45 dBA and 0.043 dB at 65 dBA (~160x price ratio)"

**CONFIRMED for the dB values; the ratio depends on which quantity is meant.** The
per-aircraft increase ratio is $3.0103/0.0432 = \mathbf{69.7}$, not 160. The 160 figure
in `proximity_weight_experiment/NOTES.md` is a *median price ratio across tiles under
noise pricing*, which is a different quantity (it folds in the participant weight
vector). The paper quotes 70 and says what it is the ratio of.

## 6. "The time term reached 68.8% of its normalised range against the utilitarian
term's 2.2%, so time outvoted the principle ~31:1"

**NOT INDEPENDENTLY VERIFIED.** This measurement was made against the *weighted*
objective scheme, which production replaced with a lexicographic one on 2026-08-27. It
is quoted in Section III only as the historical motivation for the lexicographic
change, attributed as such, and no result in Section IV depends on it. Re-deriving it
would require running the superseded solver in
`lex_objective_experiment/solver_server_dB_weighted.py`.

## 7. "Proportional returns an identical fairness result at every horizon, and slack 0
vs slack 1 costs about 1.3x"

**NOT TESTED HERE.** The paper does not use the horizon-slack comparison. All runs use
the dashboard's own `slackFor` rule (slack 1, dropping to 0 when a utilitarian objective
is live), so the horizon is whatever a participant would actually get.

## 8. Payload fidelity: does the harness send what the dashboard sends?

**CONFIRMED.** `paper/harness/payload.py` is compared field-by-field against the real
`buildSolveRequest` extracted from the shipped HTML (`extract_js.js`) across 10
configurations spanning all five principles, both `who` settings and two Proportional
rankings: **0 mismatches**. Demand-factor rounding was corrected to match JavaScript's
`Math.round` (half away from zero); Python's banker's rounding differs at exactly the
factors 1.25 and 1.75.

---

# New findings (not inherited from any prior claim)

These were produced by this paper's sweeps and have no predecessor in the workshop
notes or memory. Listed so a later reader can tell measurement from inheritance.

## 9. Three of the five principles bind on nothing at the default setting

`ablation.jsonl`, N=16, each principle against the identical payload with its own
term removed:

| principle | arrival on/off | metric on | metric off | binds? |
|---|---|---|---|---|
| Equal | 44 / 44 | peak spread 7.0 | 4.8 | no --- control already inside the 10 dB cap |
| Sufficientarian | 44 / 44 | peak 6.0 | 4.8 | no --- same reason |
| Prioritarian | 44 / 44 | protected 0.00 | 0.00 | no --- inert |
| Utilitarian | 59 / 44 | total 24.0 | 34.5 | **yes**, -30.5% bought with +34% arrival |
| Proportional | 74 / 44 | total 46.7 | 36.1 | **yes**, redistributes; +68% arrival |

Equal and Sufficientarian's caps begin to bind at D=4, four dB below the workshop
default (see #10).

## 10. A tightening cap does NOT redistribute traffic between ambient tiers

Expected, and false. `caps.jsonl` at N=16: the share of flight time over each ambient
tier is flat across every feasible cap from D=20 down to D=4, and the residual
variation (45 dBA share ranging 18.2--43.2%) does not trend with D. Because
Equal/Sufficientarian carry no objective, the tier share is set by the tie-break.

What the cap does buy is **schedule length**: at D=4 the minimum horizon rises 5 -> 7
and flight time 44 -> 48 aircraft-timesteps. At D=3 the instance is infeasible.

The redistribution is real but comes from the **objective**, not the cap: at N=16
Utilitarian flies 15.4% of its time over 45 dBA communities against Equal's 34.1%,
and 30.8% over 65 dBA against Equal's 27.3%.

## 11. Peak added noise equals peak inter-community spread in every solve

101 of 101 completed solves at the time of writing, exact to floating point, across
every principle, fleet size and cap. At the worst timestep some community always has
exactly zero added noise. Consequence: the disparity cap U never once acted as a
disparity constraint; it acted as an absolute cap.

## 12. A provably redundant constraint is load-bearing for tractability

Below N=25 the dashboard sends Equal D=limit alongside U=limit. By the argument in #1
that adds no constraint. But it shrinks each tile's count domain: summed over the map,
sum(kappa_m) is 616 with it and 800 without, the whole difference falling on the eight
45 dBA tiles (9 branches vs 32). Above N=25 the tool drops it, and Equal is one of the
three runs that fell back to an unweighted route at N=32. Not proven causal ---
Sufficientarian+People also fell back with the smaller encoding --- but it is a case
where removing a redundant constraint on correctness grounds cost the principle its
answer.

---

# Second instance: grid4 (added 2026-09-04)

Same city, same demand, same principles, but von Neumann adjacency (no diagonal
flight). Mean out-degree 6.8 -> 4.2; minimum horizon 5 -> 7. 23 solves,
`results/grid4.jsonl`. This exists because every finding above except the collapse
proposition was a measurement on one map with abundant routing alternatives.

| finding | grid8 | grid4 | verdict |
|---|---|---|---|
| Equal == Sufficientarian (identical arrival, differing paths) | yes at N<=24 | yes at N=8,16,24 (34/34, 68/68, 102/102) | **replicates** |
| peak == spread (some community always at 0) | 101/101 | 23/23 | **replicates** |
| Utilitarian flies least over 45 dBA tiles | yes (15.4%) | yes at all three demands (17.9 / 22.7 / 24.3%) | **replicates** |
| Utilitarian lowest total added dB | yes | yes at all three demands | **replicates** |
| Tractability: hard-cap principles scale, dB objectives do not | yes | yes, and Prioritarian also fails to prove by N=24 | **replicates, sharpens** |
| Equal/Sufficientarian caps slack at limit 10 | yes | yes (arrival 68/68 with cap on/off) | **replicates** |
| Prioritarian objective inert | **yes** (0.00 on AND off) | **NO** --- 0.129 dB off vs 0.00 on, at identical arrival 68 | **CHANGES** |

The last row is the informative one and it changes in the predicted direction. Our
explanation for the inertness on grid8 was that routings avoiding any three nominated
communities are freely available. Halving the out-degree is enough to make the
objective bind, though only by 0.129 dB --- physically inaudible, but strictly
positive, and bought at zero arrival cost. This supports the diagnosis rather than
undermining it, and it is reported in Sec. IV-H as such.

Note also that the corridor-based protected set still scores 0.00 on grid4 at every
demand, so three communities remain avoidable even here; only the ablation control
(no objective at all) picks up noise on them.

---

# Cap binding and shortest-path proximity (added 2026-09-05)

Two questions raised after the first draft, both now measured.

## 13. Do the Equal / Sufficientarian caps ever actually bind?

Yes, but only in a narrow window, and the deployed setting is not in it.
`results/binding.jsonl`. Control = identical payload with both caps opened to 30 dB;
both runs keep the soft-T arrival objective, so a HIGHER arrival penalty under the cap
proves the cap excluded the unconstrained optimum.

**Lever 1, tighten the limit (N=16).** Binding window is one decibel wide:

| limit dB | outcome | arrival cap/open | T_min | hops | peak dB | binds? |
|---|---|---|---|---|---|---|
| 10 | optimal | 44 / 44 | 5 | 44 | 6.99 | no |
| 8 | optimal | 44 / 44 | 5 | 44 | 4.77 | no |
| 6 | optimal | 44 / 44 | 5 | 44 | 4.77 | no |
| 5 | optimal | 44 / 44 | 5 | 44 | 4.77 | no |
| **4** | optimal | **48 / 44** | **7** | **47-48** | **3.01** | **YES** |
| 3 | infeasible | -- | -- | -- | -- | n/a (no routing exists) |

At limit 4 a 45 dBA community holds exactly one aircraft, so the four flights bound
for the quiet vertiport must land on four different timesteps. The solver spreads them
in TIME, not in space -- the tier shares barely move (#10). Equal and Sufficientarian
behave identically throughout, as Prop. 1 requires.

**Lever 2, raise demand (limit 10).** At N=32 the default limit already binds hard:
arrival 158 with the cap against 88 without, flight time 155 hops against an 88-hop
floor. The fleet genuinely cannot be routed directly under the limit.

So the caps are not vacuous -- they are slack at the shipped setting. A facilitator
wanting them to matter should lower the limit to 4 dB or double the demand.

**Open at time of writing.** Several N=32 and all N=48/N=64 rows hit the 600 s budget
(`phase2_failed_timeout`, `phase1_timeout`). Those are being re-run at a 4 h budget by
`rescue.py`; until they land, the N>=32 numbers above rest on the rows that did
settle. The N=48/64 rows were intended to test whether Equal and Sufficientarian can
be made to DIFFER (needs every tile occupied, so min added noise > 0) -- unresolved.

## 14. How far from the shortest path are these routings?

Not far, for three of the five. Per-aircraft detour = flight length minus that
aircraft's BFS shortest-path floor, pooled over all fleet sizes, 152 aircraft per
principle (`results/scaling.jsonl`).

| principle | on shortest path | +1 | +2 | >=+3 | mean detour |
|---|---|---|---|---|---|
| Sufficientarian | 80.3% | 6.6% | 6.6% | 6.6% | 0.39 |
| Equal | 67.1% | 12.5% | 11.2% | 9.2% | 0.62 |
| Prioritarian | 61.2% | 10.5% | 10.5% | 17.8% | 0.85 |
| Utilitarian | 40.8% | 27.6% | 31.6% | 0.0% | 0.91 |
| Proportional | 7.9% | 28.9% | 27.6% | 35.5% | 1.91 |

The ordering matches the ablation exactly: the three principles that bind on nothing
(#9) are the three that stay on or beside the shortest path. Only Proportional
reliably reshapes the map, and it pays nearly two extra hops per aircraft to do it.
This bounds the whole enterprise and belongs in any claim that a fairness rule
"changed the routing".

---

# Corrections forced by raising the time budget (2026-09-05)

Two claims in the first draft were artefacts of the 600 s cap. Both were comparisons
between an UNPROVEN incumbent and a PROVEN optimum, which is never valid in either
direction. `cap_audit.py` now checks for exactly this class of error.

## C1. "At N=32 the default 10 dB limit binds hard (arrival 88 -> 158)"

**FALSE. It does not bind at all.**

At the 600 s budget, `bind|equal|10|2.0` returned an unproven incumbent with arrival
158, against a proven open-cap control of 88. That reads as decisive binding. Given
four hours the same configuration proves out at **88** -- identical to the control.
Corroborating proven rows at N=32:

| row | D/U | arrival | status |
|---|---|---|---|
| sufficientarian, limit 10 | 10/30 | 88 | optimal |
| sufficientarian, limit 8 | 8/30 | 88 | optimal |
| sufficientarian, open cap | 30/30 | 88 | optimal |
| equal, open cap | 30/30 | 88 | optimal |
| equal, limit 10 (4 h) | 30/10 | 88 | optimal |

All equal the 88-hop shortest-path floor. **Raising demand does not make a cap on
ADDED noise bind**, because the extra traffic is absorbed by loud communities whose
capacity is effectively unlimited (#4). Demand raises the floor without raising the
peak. Only tightening the limit works, and only at D=4 (#13).

## C2. "At N=30 Equal and Sufficientarian separate for the first time (arrival 149 vs 147)"

**FALSE, or at least unsupported.** Both N=30 rows are `partial`: two searches stopped
at different points, not two principles diverging. The proven N=32 pair -- where the
payloads differ by MORE, (30,10) against (10,30) -- comes back **identical at 88**.

Revised claim, now in the paper: *Equal and Sufficientarian have the same proven
arrival penalty at every fleet size settled, including above N=25 where the tool stops
sending D alongside U and Equal's feasible set becomes strictly larger.* The extra
freedom buys nothing because the arrival-minimising routing already satisfies the
tighter constraint.

N=30 is being re-run at a 4 h budget (`plans/settle.json`) to close this properly.

## The conditions for the collapse, stated exactly

The paper now separates two conditions rather than asserting "they are the same":

  (i) neither principle contributes an objective term, so both minimise the same
      tie-break over their own feasible set; AND
  (ii) the optimum of that shared objective over Equal's set is also attained in
      Sufficientarian's.

(ii) holds trivially when the sets are equal, which they are below N=25 (the tool sends
Equal D=U=ell, and Prop. 1 collapses that to D<=ell). Above N=25 the sets differ and
(ii) could fail -- it does not, in any instance measured. (i) fails immediately under
the OPTIMISATION reading of Equal, which is why the collapse indicts the reading rather
than the principle.

## C3. Routing distinctness, as seen by a participant

New measurement (`table_distinct` in analyze.py): pairwise L1 distance between
per-community occupancy vectors, as a fraction of total flight time. Occupancy rather
than path lists, so relabelling interchangeable aircraft is not counted as a change.

N=16, grid8:

| | Equal | Suff | Prior | Util | Prop |
|---|---|---|---|---|---|
| Equal | -- | 0.11 | 0.23 | 0.25 | 0.25 |
| Sufficientarian | 0.11 | -- | 0.18 | 0.29 | 0.25 |
| Prioritarian | 0.23 | 0.18 | -- | 0.17 | 0.25 |
| Utilitarian | 0.25 | 0.29 | 0.17 | -- | 0.24 |
| Proportional | 0.25 | 0.25 | 0.25 | 0.24 | -- |

The principles DO produce different maps: 11-29% of flight time lands on different
communities. Equal vs Sufficientarian is the closest pair at every fleet size and is
**exactly 0.00 at N=8** -- identical maps. Their distance grows to 0.11 (N=16) and 0.23
(N=24) while their arrival penalties stay identical, so that growth is tie-break, not
principle. It is the only pair where a visible map difference corresponds to no
difference in what was optimised.

---

# Retractions R3 and R4 (2026-09-05): the budget confound, second instance

External review found two further findings that do not survive scrutiny. Both were
caught by inspection, NOT by `cap_audit.py`, which graded rows by *status* and was
blind to *budget*. The audit has been extended; see "Budget homogeneity" in
`cap_audit.md`.

## R3. Shortest-path detour comparison -- WITHDRAWN

Claimed: Equal/Sufficientarian/Prioritarian fly 100% shortest paths while Utilitarian
(49.3%) and Proportional (30.3%) detour substantially. Presented as a property of the
principles, and promoted to the abstract.

It is an artefact of mismatched budgets. Per-principle mean detour by fleet size:

| | N=6 | N=8 | N=14 | N=16 | N=22 | N=24 | N=30 | N=32 |
|---|---|---|---|---|---|---|---|---|
| Utilitarian budget | 4h | 4h | 4h | 4h | 600s | 600s | 600s | 600s |
| Utilitarian detour | 0.00 | 0.00 | 0.00 | 0.00 | 0.86 | 1.17 | 1.20 | 1.12 |
| Proportional budget | 4h | 4h | 4h | 4h | 600s | 600s | 600s | 600s |
| Proportional detour | 0.00 | 0.00 | 0.00 | 0.00 | 1.64 | 2.21 | 2.10 | 2.25 |

**Every non-zero detour comes from a 600 s run.** At all four fleet sizes given four
hours, Utilitarian and Proportional fly 100% shortest paths, exactly like the other
three. The table pooled 4 h rows for three principles against 600 s rows for two and
reported the gap as a property of the principles.

What survives: *at matched budgets all five principles fly every aircraft on a shortest
path.* That is simpler and stronger, and it is now stated in Sec. IV-B and Sec. V. The
subsection and `tab:detour` are deleted.

## R4. "Utilitarian and Proportional return bit-identical maps" -- WITHDRAWN

Claimed: at N=8 and N=16 the two produce the same routing, L1 distance exactly 0.00.

Two defects.

*The metric cannot see what it claims is absent.* `_occupancy` sums each community's
aircraft-timesteps over the whole horizon before comparing. Noise is concave in the
PER-TIMESTEP count, so two routings with identical totals can differ in noise -- and
these do:

| | N=8 | N=16 |
|---|---|---|
| occupancy L1 | 0 | 0 |
| totalAddedDB, Utilitarian | 10.2494 | 16.7798 |
| totalAddedDB, Proportional | 10.3112 | 16.7765 |
| paths identical | no | no |
| horizon T | 5 vs 6 | 5 vs 6 |

So the docstring claim that occupancy "is what the noise, and therefore the fairness,
actually depends on" is disproved by the paper's own rows.

*The claim exceeds what the rows support.* Both are `partial` at N=16. This project's
own status vocabulary says a partial row supports directional claims but "NOT orderings
or exact values" -- and exact equality is the strongest possible exact-value claim.

The subsection and `tab:distinct` are deleted. The Equal/Sufficientarian half of that
table was defensible (both proven optimal) and its content is retained in Sec. IV-C.

## What this says about the audit

`cap_audit.py` was built after R1/R2 to stop exactly this class of error, and it missed
R3 and R4. The reason is precise: it graded by status, and a table can be entirely
`partial` yet still confounded if some rows had 600 s and others four hours. The new
budget-homogeneity check tests, per grouping, whether the UNPROVEN rows share a budget
(proven rows are exempt -- more time cannot improve them). Run against the corpus it
reports:

  * across principles at one N -- **safe** (unproven rows share a budget at each N)
  * across N for one principle -- **CONFOUNDED for Utilitarian and Proportional**

which is exactly R3's error, now flagged automatically.

---

# R5 and the load confound (2026-09-05, second external review)

## R5. "On grid4 at N=16 Equal and Sufficientarian produce identical occupancy" -- FALSE

Traced to a bug in `analyze.table_distinct`, not to the data.

The function built its lookup as `{principle: row}` over every row in the sweep. That is
sound for `scaling.jsonl`, which holds one run per principle, but `grid4.jsonl` also
holds ablation controls (`g4abl|*|off|*`) and protected-set variants (`g4prot|*`). The
controls therefore **overwrote the treatments** for all five principles at demand 1.0,
and the table reported the controls' distances under the treatments' names.

| pair | identical? | L1 |
|---|---|---|
| `g4\|equal\|1.0` vs `g4\|sufficientarian\|1.0` -- the real pair | **no** | 18 |
| `g4abl\|equal\|off\|1.0` vs `g4abl\|sufficientarian\|off\|1.0` -- controls | yes | 0 |

The claim was true of the two runs with their objectives switched OFF. Corrected grid4
distance at N=16 is **0.13**, not 0.00. `table_distinct` now restricts to treatment rows
by key prefix and aborts with a visible note if any principle still has more than one
row at a demand -- a silent arbitrary pick is what caused this.

The sentence outlived the table that produced it: Sec. IV-F was withdrawn (R4) but the
grid4 replication paragraph still quoted its number. Deleting a result is not enough;
every sentence sourced from it has to be traced.

## The load confound -- DISCLOSED, cannot be removed

Phase 1 is budget-independent, so its wall time is a clean probe of machine contention.
Across the 40 configurations solved in more than one sweep:

  * median phase-1 ratio between fastest and slowest sweep: **3.10x**
  * maximum: **23.1x**

The long-budget sweeps ran on a markedly quieter machine. **Every 600 s-against-four-hour
comparison in this paper therefore changes two variables**, and all four retractions rest
on such comparisons.

Why the retractions still stand: both changes (more time, less contention) favour the
long run, and each retraction *withdraws* a claimed effect rather than asserting a new
one. A confound that makes the long run stronger cannot manufacture a null result.

Where it does bite, and is now said in the paper:

  * **Sec. IV-C, N=30.** Original: phase-1 21.4 s / 13.8 s, phase-2 610.8 s, unproven 149.
    Re-run: phase-1 7.4 s / 4.7 s, phase-2 287.4 s, **proven optimal**. The budget was not
    the binding constraint -- the load was. At nine-way contention 600 s was insufficient;
    on a quiet machine under five minutes sufficed. Both facts are now stated.
  * **Sec. IV-H.** `equal@32` has two proven runs, 802.6 s and 1118.9 s, of the same
    configuration. The paper now gives both and names the spread as contention.

`cap_audit.py` gains a load probe reporting the same 3.10x/23.1x. It is the one confound
the audit can detect but not correct: fixing it means re-running the corpus serially,
which at 107 solver-hours of measured work is not affordable.

## Other corrections this round

  * Sec. V asserted, 22 lines after retracting it, that Utilitarian "flies most over loud
    communities". Removed; the 65 dBA share is 27.3% under every principle.
  * Abstract said three retractions, Sec. V enumerated four. Now four in both.
  * "six such cells" killed -> **five** at N=32 (seven killed rows total, two of them at
    demand 3.0/4.0).
  * `tables/ablation.tex` stated a binding criterion that its own Equal and
    Sufficientarian rows fail. Caption rewritten: those two contribute no objective, so
    the metric shown for them is a by-product the solver never targeted.
  * "at matched budgets all five fly shortest paths" was unqualified and had no surviving
    body evidence. Now scoped to N <= 16, the only sizes where budgets are matched.
  * `tab:principles` shows Utilitarian and Proportional rounding to identical rows; the
    text now gives the true totals (16.7798 vs 16.7765) and notes paths and horizons differ.
  * The N=48 / N=64 saturation sweeps were run but unreported. Now one paragraph in
    Sec. IV-D: one of eight settled, and the zero-minimum property held in every routing
    returned, including at N=64.
  * "a factor of 2.4" -> "at least a factor of 2.4" (proven denominator, unproven numerator).

---

# R6 and the n=1 problem (2026-09-05, third external review)

## R6. Proportional's ablation verdict was computed from the wrong quantity

`plans.ablation` builds the Proportional control by clearing `optimizeProximity`, and
`payload.build_request` emits `proximityWeights` **only when that flag is set**. So the
control payload carries no price vector, the priced objective is uncomputable from the
solver's reply, and `analyze` silently substituted **total added dB** -- which is not
what Proportional minimises.

That substitution is what produced the sign change the table then read as a result:

| N | substituted metric (total dB) | Proportional's OWN priced objective |
|---|---|---|
| 8 | -47.6% | **-72.6%** |
| 16 | -53.5% | **-81.4%** |
| 24 | **+45.3%** | **+1.1%** |

The fix needs no new solves: `proportional_weights()` is deterministic given the
ranking, and both runs' paths are stored, so the priced sum is rebuilt offline and
applied to each. `analyze.principle_metric` now scores every principle on its own
objective -- spread for Equal, peak for Sufficientarian, protected-set noise for
Prioritarian, summed noise for Utilitarian, priced noise for Proportional -- rather than
scoring three of five on a quantity they do not optimise.

**What changes in the paper.** Proportional binds far harder than reported at low demand
(0.27x and 0.19x of control, not -47.6%/-53.5%) and does **not** bind at N=24 (1.01x,
marginally worse than control, while paying +82% arrival). The old +45.3% was an artefact
of the wrong metric; the new +1.1% is a real failure to improve.

## The central claim was reported at n=1 when n=3 was in hand

`ablation.jsonl` has always held 30 rows -- 5 principles x on/off x three demands
(N = 8, 16, 24) -- and Table III printed N=16 only. The claim "three of five bind on
nothing" was therefore a single-demand result with nine paired proven comparisons
sitting unused in the file, and N=16 happened to be the demand most favourable to the
two principles that do bind.

Table III now spans all three demands. What that exposes:

  * Equal, Sufficientarian, Prioritarian: arrival identical on/off at **every** demand
    (22/22, 44/44, 66/66). Nine paired comparisons, all proven. The central claim is
    now n=3 rather than n=1.
  * Utilitarian binds at all three but the effect **decays monotonically**: 0.37x,
    0.49x, 0.84x of control.
  * Proportional binds hardest at low demand and then **stops**: 0.27x, 0.19x, 1.01x.

The two principles that work best at workshop scale are the two that stop working first
as demand grows -- a finding that only exists because the other two demands were printed.

## The encoding speedup is now measured, and the claim was wrong

Sec. III-D said the max/min disparity encoding "is what brings problems of this size
into range at all", supported only by an arithmetic constraint count. `pairwise_bench.py`
builds both encodings on an otherwise identical phase-2 model and times them, checking
they agree on the objective (they do).

At N=6 the two encodings are equivalent (arrival 18 both) and:

| encoding | U-constraints | build | solve |
|---|---|---|---|
| max/min | 306 | 0.33 s | 0.64 s |
| pairwise | 25,200 | 3.00 s | **0.12 s** |

The pairwise form is **5x faster to solve** and 9x slower to build. Max/min wins on
total time (3.2x) entirely through construction cost, not search. The paper's framing --
that the pairwise encoding was intractable -- is not supported at this size. Larger N
is running; whatever it shows, the claim has to be restated in terms of what was
measured.

This was the one engineering claim in the paper with no experiment behind it, and the
first time it was run it contradicted the text.
