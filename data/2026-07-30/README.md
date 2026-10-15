# 2026-07-30 — the two dB-target sweep collections

Two datasets, both committed on 2026-07-30, both on a **16-station (4x4)** grid of
Austin community archetypes. Read the ordering rule below before using either.

## Which one is live

**`dB45_collection/` supersedes `dB_target_sweeps/`.**

`dB45_collection/INTEGRATION_HANDOFF.md` states the rule in its own §0.1: it is "the
only live dataset", and `dB_target_sweeps/` is "the older 55 dB-per-craft
collection; its reports and CSVs come from previous trials with different
parameters, a different aircraft level, and a different station map. They are stale
by construction and nothing in them carries over."

Do not mix numbers between the two folders, and do not average across them. The
station maps differ: per the project notes, `dB45`'s active workbook has station 6 =
Create-Your-Own B and station 8 = Dove Springs, which is the **reverse** of the
55 dB grid.

## `dB45_collection/` — the 45 dB study

The live collection. Aircraft at **45 dB per craft** (`dbPerCraft,45` in every CSV
preamble), 14 solver aircraft carrying per-aircraft multipliers for 56 units of
total traffic.

```
dB45_collection/
├── INTEGRATION_HANDOFF.md   ← read this first; full dataset + dashboard spec
├── data/base_model/         community attributes (Sample Communities.xlsx is canonical)
├── data/full_routes/        per-combo, per-domain, per-mode route CSVs
├── data/summaries/          aggregate tables
├── data/probes/             generation-side probes
├── scripts/                 the generators
├── logs/
├── build/
└── uam-dashboard-standalone-2026-07-20-v2.html
```

Each CSV carries a `#` preamble written by the code that produced that exact file —
domain, combo, mode, `U`, `D`, whether `D` was binding, the variant, `T_max`,
`weightTime`, the objective flags, `maxAvgAddedDb`, `maxPeakAddedDb`, `dbPerCraft`,
`N`, the multipliers, traffic totals and demand fulfilled. **That preamble is the
authoritative description of its own file.**

The handoff reports 156 of 168 intended files present, with 12 gaps and their
causes documented.

## `dB_target_sweeps/` — the earlier 55 dB collection

Kept for provenance. Five fairness domains (`equal_allocation`, `sufficientarian`,
`utilitarian` plus `utilitarian_peak`, `prioritarian`, `proportional`) across 4
baseline combos. 14 aircraft, every multiplier 1.

`CONTEXT.md` is the orientation file and is written to be self-verifying. It also
sets a trust order that still applies inside that folder:

1. the solver — defines what every number means
2. the `#` preamble inside each CSV — per-file accurate
3. `scripts/*.py` — which config produced which file
4. `reports/*.md` — **narrative, partly unverified, and known to contain at least
   three errors**, listed in its §8.2. Useful for "why", not authoritative for
   "what".

Begun 2026-07-19 and extended 2026-07-30; the 07-30 work reorganised it into
`data/scripts/reports/dashboards` and added the route-enriched dataset and the
proportional domain.

## Solver versions

| data | solver |
|---|---|
| `dB_target_sweeps` initial generation (2026-07-19) | `366a85d` — the first solver state in this repo's history |
| `dB_target_sweeps` extension + `dB45_collection` (2026-07-30) | `9e0be66` — max/min `U` encoding |

`9e0be66` is the commit that replaced the pairwise `U` table with the max/min
encoding (~110k assertions down to ~2,089). It is folded into this repository's
second solver commit, which also carries four later 2026-08-23 changes that
**postdate this data** — so the exact file that produced `dB45_collection` is
`9e0be66`'s version, not that whole commit.

`dB45_collection` rests on one unmodified solver by design: its handoff §0.3 records
that `solver_server_dB.py` was read-only for the entire generation phase, with
timeout changes made at runtime only. That is what makes the collection internally
comparable.

## Relationship to the current dashboard

Neither dataset matches the dashboard in `5x5_realtime_solver/`. Both are
16-station; the current activity is 25-station with 45 dB aircraft and three
vertiports. These are the previous generation of the project, retained as data
rather than as inputs to the current tool.
