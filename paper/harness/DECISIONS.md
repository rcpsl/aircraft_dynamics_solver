# Decisions taken without asking

The session was left running with standing authority to pick the better option and
record it. Every judgement call that changed what ran, or departed from the written
brief, is here with its reason. `NIGHT_REPORT.md` records what happened; this file
records why it was allowed to.

Machine for all of it: Windows 11, i9-13900H, 14 physical / 20 logical cores, 31.6 GB
RAM, Python 3.11.5, Z3 4.16.0. `par` budget = cores - 2, capped at 8, so **par = 8**.

---

## D1. `worker.py`'s solver path is derived, not hard-coded

The brief says to fix the hard-coded `SOLVER` path first. It was already correct for
this machine, but it was still an absolute string, and so was the `sys.path` insert
next to it. Both now derive from `__file__`. Nothing about the run changes; the harness
stops being machine-specific.

## D2. The incumbent checkpoint interrupts rather than reads

The brief asks for "the current incumbent ... every 10 minutes". Written literally that
means a second thread calling `opt.model()` while `check()` is running on the same Z3
context. `solver_server_dB.py` says at `_solve_lock` that this corrupts Z3's AST state
and crashes nondeterministically, and it is the reason the production server serializes
every solve. Doing it to a sweep that runs for days would trade a rare inconvenience
for a random one.

What `Checkpointer` in `worker.py` does instead:

* **Heartbeat, every 10 min, no Z3 involved.** `results/checkpoints/<key>.json` carries
  elapsed wall time, the phase, and the solver's own progress dict. That is the "known
  lower bound on effort" the brief wants for a cell still running in the morning.
* **Incumbent on demand.** Creating `results/checkpoints/<key>.STOP` (or `STOP_ALL`)
  delivers exactly one `main_ctx().interrupt()` — the one cross-thread call Z3
  documents as safe, and the one `/cancel` already uses. The interrupted phase-2 check
  returns `unknown`, which is the solver's own `_best_so_far` path: it salvages the
  incumbent **and replays it against every hard constraint** via `_model_is_feasible`
  before returning it. The row lands as `partial` with `stoppedEarly` set.

So the incumbent is captured through the production salvage path, verified, rather than
scraped out from under a running search. Tested end to end before anything long
started: `ckt|default|proportional|0.5` ran 60 s, took the STOP, and returned
`optimality=partial`, `stoppedEarly` set, with `paths`, `countMatrix` and `noiseMatrix`
all present. Verified feasible routing, on demand, no thread-safety risk.

The interrupt is only delivered while `S._in_check` is true. An interrupt that lands
between checks stays on the context and would kill the salvage replay instead — see
`_drain_interrupt` in the solver.

## D3. Phase 2 runs as two sequential lanes, into one file

The brief says "small N first, all six conditions per N", `par = 8`, one
`results/fleet.jsonl`. Taken literally the ladder never completes, and the reason is in
the prior data:

| principle | proven at | not proven at |
|---|---|---|
| Equal / Sufficientarian / Prioritarian | every N to 32, seconds to ~400 s | -- |
| Utilitarian | N=6 (75 s), N=8 (337 s) | N=14, N=16 in 4 h |
| Proportional | N=6 (4 649 s) | N=8 and up in 4 h |

Thirteen of the 48 jobs (Utilitarian from N=14 up, Proportional from N=8 up) do not
terminate on any horizon this session has. Thirteen non-terminating jobs against
`par = 8` means every slot is permanently occupied before the sweep reaches N=22, and
the cheap Equal / Sufficientarian / Prioritarian / baseline cells at N=22, 24, 30, 32 —
the ones that *would* prove out — never start. Interleaving does not just delay the
tractable ladder, it prevents it.

So Phase 2 runs as two runner invocations against the same `results/fleet.jsonl`,
**sequentially**, each small-N-first:

* **Lane A** — Equal, Sufficientarian, Prioritarian, baseline. 32 jobs. Terminates.
* **Lane B** — Utilitarian, Proportional. 16 jobs. Runs until stopped; how far it gets
  is the tractability result.

Sequential, not concurrent, because two runners appending rows that carry `paths` and
two 25xT matrices to one file would interleave partial writes. One file, as asked,
because everything downstream reads one file. `runner_par` is on every row, so the
contention a timing was measured under travels with it.

This serves the brief's stated purpose — "the proven part of the ladder is complete
early" — which the literal ordering defeats.

## D4. The divergence check uses capped probes for Utilitarian and Proportional

Phase 1 wants all five principles at N=16 to decide the setup. Utilitarian and
Proportional do not settle at N=16 on any budget available, so an unlimited pilot cell
for them would block the decision indefinitely.

They therefore run once, at a 900 s cap, into `results/screen.jsonl` marked
`probe: true`, purely to feed the divergence check. Screening is a decision procedure,
not a result, and the brief's budget rule governs paper data. Two consequences, both
recorded rather than hidden:

* No probe row ever reaches a table, a figure, or `fleet_metrics.csv`.
* What a probe contributes is an *occupancy vector* — a real property of a real
  constraint-satisfying routing, which the status vocabulary in the project README
  already licenses reading off a `partial` row. It is not read as an optimum.

Their unlimited runs happen once, in Phase 2 Lane B, rather than twice.

## D5. Prior sweeps cannot leak into the new files

`analyze.load` upgrades a row whenever another sweep holds a stronger run of the same
configuration, matched on `cfg`. Several fleet-study cells have a `cfg`
byte-identical to a 600 s `scaling` cell, so the merge would have seated a 600 s
incumbent inside an unlimited-budget table — precisely the error class the redirection
exists to remove, and the source of every retraction in `claims_audit.md`.

`pilot`, `fleet`, `fleet_default` and `screen` are added to `MERGE_EXEMPT`, which
blocks it in both directions: they are neither upgraded from nor used to upgrade.

## D6. `payload.py` gains an ambient-map parameter instead of an edit

Screening knob 6 varies the ambient map. Editing `BASELINE` in place would also move
the Proportional price vector, because `prop_factor_scores` reads the same map for its
`ambient` factor — the setup would then change two things and the screen would not know
which one separated the principles. `ambient_map(kind)` is threaded through
`build_request` and `proportional_weights` as a parameter, default unchanged.
`validate_payload.py` still reports 0 mismatches against the shipped dashboard JS.

`aircraft_db` is a parameter now too (knob 3), same reasoning, same default.

## D7. The default setup passes; a slack screen runs anyway, as a side note

The Phase-1 divergence check **passed on the dashboard's default setup**, and by a wide
margin: 5 of 5 principles produce mutually distinct routings (pairwise occupancy
distance min 0.114, mean 0.189) and 5 of the 6 headline metrics are visibly spread.
The rule was fixed before the data was seen, so it is applied as written:
`SETUP_MAIN = default`, Phase 1b is not needed, and Phase 2 runs on the default.

The one metric that does not clear its threshold is travel time — avg trip hops spread
0.12 against a 0.25 threshold. That is the brief's own hypothesis showing up: at the
default, `T_max` is the Chebyshev floor plus one (plus zero when the Utilitarian term is
live), so there is barely a timestep to detour into. Equal, Sufficientarian and
Prioritarian all sit exactly on the shortest-path floor; Utilitarian (2.81) and
Proportional (2.88) buy what little detour the horizon allows.

Rather than change the setup after seeing the data — which is how four of the five
retractions in `claims_audit.md` happened — the default stays, and **one slack setup
(`sl3`) is screened separately at N=16**, logged in `screen_log.md`, and cited in one
sentence of Sec. IV-C. It answers "what would these principles do with room to detour"
without any paper number resting on it. It runs after Lane A and before Lane B, costing
Lane B about 20 minutes of a run measured in days.

## D8. `fig_routes` now uses the shared renderer

The new `routes_grid` needed a map renderer, and `fig_routes` already had one inline.
Two copies of the same drawing code would drift, and the old copy hard-coded
`P.build_streams(1.0)` and `P.BASELINE`, so it could only ever draw the default setup at
N=16. Both now call `_draw_map(ax, row, req, ...)`, which takes its ambient shading and
its streams from the request the row was actually solved from. `figs/routes.pdf`
re-renders unchanged in style.

## D9. `divergence.check` needed a setup filter, and had produced one wrong table

`screen.jsonl` holds every screened setup in one file, and `principle_of` reads the
condition out of the key, which is identical across setups (`scr|sl3|utilitarian|1.0`
and `probe|default|utilitarian|1.0` both say "utilitarian"). The first `sl3` check
therefore pooled both setups and, both rows being `partial`, kept whichever came first
in the file — reporting the **default** setup's Utilitarian and Proportional trip
lengths under the `sl3` heading.

Caught by checking `T_used` before trusting the table: the tractable four showed
`T_used = 8`, so the slack had plainly taken effect, yet the Utilitarian and Proportional
trip lengths were byte-identical to the default's. `check()` now takes an explicit
`setup` and every invocation passes one; `screen_log.md` was deleted and both checks
re-run. The corrected `sl3` numbers are materially different (avg trip hops 6.75 and
6.50, not 2.81 and 2.88) and change what the screen means — see `screen_log.md`.

The `default` verdict was never affected: nothing else was in the file when it ran, and
re-running it with the filter reproduces it exactly.

## D10. `pilot.jsonl` is not part of the paper's data set

Its four cells are the same experiment as the fleet sweep's N=16 cells — same setup,
same conditions, same unlimited budget — under different keys, so loading both seated
two rows for one cell and let an arbitrary one win. `metrics_run.DEFAULT_FILES` reads
`fleet.jsonl` and `fleet_default.jsonl` only. The pilot stays on disk as the Phase-1
record and can be passed explicitly.

---

# 2026-09-11 — finishing the sweeps, and the travel-time question

## D11. The eight unfinished cells were harvested, not waited out

Lane B's run 1 reached 16.7 h on Utilitarian and Proportional above N=8 without
returning; run 2 reached 15.4 h on the same cells, also without returning. Those are two
*independent* searches — Z3 keeps no resumable state — so the correct lower bound is the
larger of the two, 16.7 h, not their sum. What the pair establishes is that ~16 h is not
close to enough, twice over, and the growth rate (77 s → 329 s → >16 h for three steps up
the ladder) puts N=14 days away.

Waiting longer would not have produced proofs, and the comparison the work now needs —
performance against principle, on every metric family — needs every cell to have *an
answer*. `STOP_ALL` was dropped and all eight returned through the solver's own salvage
path: `partial`, `stoppedEarly` set, paths and matrices intact, each replayed against
every hard constraint before being served.

Those rows are used for routing properties and never as optima. `verify_sec4.PROVEN`
makes the filter explicit rather than assumed (D16).

## D12. `phase1_stopped` and `phase1_timeout` no longer count as done

The `STOP_ALL` sentinel was still on disk when the runner launched the four queued cells
behind the harvested eight, so all four took an interrupt during phase 1 and recorded
`phase1_stopped` — feasibility never decided, no answer at all. `runner.py` counted them
as done, which would have silently dropped them from every future resume.

It now keeps one explicit set:

```python
UNANSWERED = {"NO_OUTPUT", "phase1_timeout", "phase1_stopped"}
```

`phase1_noise_cap`, `_unreachable` and `_structural` are deliberately *not* in it: those
are proofs that no routing exists, derived without search, and are real answers. Neither
is a phase-2 stop, which leaves a verified feasible routing.

## D13. Travel time does separate the principles — just not in distance

The ladder shows `extra_vs_floor` spread of exactly **0 at all eight fleet sizes**, so
"principles do not cost travel time" looked like the finding. It is not the whole finding.
The arrival penalty *does* separate, by up to 3 aircraft-timesteps, at the sizes where
the decibel objectives are proven — and hops cannot see why.

`metrics.derive` now records `departure_delay_total`, `departure_delay_max` and
`hover_steps_total`. At N=8, every condition flies 22 hops with zero hovering, and:

| condition | departure delay |
|---|---|
| Baseline / Equal / Sufficientarian / Prioritarian | 8 |
| Utilitarian | 9 |
| Proportional | 11 |

The two decibel objectives buy their noise reduction by holding aircraft **on the
ground** and staggering the fleet in time, not by routing it apart in space. That is a
second currency, invisible to every distance metric, and it is the honest answer to
"travel time shows no difference".

## D14. Two new sweeps, because one lever moves only half the menu

A flat metric is only worth reporting once you have shown what does move it, so two
levers were designed against different halves of the menu:

* **`slack_sweep`** (E5, unlimited budget, paper grade) — horizon slack 1–4 for the four
  conditions that prove out. Result: **nothing moves.** Zero extra hops and identical
  departure delay at every slack value, all proven. Given four extra timesteps they use
  none. Combined with the earlier screen, where Utilitarian and Proportional fly 108 and
  104 hops against a floor of 44 at slack 3, the lever separates *objectives* from
  *caps* rather than moving all five.
* **`cap_sweep`** (E6) — D ∈ {3,4,5,6,8} for Equal and Sufficientarian, the two
  principles the cap *is*. This is the lever left for them: at D=4 a 45 dBA community
  holds one aircraft, so routing around a full quiet tile becomes the only option.
  D=3 is included because an infeasible cell is a real answer about where the rule stops
  being satisfiable at all.

## D15. Rows with no answer are dropped from `fleet_metrics`

`derive` on a row with no `paths` returns a shell of `None`s, which then reads downstream
as a cell that has data in every column. `metrics_run.build` now skips anything in
`runner.UNANSWERED`; unfinished cells are reported from the runner log and the
checkpoints, as "searching", rather than as rows of dashes.

## D16. Every cross-condition check is restricted to proven cells

Harvesting the incumbents broke four `verify_sec4` checks, correctly: a stopped search
pays extra arrival time *for having been stopped*, so letting one into a travel-time
comparison manufactures precisely the difference being tested for. The checks now filter
through `PROVEN()`, and Section IV's Prioritarian claim is qualified to "the lowest total
added noise of any condition **proven** at those sizes", noting that Utilitarian's
incumbents are lower but unsettled.

## D17. The indifference floor is measured twice, and incomplete floors are not reported

The slack instrument has one weakness a reviewer will find: a wider horizon is a strictly
*larger* feasible set, so a condition could in principle have done genuinely better in
it. (None does — arrival is identical at every horizon — but the objection exists.)

`perm_sweep` removes it. Permuting the order the aircraft are listed in leaves the same
origin–destination pairs, the same fleet and **the same feasible set**: every routing
available before is available after, and the optimum is the same routing under a
different name. Z3's search order follows its variable-creation order, which follows the
aircraft order, so the permutations land on different members of one optimal set. The
range they cover is the tie-break with no confound at all. The generated plan was checked
to preserve the OD multiset exactly before it was queued.

Second guard, added after nearly publishing an inflated number: **a floor measured over
fewer settings is an underestimate**, which inflates the spread-to-floor ratio and makes
a difference read as attributable when it is not. N=24 briefly showed ratios above 1.0
for exactly that reason — only 8 of its 16 slack cells had finished. Both `fig_floor` and
`compare.sensitivity` now omit any fleet size whose floor is incomplete, and say so,
rather than report a number that will move.

## D18. Two figures dropped from Section IV, none deleted

Adding `fig:floor` took Section IV to nine floats and ~3,500 words, which is about five
pages against a paper `README.md` already estimates at 11–12 for a hard 8. The floor
figure is now the most load-bearing thing in the section, so the space came from
elsewhere: `route_sharing` and `noise_over_time` are no longer `\input`, and each keeps
one sentence in the text instead.

Both are still generated and current, and the omission is commented in the tex. This is
the convention `tables/caps.tex` and `figs/tradeoff.pdf` already follow. Section IV is now
7 floats and 3,441 words.

## D19. `.tex` is edited only through the editor, never a heredoc

`paper/README.md` warns that shell heredocs and `python -c` eat backslashes in this
environment, which is why `check_tex.py` exists at all. Trying to drop the two floats with
a heredoc turned `\begin` into a backspace control character — caught only because the
script asserted its match first and wrote nothing. Every `.tex` edit in this session goes
through the editor, and `check_tex.py` runs after each one.

## D20. The cap sweep's N=32 tail was stopped after 2.3 h, and most of it yielded nothing

Five cells at N=32 ran 130 minutes without returning, two of them still in **phase 1** —
feasibility itself undecided under a disparity cap of 3 or 4 dB with 32 aircraft. They
were blocking the rest of the queue, so all five were stopped with per-cell `.STOP`
files. What came back is worth recording precisely, because three different failure
modes look alike in a table:

| cells | status | what it means |
|---|---|---|
| `cap\|5,6\|equal`, `cap\|4\|sufficientarian` | `phase2_failed_timeout` | the interrupt found **no incumbent Z3 could verify**, so there is no weighted answer at all; the row carries phase 1's unweighted route and must never be read as the principle's |
| `cap\|3,4\|equal` | `phase1_stopped` | feasibility never decided — **not** infeasible |
| `cap\|3\|sufficientarian` | `phase1_noise_cap` | proven no routing exists, derived without search |

So the tight end of the cap range at N=32 — exactly where the detour lives — is out of
computational reach. The usable N=32 results are Sufficientarian at D=5, 6 and 8.

`verify_sec4` asserts that the `phase2_failed` rows carry no optimality verdict and are
flagged `fellBackToPhase1`, and that `analyze.status_mark` calls the stopped cells
`unsettled` rather than `infeasible`.

## D21. The cap's detour window widens with the fleet — the one fleet-size effect on travel time

Everything else in this study says travel time is invariant. This is the exception, and
it is proven on both ends:

| Sufficientarian, extra hops above the floor | D=8 | D=6 | D=5 | D=4 | D=3 |
|---|---|---|---|---|---|
| N=16 | 0 | 0 | 0 | +4 | proven infeasible |
| N=32 | 0 | +4 | +8 | no answer | proven infeasible |

A cap that is free at N=16 costs eight fleet-hops at twice the fleet, every cell proven
optimal and at capacity utilisation 1.00. "What does this principle cost" is therefore
not a property of the principle alone — it is a property of the principle at a fleet
size. Reported for Sufficientarian only: above N=25 the tool stops sending D alongside U
for Equal, so the two are not tightening the same quantity there.

## D22. A bad edit to `verify_sec4.py`, and the recovery

Fixing the D=3 check, I spliced the file by string index on an assumed ordering of two
markers that did not hold, duplicating three check blocks. The first repair was worse: it
split on any line starting with `@check(` **or** `def `, which separated every decorator
from its function, and then deduplicated the functions — all of which are named `_`.

Recovered because a copy had been taken before the first edit. The working dedup splits
only at a decorator, or at a `def` **not preceded by one**, so a check stays bound to its
body. Result: 53 checks, no duplicates, all passing.

The general lesson, already in the project's README for `.tex` and now true of the
harness too: **edit source through the editor, not by index arithmetic on a string.**
The only reason this cost minutes rather than the session is that the file was copied
first and `ast.parse` was run after.
