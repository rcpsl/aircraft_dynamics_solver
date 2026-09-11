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
