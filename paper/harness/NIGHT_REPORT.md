# Night report — fleet-size study, 2026-09-09

What actually happened. `NIGHT_PLAN.md` is what was intended, `DECISIONS.md` is why the
departures from the brief were allowed, `CONTRADICTIONS.md` is the list of paragraphs in
Sections I–III and V that the redirection breaks. The next session starts here.

**Status 2026-09-11: Lane A complete and proven; Lane B's first run was killed by a
machine restart with 12 of 16 cells unrun, and has been relaunched.** See "Lane B run 1
was interrupted" below. Nothing in Sections 3-5 depends on it finishing; the frontier it
reached is itself the Experiment 4 result.

---

## Machine and conditions

Windows 11, i9-13900H, 14 physical / 20 logical cores, 31.6 GB RAM, Python 3.11.5,
Z3 4.16.0, `solver_server_dB.py` at `f231cb9` **unmodified**. `par = 8` throughout,
recorded on every row as `runner_par`. No other load on the machine.

Every solve: `timeout_ms = 10^9` (≈11.6 days), `wall_kill` disabled. No row in the study
was shaped by a clock, and no comparison in Section IV crosses budgets.

---

## Phase 0 — Preflight — COMPLETE (01:34–01:50)

| step | result |
|---|---|
| `SOLVER` path | already correct; **replaced with a path derived from `__file__`**, as was the `sys.path` insert (D1) |
| `validate_payload.py` | **0 mismatches**, re-run after the `payload.py` changes, still 0 |
| `check_tex.py` | clean |
| `analyze.py` / `figures.py` read | loader reused, not reimplemented; `fig_routes`'s renderer factored into `_draw_map` and now shared with the new grid (D8) |
| `worker.py` extended | `countMatrix`, `noiseMatrix`, `runner_par`, `slack`, `setup`, `probe`, and `Checkpointer` |
| smoke solve | `smoke\|default\|equal\|0.25`, unlimited, via `runner.py`: **optimal in 1.25 s**, row carries `paths`, `countMatrix`, `noiseMatrix`, `runner_par` |

### Checkpoints, tested before anything long started

`results/checkpoints/<key>.json` every 600 s: elapsed, phase, the solver's progress dict.
To capture an incumbent, create `<key>.STOP` or `STOP_ALL`; one `main_ctx().interrupt()`
is delivered and the solver's own `_best_so_far` path salvages the incumbent **and
replays it against every hard constraint** before returning it.

Verified end to end on `ckt|default|proportional|0.5`: heartbeat on schedule, then the
stop produced `optimality: partial`, `stoppedEarly` set, `paths` / `countMatrix` /
`noiseMatrix` all present. Why it interrupts rather than reading Z3 from a second thread:
D2.

### ICRA 2027 deadline

`paper/README.md` states 15 September 2026, 11:59 PST, 8 pages hard including references,
double-anonymous, over-length returned without review — a check the repository records as
made against the CFP on 2026-09-05. **This session could not re-verify it: there is no
network access here.** The date is six days out. See the length note at the end.

---

## Phase 1 — Pilot at N=16 — COMPLETE, divergence check PASSED

Four conditions, unlimited budget, all **proven optimal**, 17 s for the sweep.
Utilitarian and Proportional ran as 900 s probes into `screen.jsonl` for the check only
(D4) — no probe row reaches any table, figure, or `fleet_metrics.csv`.

**Verdict: PASS on the dashboard's default setup, so `SETUP_MAIN = default` and Phase 1b
was not required.** 5 of 5 principles produce mutually distinct routings (pairwise
occupancy distance min 0.114, mean 0.189); 5 of the 6 headline metrics are visibly
spread. Full table in `results/screen_log.md`.

The one metric that misses its threshold is travel time (spread 0.12 against 0.25), which
is the brief's own hypothesis about the tight horizon. A single slack setup was screened
to settle it (D7) and the answer is in `screen_log.md`: with three extra timesteps,
Equal, Sufficientarian and Prioritarian **prove optimal and still fly the shortest-path
floor**, so their travel-time neutrality is a property of the principle, not of the
horizon. Utilitarian and Proportional do use the extra room (108 and 104 fleet hops
against a floor of 44), but from searches that had not terminated, so that is reported as
direction only and their noise values at `sl3` are explicitly **not** compared with the
default's.

---

## Phase 2 — Main sweep — Lane A COMPLETE, Lane B INTERRUPTED then RELAUNCHED

Two sequential lanes into one `results/fleet.jsonl`, each small-N-first (D3).

**Lane A — Equal, Sufficientarian, Prioritarian, baseline. 32 of 32 cells, all proven
optimal, 802 s.** Every fleet size on the ladder. `fleet|default|equal|2.0` (N=32) took
696 s — a cell that returns no weighted answer at all under the deployed 600 s budget, so
removing the budget bought a result that did not exist before.

**Lane B — Utilitarian and Proportional. 4 of 16 cells returned so far**, all proven:

| cell | wall | status |
|---|---|---|
| `fleet\|default\|utilitarian\|0.25` (N=6) | 78 s | optimal |
| `fleet\|default\|utilitarian\|0.5` (N=8) | 330 s | optimal |
| `fleet\|default\|proportional\|0.25` (N=6) | 4584 s | optimal |
| `fleet\|default\|proportional\|0.5` (N=8) | **29396 s** | optimal |

The last of those landed at 10:39, after **8 h 10 min** of unbroken search. It is the
clearest single vindication of removing the budget: the prior corpus recorded this
configuration as unsettled after four hours, and it is not intractable, only slow.

### Lane B run 1 was interrupted — 12 of 16 cells unrun

The eight cells searching past N=8 were killed **by a machine restart**, not by anything
in the harness. Evidence: every worker's heartbeat stops at the same instant,
`2026-09-09T19:09:43`, and `Win32_OperatingSystem.LastBootUpTime` is
`2026-09-10 02:43:41`. The runner reaped its dead children at 02:39, launched the four
queued cells, watched them die in 1.0 s each as the system went down, and exited. Twelve
rows landed as `NO_OUTPUT`.

Before dying, each had run without terminating for:

| cell | elapsed |
|---|---|
| Utilitarian N=14, N=16 / Proportional N=14, N=16 | 16.7 h |
| Utilitarian N=22 / Proportional N=22 | 16.6 h |
| Utilitarian N=24 | 15.4 h |
| Proportional N=24 | 8.5 h |

Those are the lower bounds Section IV-E and `fig:solve-time` now report. The run-1
heartbeats are preserved in `results/checkpoints_run1_killed/`.

`wall_kill` was correctly disabled (`10^9`), so nothing in `runner.py` killed them; and
`runner.py` deliberately does not count `NO_OUTPUT` as done, so the relaunch picked up
**exactly those 12 and skipped the 36 completed cells** — the resumability behaved as
designed. Lane B was relaunched 2026-09-11 00:07, `par = 8`, log `results/fleet_b2.log`.

**If this machine can restart itself again, the relaunch will meet the same end.**
Suspend automatic restarts (Windows Update active hours, or pause updates) before
relying on a multi-day run.

**36 cells on disk, all 36 proven optimal.** No `partial`, no `fallback`, no `killed`, no
`infeasible`. Both N=6 and N=8 now have a complete proven set of all six conditions.

---

## Phases 3–4 — Metrics, figures, tables — COMPLETE

* `metrics.py` — `derive(row, req)`, pure. **Self-test passes**: 18 checks on three
  pre-existing rows that carry no stored matrices, so `peakAddedDB`, `totalAddedDB`,
  `maxCount`, `tripHops`, `stationsTouched` and `peakSpreadDB` are a genuine second
  derivation, all identical.
* `metrics_run.py` → `results/fleet_metrics.{csv,json}`, 36 rows, plus the `cells()` /
  `metrics_index()` loader that figures and tables share.
* Figures → `tex/figs/`: `routes_grid`, `metric_vs_N`, `route_sharing`,
  `noise_over_time`, `solve_time`. Still-running cells are drawn as arrows from their
  elapsed time, read live from the checkpoint files.
* Tables → `tex/tables/`: `fleet.tex`, `capacity.tex`, `setup.tex`.
* `results/fleet_findings.md`, regenerated; every number carries its row key.
* `results/summary.md` regenerated; the old tables are untouched and still build.

### `verify_sec4.py` — new, and it earned its place

Every numeric claim in Section IV is asserted against `fleet_metrics.json`. **38 checks,
all passing.** It was written because two claims in the first draft were true of the four
conditions then on disk and false once a fifth landed, and it then caught a third and
worse error described below.

---

## Phase 5 — Section IV rewritten — COMPLETE

`tex/sec4_results.tex`, ~2,700 words, six subsections: Setup, then one per experiment,
then a summary. `check_tex.py` clean. All eight labels that Sections I–III and V
reference into Section IV still exist, so the document still builds.

### The three findings that carry the section

**1. A cap-based principle does nothing until the fleet outgrows the map.** At N=6 and
N=8, Equal, Sufficientarian and the baseline return *the same routing* — and this is the
strong form, checked on the count matrix at each individual timestep and on the multiset
of paths, not only on summed occupancy. From N=14 they separate and stay separated
(Equal 0.19–0.25 from baseline). Prioritarian and Utilitarian, which carry objectives
rather than caps, differ from the baseline at every size including N=6 (0.111 and 0.389).
Whether a principle does anything in low traffic is decided by how it was encoded, not by
which principle it is.

**2. The condition holding the fewest aircraft over any community is the loudest.** At
N=24 Equal peaks at 10.00 dB against the baseline's 7.78 while carrying 9 aircraft over
its busiest tile against 13. Both proven. Under D=10 the closed-form capacity is 9 / 90 /
900 aircraft at 45 / 55 / 65 dBA, so a cap on *added* noise makes loud communities a
hundred times cheaper to overfly; Equal's 45 dBA utilisation climbs 0.11 → 0.39 to N=24
while its 65 dBA utilisation never exceeds 0.01. The cap binds entirely on the quiet.

**3. Fairness is free in travel time here, and expensive in tractability.** Every proven
cell at every fleet size flies shortest paths: total hops equal the floor, and equal the
baseline's, for all six conditions to N=32. Arrival penalty is identical — 18, 22, 40,
44, 62, 66, 84, 88 — across the four cap-based conditions at every size, all proven. Yet
Utilitarian halves total added noise at N=8 (10.2 dB against 19.7) at zero travel cost,
by moving flight time off quiet communities (45 dBA share 22.7% → 9.1%). The whole cost
of the choice lands on *which* communities carry noise. The tractability cost is the
opposite of free: the cap-based conditions prove out to N=32 within a factor of 3.1 of
each other; both decibel-valued objectives stop at N=8, a fleet a quarter the size.

### An error caught, worth recording

The summary first said Proportional and Utilitarian return the same routing at N=6 —
their summed occupancy vectors are byte-identical. **That is the exact claim retraction 4
in `claims_audit.md` withdrew**, for the exact reason: a metric that sums over time
cannot see a difference in timing. Re-checked at the finer grain, they are *not* the same
routing — Proportional uses a six-step horizon where Utilitarian uses five, holds one
aircraft on the ground for two timesteps, and differs in the per-timestep count matrix.
The section now says what is true, and the overnight cells strengthened it rather than
weakening it: at **both** N=6 and N=8 Proportional lands within 0.1 dB of Utilitarian's
summed noise, on the same peak and the same 45 dBA share, while running a six-step
horizon against Utilitarian's five and differing in the per-timestep counts — for 59×
and 89× the solve time. `verify_sec4.py` asserts both halves at both sizes, so the wrong
version cannot come back.

`figs/routes_grid.pdf` has the same hazard by construction: its line widths sum over the
horizon, so the Utilitarian and Proportional panels at N=8 are drawn identically. The
caption now says so.

The same blindness applies to `occ_dist_vs_baseline`, which is why finding 1 above was
re-checked per timestep before being written.

---

## Hand-off

### To harvest the still-running cells

The paper reports only completed solves, so the running cells are left running. When they
are wanted as verified feasible routings:

```bash
cd paper/harness
touch results/checkpoints/STOP_ALL          # one interrupt per worker
# each writes a `partial` row with stoppedEarly set, paths and matrices intact
rm results/checkpoints/STOP_ALL
python metrics_run.py && python figures.py --fleet && python analyze.py
python findings.py && python verify_sec4.py && python check_tex.py
```

Those rows land in `fleet.jsonl` under their own keys, so `runner.py` will then treat
them as done. Z3 keeps no resumable state, so a stopped search restarts from zero either
way — stopping loses nothing that killing the process would not also lose.

### To continue instead

```bash
python runner.py plans/fleet_b.json     # resumable; skips the 3 completed keys
python plans.py fleet_stretch && python runner.py plans/fleet_stretch.json   # N=38,40
python plans.py fleet_default                 # only needed if SETUP_MAIN moves off default
```

### Nothing was dropped

The drop order in `NIGHT_PLAN.md` (stretch → `fleet_default` → largest remaining N) was
never invoked. `fleet_default` is unnecessary because `SETUP_MAIN` **is** the default, so
the reference sweep would duplicate `fleet.jsonl` exactly. `fleet_stretch` (N=38, 40) was
not started because Lane B has not cleared.

### Scope, as instructed

Not run: `who = People`, `propranking`, degeneracy/tie-breaking, "what a participant
sees", `caps`, `binding`, `grid4`, `reps`. Communities only.

---

## Open items for the next session

1. **`paper/` is not under version control.** `git status` reports it untracked. The
   rewrite of `sec4_results.tex` destroyed the only copy of `eq:capclosed`, which §III
   references; it was reconstructed from `figures.py: fig_capacity` and checked against
   the numbers in `fig:capacity`'s own caption, but there was no earlier copy to compare
   against. **Commit `paper/` before the next rewrite.**

2. **Length is worse, not better.** Section IV is ~2,700 words and carries eight floats
   (three `figure*`, two `figure`, three tables) — roughly 3.5–4 pages against a hard 8
   for the whole paper, which `README.md` already estimated at 11–12. Ranked drop list,
   cheapest first: `noise_over_time` (a `figure*`, and its finding — that all conditions
   share one two-peaked shape — is one sentence); `route_sharing` (single column, its
   trend is also in `metric_vs_N`); `setup.tex` (`SETUP_MAIN` is the default, so the
   table's every row reads "unchanged" and one sentence replaces it). Dropping all three
   costs no finding and recovers roughly a page and a half.

3. **`CONTRADICTIONS.md`** lists every paragraph in Sections I–III and V that the
   redirection breaks, graded FRAMING / SUPERSEDED / CONTRADICTED. Two are outright
   contradicted by tonight's data and must change before submission: §I contribution 2c
   ("three of the five principles bind on nothing") is now N-dependent, and §I
   contribution 3 (the 600 s framing) understates the result.

4. **`sec:mismatch` and `sec:degeneracy` still resolve but now point at adjacent
   material.** `check_tex.py` cannot see that; a read can.

---

# 2026-09-11 — the sweeps finished, and a claim was retracted

## Lane B finished, by harvest rather than by proof

Run 2 reached 15.4 h on the seven cells above N=8 without returning, after run 1 reached
16.7 h on the same cells. Two independent searches — Z3 keeps no resumable state — so the
lower bound is the larger, 16.7 h, not the sum. `STOP_ALL` harvested all eight through the
solver's own salvage path: `partial`, `stoppedEarly` set, paths and matrices intact,
each replayed against every hard constraint before being served.

Four cells (Utilitarian and Proportional at N=30 and N=32) were caught by the sentinel
still being on disk when they launched, recorded `phase1_stopped`, and are queued to
re-run. `runner.py` now treats `phase1_stopped` and `phase1_timeout` as unanswered so a
resume picks them up (D12).

**Final fleet state: 44 cells with an answer — 36 proven optimal, 8 verified feasible
routings — and 4 with no answer yet.**

## THE CORRECTION: most between-principle differences are below the solver's indifference

This is the significant result of the session and it retracts a claim I put into
Section IV two days ago.

The slack sweep was built to move travel time. It does not — but it measures something
more useful. Across horizon slack 1 to 4, **every cap-based condition attains the same
arrival penalty**: 22 at N=8, 44 at N=16, 66 at N=24, at every horizon. Arrival is the
only quantity Equal, Sufficientarian and the baseline minimise, and Prioritarian's own
objective evaluates to **0.0 at every slack and every fleet size**, so it pins nothing
either. Nothing any of the four optimises is improving. Yet the routing that comes back
changes, and with it the noise and the congestion.

That variation is the solver choosing among routings it is indifferent between, and it
sets a floor:

| N=16 | one condition, horizon 1–4 | between all four conditions | |
|---|---|---|---|
| peak added noise | **5.64 dB** | 2.22 dB | below the floor |
| max aircraft per tile | **5** | 4 | below the floor |
| tile-timesteps carrying 2+ | **5** | 3 | below the floor |
| total added noise | 8.4 dB | 8.9 dB | marginally above |
| extra hops | 0 | 0 | no difference either way |

**What was withdrawn.** Section IV-D led with "the condition holding the fewest aircraft
over any one community is also the loudest — at N=24 Equal peaks at 10.00 dB against the
baseline's 7.78". The measurements are right; the attribution was not. A 2.22 dB gap
cannot be read as a property of Equal when one condition covers 5.64 dB on its own. The
subsection now states the floor first and declines the claim. Section IV-B's congestion
ordering is qualified the same way.

**What survives, and why.** Anything that is an identity rather than a margin, or that
clears the floor:

* Equal, Sufficientarian and the baseline return the **identical** routing at N=6 and
  N=8 — verified per timestep and on the path multiset. A distance of exactly zero is
  not a margin.
* Travel time is zero for every proven cell at every fleet size and **at every horizon
  from floor+1 to floor+4**, all proven. The invariance is stronger than before.
* Utilitarian's N=8 reduction is 9.5 dB against a 5.4 dB floor — attributable.
* The 9/90/900 capacity asymmetry is analytic, not measured.
* The tractability frontier, and Proportional matching Utilitarian at 59×/89× the cost.

`verify_sec4.py` now has **43 checks**, five of them asserting both halves of the floor
comparison, so the retracted reading cannot come back.

## Travel time does separate — in a currency hops cannot see

Every condition flies the same distance with zero hovering, but at N=8 the departure
delay is 8 aircraft-timesteps for the four cap-based conditions, 9 for Utilitarian and
11 for Proportional. The decibel objectives buy their noise reduction by holding aircraft
**on the ground**, de-conflicting the fleet in time rather than routing it apart in
space (D13).

## New artefacts

* `compare.py` → `results/comparison.md` — the three metric families, plus the floor.
* `slack_sweep` / `slack_probe` / `cap_sweep` plans, and `figs/levers.pdf`.
* `report_html.py` → `paper/results_review.html`, published; now leads with the floor.

---

# Session 3 — 2026-09-11/12 — the study moved to a regime where the principles bind

## The setup, and why

`SETUP_MAIN = D6_protA`: cap **D = 6 dB** applied to all five principles (Equal and
Sufficientarian through `limit`, the others through a `req` override, so all five face one
hard constraint and differ only in their objective), and the Prioritarian protected set
moved to **stations 14, 4, 8** — Lower-Income Urban, University, Working-Class Homeowner:
the three busiest non-vertiport communities that are also low-income.

Chosen by a 100-cell screen (`results/setup_choice.md`), K=4 permutations, unlimited:

| setup | Equal | Suff | Prior | Util | Prop | active |
|---|---|---|---|---|---|---|
| `D6` / `D5` | yes | yes | no | — | — | 2/5 |
| `protA` | no | no | yes | — | — | 1/5 |
| **`D6_protA`** | yes | yes | yes | yes | yes | **5/5** |
| `D5_protA` | yes | yes | yes | yes | yes | 5/5 |

Neither knob alone works. Caps activate by binding exactly (utilisation 1.00, against
0.31 and 0.25 at the shipped D=10). Prioritarian activates because the protected set is
now where aircraft fly: its ablation control puts **3.45 dB** on the set at N=16 and the
objective removes it. `PROT_BURDEN` carries **zero** aircraft-timesteps at every fleet
size, which is why that objective was always 0.0 — a property of the set, not of the
principle. **D6 over D5** on attributable differences at N=24 (2/6 against 1/6) and
tractability headroom.

**Justification paragraph for §IV-A** is in the section already: choosing an operating
point at which a principle does something is a precondition for measuring what it does,
not a result. The shipped default is reported in one paragraph and `tables/reference.tex`.

## Encoding: both objectives run COUNT-weighted

`utilNoiseMode: false` and `proximityMode: "count"` — forms the solver already exposes,
no solver change. Screened at N=6/8/16, unlimited, K=4: **every cell proved, 4/4**.

| N=8 mean wall | dB form | count form | |
|---|---|---|---|
| Utilitarian | 328.9 s | **6.4 s** | 51× |
| Proportional | 29 395 s | **26.5 s** | **1110×** |

At N=16 the count form proves in 26 s and 119 s where the dB form did not prove in 15.4 h.

## Ladder status — 192 cells, `results/fleet_main.jsonl`

**184 answered, 8 `phase2_failed_timeout`, 34 harvested at H = 3600 s.**
All six conditions are proven 4/4 at every size **N = 6 … 24**. Above that:

| condition | proven to | above it |
|---|---|---|
| Equal | N=24 | N=30, 32: **no verified routing** in any permutation (disparity cap) |
| Sufficientarian | N=24 | harvested |
| Prioritarian | N=24 | harvested |
| **Utilitarian** | **N=30** | N=32 harvested |
| Proportional | N=24 | harvested |
| Baseline | N=32 | — |

## Each principle's response to N, with the attributability verdict

Attributable = means apart by more than the larger permutation band AND ranges disjoint.

- **Equal** — nothing below N=14; pins peak at 4.77 dB with **zero band** from N=14; pays
  2.75 fleet-hops from N=22 (attributable at N=22, 24); peak attributable at N=22.
  `fleet|D6_protA|equal|{1.25,1.5}|p{0..3}`
- **Sufficientarian** — identical behaviour to Equal throughout, as Prop. 1 predicts;
  3.00 and 2.75 hops at N=22, 24. `fleet|D6_protA|sufficientarian|{1.25,1.5}|p{0..3}`
- **Prioritarian** — same peak pinning, 2.50 hops, and additionally cuts **total** added
  noise attributably at N=14 and 16 (28.0 dB against the baseline's 37.7).
  `fleet|D6_protA|prioritarian|{0.75,1.0}|p{0..3}`
- **Utilitarian** — zero extra distance at every size; pays **3 aircraft-timesteps of
  departure delay** at N=22, 24 (attributable, zero band both sides); cheapest condition
  in the study to solve. `fleet|D6_protA|utilitarian|{1.25,1.5}|p{0..3}`
- **Proportional** — the only principle whose routing is **fully determined at every
  fleet size** (zero band on total added noise and on max aircraft per tile); largest
  total-noise reduction, attributable at five of six proven sizes; also pays in departure
  delay. `fleet|D6_protA|proportional|{0.25..1.25}|p{0..3}`

## The result worth taking to the paper

**A binding cap does not merely lower the peak — it removes the arbitrariness in it.**
From N=14 up, all five principles return a peak of exactly 4.77 dB in all four
permutations (band 0.00); the baseline returns 5.64 / 5.88 / 6.70 / 7.70 dB with bands of
2.22 / 2.22 / 1.76 / 3.98. The mechanism is integer capacity: `eq:capclosed` gives a
45 dBA tile exactly two aircraft at D=6, and the routing saturates it. Two aircraft over a
quiet tile add 4.77 dB.

Session 2's problem was that differences *between* principles were smaller than variation
*within* one. A binding constraint inverts that — it makes the outcome determinate.

## Generated

Figures: `routes_grid` (rows N=8/16/24/32 × six conditions), `metric_vs_N` (six panels,
mean line + permutation band, lines joining proven cells only). Tables: `response.tex`,
`fleet_main.tex`, `capacity.tex`, `reference.tex`. Generated but not `\input`:
`reference`, `capacity`, `solve_time`, `route_sharing`, `noise_over_time`, `floor`.

`verify_sec4.py` rewritten for this section: **10 checks, all passing**. `check_tex`,
its selftest, `metrics.selftest` and `validate_payload` all clean.

## Page count and the cut list

§IV is **1,971 words with 4 floats**, down from 3,441 and 7. Estimate for the whole paper
after the §I/§III/§V vocabulary pass: still **~10 pages against a hard 8**. The cheapest
remaining cuts, per `README.md`, are unchanged: §II to a half-column table (~500 words),
and §III's per-principle subsections merged (~400). Those two plus the §IV reduction
already banked bring it to roughly 8.5; reaching 8 still needs one further cut, and §IV-E
(solver performance) is now the cheapest candidate since the encoding result can be
stated in two sentences of §IV-A.

## Resume

```bash
cd paper/harness
python plans.py fleet_a && python runner.py plans/fleet_a.json   # resumable
python plans.py fleet_b && python runner.py plans/fleet_b.json
python metrics_run.py results/fleet_main.jsonl --stem fleet_main_metrics
python figures.py --fleet && python analyze.py && python findings.py && python compare.py
python verify_sec4.py && python check_tex.py
```

Stretch not run: N = 38, 40. `fleet.jsonl` (the shipped-default ladder) is untouched and
is the reference the paper cites in one paragraph.

---

# Session 5 — 2026-09-14/15 — Experiment 5: the decibel form against the count form

## The sweep

`results/fleet_db.jsonl`, plan `plans/fleet_db.json`. Utilitarian (`utilNoiseMode: true`)
and Proportional (`proximityMode: "noise"`, the payload default; `validate_payload.py` 0
mismatches) in decibel form on `D6_protA`, ordered like the ladder so ordering k pairs with
the count cell's ordering k.

* **Scale:** N = 6 … 24 × 4 orderings = 48 runs, `par = 8`, no Z3 budget.
* **Queue:** Lane 1 (N = 6, 8) ran first. Lane 2 was queued ordering-major (D30).
* **Launch:** 2026-09-14 04:00 UTC.
* **Harvest:** the controller placed HOLD at 00:00:13 UTC, saw all 8 running cells in phase
  2, and placed STOP_ALL at 00:02:13. Every worker had returned by 00:02:23, and the
  sentinels were removed. **H = 20.0 h.**
* **Outcome:** 19 proven, 8 harvested (verified, `partial`), 21 never launched.
* **Checks:** objective reconstruction 27/27; `verify_sec4.py` 42/42.

## Proof frontier and wall times

| decibel cell | orderings proven | mean wall (proven) | count form | slowdown |
|---|---|---|---|---|
| Utilitarian N = 6 | 4/4 | 48.7 s | 1.6 s | 30× |
| Utilitarian N = 8 | 4/4 | 295.6 s | 2.4 s | 124× |
| Utilitarian N = 14 | 2/4 (p0 10,611 s, p1 14,509 s) | 3.5 h | 6.0 s | — |
| Utilitarian N = 16 | 1/4 (p0 44,439 s) | 12.3 h | 8.5 s | — |
| Proportional N = 6 | 4/4 | 2,655 s | 4.2 s | 625× |
| Proportional N = 8 | 4/4 | 17,793 s | 8.2 s | 2,159× |

## Every harvested run

| run | elapsed | incumbent J_dB | Z3 lower bound | gap |
|---|---|---|---|---|
| `utilitarian_db|1.0|p1` (N = 16) | 25,010 s | 19.72 | 0.012826 (normalised), equal to incumbent | 0 %: at the optimum p0 proved, stopped in the arrival tier |
| `utilitarian_db|1.25|p0` (N = 22) | 60,229 s | 35.03 | −∞ | unavailable |
| `utilitarian_db|1.5|p0` (N = 24) | 54,322 s | 38.34 | −∞ | unavailable |
| `proportional_db|0.75|p0` (N = 14) | 69,504 s | 217.15 | −∞ | unavailable |
| `proportional_db|0.75|p1` (N = 14) | 33,609 s | 217.24 | −∞ | unavailable |
| `proportional_db|1.0|p0` (N = 16) | 68,864 s | 222.04 | −∞ | unavailable |
| `proportional_db|1.25|p0` (N = 22) | 59,330 s | 327.32 | −∞ | unavailable |
| `proportional_db|1.5|p0` (N = 24) | 53,152 s | 334.30 | −∞ | unavailable |

## Quality loss on the decibel objective

J_dB is in dB for Utilitarian and price-weighted dB for Proportional; count means are
over four orderings.

| principle | N | J* (or best reached †) | count routing | loss |
|---|---|---|---|---|
| Utilitarian | 6 | 9.52 | 20.79 [17.53, 24.07] | 11.27 (118 %), attributable |
| Utilitarian | 8 | 10.24 | 20.37 [18.36, 23.71] | 10.13 (99 %), attributable |
| Utilitarian | 14 | 19.18 | 35.66 [31.77, 38.58] | 16.48 (86 %), attributable |
| Utilitarian | 16 | 19.72 | 39.31 [36.01, 48.71] | 19.59 (99 %), attributable |
| Utilitarian | 22 | 35.03 † | 54.38 | ≥ 19.35 (≥ 55.2 %) |
| Utilitarian | 24 | 38.34 † | 53.85 | ≥ 15.51 (≥ 40.5 %) |
| Proportional | 6 | 109.43 | 128.00 (all orderings) | 18.58 (17.0 %), attributable |
| Proportional | 8 | 115.85 | 134.43 (all orderings) | 18.58 (16.0 %), attributable |
| Proportional | 14 | 217.15 † | 220.00 | ≥ 2.8 (≥ 1.3 %) |
| Proportional | 16 | 222.04 † | 224.79 | ≥ 2.8 (≥ 1.2 %) |
| Proportional | 22 | 327.32 † | 327.34 | ≥ 0.0 |
| Proportional | 24 | 331.37 † (the count routing) | 331.37 | ≥ 0: the count routing beats the decibel incumbent's 334.30 |

## Form comparison where both are proven (decibel vs count, N = 6 / N = 8)

`*` marks an attributable difference.

| metric | Utilitarian | Proportional |
|---|---|---|
| summed added noise | 9.54 vs 20.83* / 10.25 vs 20.39* | 9.60 vs 10.92* / 10.31 vs 11.63* |
| peak added noise | 4.77 vs 3.89 / 4.77 vs 3.89 | 4.77 vs 3.01* / 4.77 vs 3.01* |
| occupied tile-timesteps | 10 vs 15.25* / 10 vs 16.25* | 11 vs 13* / 11 vs 13* |
| tiles overflown | 6 vs 10 / 6 vs 9.5 | 6 vs 6 / 6 vs 6 |
| extra fleet-hops | 0 vs 0 | 0 vs 0 |
| departure delay | 7 vs 6* / 9 vs 8* | 9 vs 6* / 11 vs 8* |

## Corrections made on the way

* **The brief said the loss against a harvested incumbent is an upper bound.** It is a
  lower bound: the optimum can only lie at or below the best routing reached.
  `encoding.py` and the paper say lower bound. An upper bound needs a finite Z3 lower
  bound, and Z3 gives −∞.
* **A first draft said Proportional's count routing is "within 1.3 %" above N = 8.** N = 14
  is 1.31 %. `verify_sec4.py` failed the check, and the text now says 1.4 %.
* **`form_compare` once marked a one-ordering decibel cell attributable,** because
  `aggregate()` gives it a zero-width band. Bands now require four orderings, and such
  cells are *not testable*.

## Paper state

8 pages, `check_tex` clean, 42 checks. §IV-F, Table III, Fig. 5, and dB rows in Table IV.
Details and open decisions are in `../DRAFT_REPORT.md`.

## Resume

```bash
cd paper/harness
python plans.py fleet_db && python runner.py plans/fleet_db.json   # resumes the 21 unlaunched runs
python encoding.py && python export_plot_data.py && python verify_sec4.py && python check_tex.py
```
