# full_routes/ — Full Aircraft Routing Data

## 1. What this is

The 120 CSVs in `equal_allocation/`, `sufficientarian/`, `utilitarian/`, and
`prioritarian/` only ever stored *aggregated* per-station summaries — no file
retained the actual solver `paths` array (which station each aircraft occupies
at each timestep). This folder re-solves every one of those 120 scenarios
from its exact documented config and adds the missing per-aircraft routing
table, plus explicit demand-fulfilled figures, while keeping every
previously-existing per-zone column unchanged.

**Coverage: 115 of 120 files (95.8%).** Every produced file passed an
integrity check (routing table present, zone table present, exactly 16 zone
rows) before this report was written. See §4 for the current 5 remaining
files and — importantly — per-file reasons that are **not all the same
root cause**; don't assume they're one uniform gap.

**See also**: `DASHBOARD_DATA_INTEGRATION_V2.md` in this folder covers a
newer, separate addition — a 5th fairness domain (`proportional/`, complete
at 12/12) — and the full dashboard-wiring picture across all five domains.

## 2. File format

Each file has this structure:

```
# domain,<equal_allocation|sufficientarian|utilitarian/<utilitarian|utilitarian_peak>|prioritarian>
# combo,<s2-65_s6-55|s2-65_s6-45|s2-55_s6-55|s2-55_s6-45>
# mode,<domain-specific: community_equal/people_equal, unweighted/weighted, no_weight/weighted, community/people>
# <domain-specific solver params: D, U, hardT, T_max, weightTime, weightUtilitarian,
#  weightPrioritarian, protectedStations, lens, target_dB, metric, variant, cap, ...>
# N,<physical aircraft count actually flying>
# aircraftMultipliers,<list, one weight per aircraft>
# totalTraffic,<sum of aircraftMultipliers -- the "demand fulfilled" number>
# maxTraffic,56   <- the full base fleet's total weighted demand (always 56)
# demandFulfilledPct,<totalTraffic/56 * 100>
# historicalValue,<only present when a historical value existed to compare against>
# reproducedValue,<what this re-solve actually found>
# matchesHistorical,<True/False -- only present for equal_allocation>
Time Steps (T),<T>

Routing (station per aircraft per timestep):
Aircraft,Multiplier,Start,End,T0,T1,...,T<T-1>
1,<mult>,<start_station>,<end_station>,<station at t=0>,<station at t=1>,...
2,...
...

Zone,Avg Added dB,Avg Total dB,Peak Added dB,Peak Total dB,Avg Aircraft,Peak Aircraft
Zone 1,...
...
Zone 16,...
```

The `Zone,...` table is byte-for-byte the same schema as every other CSV in
`dB_target_sweeps/` — nothing about the existing dashboard-facing format
changed, this folder only adds to it.

## 3. The tied-optimal caveat — read before trusting an exact number

For `equal_allocation`'s `community_equal` mode (and to a lesser extent
`people_equal`), the objective is weak — mostly just a soft time penalty —
so **many structurally different routings tie for the same optimal cost**.
Confirmed empirically before generating this data: solving the *exact same*
config twice in a row can return different (but equally valid) results:

```
trial 0: max avg_added = 1.3632
trial 1: max avg_added = 1.7932
trial 2: max avg_added = 1.7932
```

This isn't a bug — `equal_allocation/README.md` §9 documents the same
phenomenon ("Z3 finds structurally different tied-optimal solutions"). The
original data collection never recorded which aircraft subset was used for
the `N7_mult1`/`N4_mult1` fleet-shrink variants, so exact historical
reproduction isn't always achievable — not because of a missing parameter,
but because the historical run itself was one arbitrary pick among several
valid ties.

**How this dataset handles it**: every `equal_allocation` file carries
`historicalValue`/`reproducedValue`/`matchesHistorical` in its preamble.
Across the 44 successfully-produced `equal_allocation` files: **19 matched
the historical value exactly, 25 found a different but equally valid
tied-optimal solution** (flagged `matchesHistorical,False` with an explanatory
`note` line). `sufficientarian` and `prioritarian` don't have this issue —
their objectives are strong enough to pin down a unique answer, confirmed by
an exact zone-by-zone match against the pre-existing sufficientarian D8 file
before this run started.

## 4. The 5 remaining missing files — two different root causes, not one

Starting from the original 10 missing files (all "weighted" objective
variants — station-transit-cost scenarios), a follow-up session ran two more
retry rounds: `retry_extended_timeout.py <combo> 900000` (900s Z3 budget, up
from 420s) recovered 3 of the 10 —
`s2-55_s6-55/equal_allocation/people_equal/3dB_peak.csv`,
`s2-55_s6-55/utilitarian_peak/weighted/result.csv`, and
`s2-65_s6-45/equal_allocation/people_equal/18dB_peak.csv` — each solving
comfortably inside the new budget (40–755s) once given enough room. A
follow-up seeded round (`Z3_RANDOM_SEED` env var, now supported by
`_solve_helpers.py`, forcing `smt.random_seed`/`sat.random_seed`) recovered
one more — `s2-65_s6-55/utilitarian/weighted/result.csv`, solved in 25.2s
with seed 42 after failing at 907.9s unseeded. **5 files remain**, and they
split into two genuinely different situations:

### 4.1 Four files: a real, still-unexplained Z3 tractability wall

```
s2-65_s6-45: utilitarian/weighted/result.csv
s2-55_s6-45: equal_allocation/people_equal/8dB_peak.csv, sufficientarian/weighted/D8.csv, utilitarian/weighted/result.csv
```

All four use their domain's correct, verified config (full N=14 fleet with
the documented multipliers for `utilitarian`/`sufficientarian`; config
cross-checked against each file's own source preamble). Every attempt —
420s, 900s plain, 900s with `Z3_RANDOM_SEED=42`, and (for
`s2-65_s6-45/utilitarian/weighted`) 600s at `T_max=6` instead of 7 — failed
at **within ~1-2% of whatever budget was given** (425s/420s, 907-912s/900s,
609s/600s). Failure time scaling with the timeout, rather than converging
partway through a larger one, means Z3 genuinely isn't finding/proving an
optimum here regardless of clock time, random seed, or a one-step T_max
reduction. A real fix would need code changes to `optimize_objectives`
(e.g. the station-weighted term's `Implies`-constraint construction cost),
which nothing in this folder has attempted.

**If you want to try again**: `retry_extended_timeout.py <combo> [timeout_ms]`
overrides `solver_server_dB.SOLVE_TIMEOUT_MS` for just that process and
calls `run_combo.py`, which skips existing files — always safe to re-run.
Set `Z3_RANDOM_SEED=<n>` in the environment first to also vary the search
seed. Given the evidence above, neither alone is likely to help further.

### 4.2 One file: status genuinely unknown — a debugging bug invalidated the earlier retries, don't reuse those numbers

```
s2-65_s6-55: equal_allocation/people_equal/3dB_avg.csv
```

This file's first two "failures" (at ~10s each, across 6 different random
seeds) were **not evidence of solver difficulty** — they used the wrong
fleet config. This file's documented variant is `N14_mult1` (14 aircraft,
**unit multipliers**, total traffic 14 — confirmed against
`equal_allocation/s2-65_s6-55/people_equal/picks_summary.csv`'s
`3,avg,N14_mult1,6.0,2.8873` row and the historical file's own
`Total Traffic,14` / `T=6` preamble), but the retry scripts written for it
mistakenly passed the full config-default fleet (`aircraftMultipliers`
summing to 56) instead. That's a substantially harder problem, and it
reliably failed in ~10s at phase 1 (pure feasibility, `find_min_T` —
never even reached the weighted phase-2 objective this file is nominally
about). A corrected attempt (unit multipliers, matching the historical
config exactly) was in progress and had not returned a result when retries
were stopped by explicit instruction to stop grinding on this and document
instead. **This file's true difficulty is unknown — do not treat it as
part of the §4.1 "genuine wall" group.** `retry_multiseed.py` in this
folder has the corrected config and is ready to run.

## 5. Known assumptions worth double-checking

- **N7_mult1/N4_mult1 aircraft subset (equal_allocation only)**: the original
  data never recorded which 7 or 4 of the 14 aircraft were kept for these
  fleet-shrink variants. This folder uses an "every other" subsample
  (`subsample_fleet()` in `_solve_helpers.py`) — the same convention used
  successfully for prioritarian's people-mode fleet-shrink earlier this
  session. Combined with the tied-optimal issue above (§3), this means the
  *combination* of "right subset" and "which tie Z3 lands on" is not fully
  verifiable against history for every cell — treat `matchesHistorical,False`
  rows as "a valid answer for this config," not "the same answer as before."
- Every config parameter otherwise comes directly from the pre-existing
  files: `equal_allocation/<combo>/<mode>/picks_summary.csv` (variant + U),
  `sufficientarian`/`prioritarian`'s own `#`-preamble metadata (fully
  self-documenting), and `utilitarian_data_report.md` + each combo's
  `d_min.txt` for the utilitarian domain's fixed D values.

## 6. Reusable scripts in this folder

- `_solve_helpers.py` — shared solve+format logic (imports `solver_server_dB`
  directly, no Flask needed), config parsers, the subsample/fleet helpers.
  Also reads an optional `Z3_RANDOM_SEED` env var and applies it to
  `smt.random_seed`/`sat.random_seed` if set — no effect on normal runs.
- `run_combo.py <combo>` — regenerates all 30 files for one baseline combo;
  safe to re-run any time, skips files that already exist.
- `retry_extended_timeout.py <combo> [timeout_ms]` — same, with a
  configurable (longer) Z3 timeout for this process only.
- `retry_multiseed.py` — targeted, corrected retry for
  `s2-65_s6-55/equal_allocation/people_equal/3dB_avg.csv` specifically
  (§4.2) — tries a few random seeds in quick succession since this file's
  phase-1 search resolves fast either way. **Has the config bug fix
  applied** (unit-multiplier `N14_mult1` fleet, not the config-default
  fleet); safe to run as-is.

## 7. Suggested next step for whoever picks this up

If exact historical reproduction of the 25 "different-tie" equal_allocation
cells matters: `_solve_helpers.py` now supports pinning Z3's search via
`Z3_RANDOM_SEED`, but seeding only changes *which* tie is found — it doesn't
make re-solving converge on the *specific historical* tie, since that
information (which of several equally-valid solutions the original run
picked) was never recorded and can't be recovered. Treat these as "a
numerically valid demonstration of the same target," not a byte-exact match
to the historical dashboard numbers.

For §4's 5 remaining files: don't lump them together. §4.1's four files have
real evidence of a Z3 tractability wall independent of timeout/seed/T_max —
a fix likely needs `optimize_objectives` code changes, not more retries.
§4.2's one file has no such evidence yet — its only "failures" so far used
a wrong config — so it should be retried correctly (`retry_multiseed.py`)
before drawing any conclusion about it.
