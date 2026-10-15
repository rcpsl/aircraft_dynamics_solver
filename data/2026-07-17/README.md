# 2026-07-17 — U-sweep on one route triple

## What this data is

`route_3_5_11_results/` — a search for the tightest feasible disparity cap `U` on a
single scenario, 30 aircraft over a 16-station grid with `D = 90` (effectively
unconstrained, so `U` is the only binding rule).

- `search_log.csv` — every probe the search made: the `U` tried, whether it came
  back sat or unsat, the reason when it failed, the horizon `T` reached, and the
  elapsed seconds. This is the record of the search itself, including the failures.
- `summary.csv` — the five surviving examples, `U` = 9.0 to 11.0 in 0.5 steps.
- `example_N_U*.json` — the full solver reply for each.
- `example_N_U*_frontend.json` — the same reply reshaped for the dashboard of the
  time.

## What it shows

`U` between 9.0 and 11.0 is the interesting band for this scenario: all five solve,
and the horizon drops from `T = 7` at `U <= 10.0` to `T = 6` at `U >= 10.5` — a
tighter gap cap buys itself an extra timestep. Each solve took 260-269s.

`search_log.csv` also records that `U = 7.0` came back `unsat` with reason
`timeout` after 46.2s. That is a timeout, not a proof of infeasibility, and the two
should not be conflated when reading this file.

Note `totalTransit` and `totalUtilNoise` are empty in `summary.csv`: the solver only
reports them when the utilitarian objective is switched on, and it was not.

## Solver version

Produced by `solver_server_dB.py` as it stood on 2026-07-17, i.e. commit `0122b47`
(2026-07-16, "harden dB solver against multiplier-driven constraint blowup and
concurrent-request crashes"). That is **two commits before** the first solver state
replayed in this repository's history, so the exact file is not in this repo. The
nearest recorded version is the first solver commit here (`366a85d`, 2026-07-19).

Between `0122b47` and today the solver changed in ways that affect these numbers
directly — most of all `9e0be66` (2026-07-30), which replaced the pairwise `U` table
with a max/min encoding and cut the model from ~110k assertions to ~2,089. **The
260-269s solve times here are not comparable with current timings.** The feasibility
results should still hold, since the encoding change is documented as sound and
complete, but they have not been re-run.

## Status

Superseded as a dataset. It was gitignored in the original repository and is kept
here for the record of the `U` search, not as a current result. It uses a 16-station
grid, where the current dashboard uses 25.
