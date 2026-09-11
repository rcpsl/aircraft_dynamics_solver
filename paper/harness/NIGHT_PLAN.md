# Night plan — fleet-size study

Written at the end of Phase 0, 2026-09-09 01:50 local. What each phase runs, in order,
with the estimate it was scheduled against. `NIGHT_REPORT.md` records what actually
happened; `DECISIONS.md` records the judgement calls.

## Machine and parallelism

Windows 11, i9-13900H, 14 physical / 20 logical cores, 31.6 GB RAM.
Python 3.11.5, Z3 4.16.0. Solver `solver_server_dB.py` at `f231cb9`, unmodified.

**`par = 8`** (cores − 2, capped at 8) for every sweep in the study. It is stamped on
every row as `runner_par`, because solve times are comparable only within one sweep at
one level of contention. No other load was placed on the machine during the night.

## Budget

`timeout_ms = 10**9` (≈11.6 days of Z3 budget) and `wall_kill = 10**9` s. Neither can
fire. A row is `optimal` or `infeasible`; a `partial` can now arise only from a
deliberate stop (see the checkpoint note), and carries `stoppedEarly`.

## Checkpoints

`worker.py` writes `results/checkpoints/<key>.json` every 600 s: elapsed wall time,
phase, and the solver's progress dict. To capture the incumbent of a cell that must be
stopped, create `results/checkpoints/<key>.STOP` (or `STOP_ALL`); the worker delivers
one `main_ctx().interrupt()` and the solver's own `_best_so_far` path salvages the
incumbent, verifies it against every hard constraint, and returns it as `partial`.
Tested end to end before Phase 1 (see `DECISIONS.md` D2).

## Conditions

Six per fleet size: the five principles, plus `baseline` — the same fleet with
`D = U = 30` and every `optimize*` flag off, i.e. the solver's shortest-time routing
with no fairness constraint and no fairness objective. Soft T and the arrival tie-break
stay on in all six, so the only thing that moves is the fairness term.

## Phases, in order

| # | plan | jobs | estimate | rests on |
|---|---|---|---|---|
| 0 | preflight | — | 30 min | — |
| 1 | `pilot` (4 tractable conditions, N=16) + `probe` (Utilitarian, Proportional, capped) | 4 + 2 | 20 min | prior N=16 walls: 55–75 s each |
| 1b | `screen` — knob search, only if Phase 1 fails the divergence check | ≤ 36 | 1–3 h | — |
| 2 | `fleet` Lane A: Equal, Sufficientarian, Prioritarian, baseline × 8 sizes | 32 | 30–60 min | prior walls summed / par |
| 2 | `fleet` Lane B: Utilitarian, Proportional × 8 sizes | 16 | does not terminate | see below |
| 3 | `metrics.py` → `fleet_metrics.csv` / `.json` | — | minutes | — |
| 4 | `figures.py` / `analyze.py` → 5 figures, 3 tables | — | minutes | — |
| 5 | `tex/sec4_results.tex` rewrite | — | — | Phases 2–4 on disk |

## Where the tractability frontier is expected to sit

From the prior corpus (`results/*.jsonl`, 600 s and 4 h budgets — context only, none
of it is reused as paper data):

| principle | proven optimal at | still unproven after 4 h |
|---|---|---|
| Equal | N ≤ 30 | N = 32 fell back at 600 s; expected to prove with no budget |
| Sufficientarian | N ≤ 32 | — |
| Prioritarian | N ≤ 32 (400 s at N=32) | — |
| Utilitarian | N = 6 (75 s), N = 8 (337 s) | N ≥ 14 |
| Proportional | N = 6 (4 649 s) | N ≥ 8 |

Utilitarian's proven times grow ≈ 4.5× per two aircraft, which puts N = 14 near 8 h and
N = 16 near 38 h if the trend holds. Proportional is steeper still. **Lane B is
therefore expected to prove Utilitarian to N = 8 and Proportional to N = 6, and to
leave the rest running.** That frontier is a result, not a shortfall: it is the answer
to "which principles are tractable to which fleet size when the clock is removed", and
it is what Experiment 4 reports.

Lane A and Lane B run sequentially into one `results/fleet.jsonl`, each ordered small-N
first, for the reason in `DECISIONS.md` D3.

## Drop order if Phase 2 overruns

As instructed, and recorded when taken:

1. `fleet_stretch` (N = 38, 40)
2. `fleet_default` reference runs
3. the largest remaining N

Budgets are never capped to make something fit. Cells still running are left running,
their checkpoints in place, and reported as "proven to N = k; beyond that a verified
feasible routing".

## Scope, explicitly not run

`who = People`, participant rankings (`propranking`), degeneracy / tie-breaking,
"what a participant sees", `caps`, `binding`, `grid4`, `reps`. Communities only.

## Commands to resume

```bash
cd paper/harness
python plans.py fleet && python runner.py plans/fleet.json      # resumable; skips done keys
python metrics_run.py                                           # -> results/fleet_metrics.{csv,json}
python figures.py && python analyze.py
python check_tex.py
```
