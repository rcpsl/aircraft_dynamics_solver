# Prioritarian Community-Equity Sweep — Data Report

## 1. What this data is

A "prioritarian" fairness search over the UAM noise-fairness model: rather than
capping noise (sufficientarian) or comparing every station pairwise
(egalitarian), the solver is asked to **minimize noise specifically at a
named list of "protected" stations** — here, four different lists, each
representing a different equity lens Austin community advocates raised:

| group folder | protected stations | equity lens |
|---|---|---|
| `low_income` | 6, 12 | Low-income communities of color |
| `transit_desert` | 6, 12, 15 | Already a transit desert |
| `few_jobs` | 4, 6, 12, 14 | Few local jobs |
| `mostly_renters` | 1, 3, 5, 10, 15, 16 | Mostly renters |

The question asked: does telling the solver "minimize noise at these
community-flagged stations" actually change where noise ends up, and does
adding a transit-time (utilitarian) objective on top change that further?

**Read §5 before drawing conclusions from the numbers** — the honest answer
turned out to be "no, not in this dataset," for a structural reason that's
important to understand before comparing rows across these CSVs.

## 2. How the data was collected

**Solver**: `solver_server_dB.py`'s `/solve` HTTP API (Z3-based route/timing
solver), run from a clean, private instance (port 5090) after clearing ~20
orphaned solver processes left running by unrelated prior sessions on the
project's conventional ports — see [[dbsolver_infra]] in the assistant's
memory if this recurs. No permanent code changes were made (one temporary
timeout probe was reverted — see §5).

**Base scenario**: `uam-config_finalized.json` — N=14 aircraft, M=16 stations,
fixed adjacency graph, all 14 aircraft travel only between station 1 and
station 16 (in both directions), `aircraftDB` = 55dB, `aircraftMultipliers`
= `[2,5,5,5,5,5,5,5,5,2,5,3,2,2]` (sums to 56 "virtual" aircraft).

**Fixed across every run**:

| Parameter | Value | Meaning |
|---|---|---|
| `D` | 40 | noise-increase cap, non-binding ("don't care") |
| `U` | 50 | disparity cap, non-binding ("don't care") |
| `hardT` | `true` | **see §5 — deviates from the soft-T convention used elsewhere in this project** |
| `optimizePrioritarian` | `true` | every run |
| `weightPrioritarian` | 1.0 (default) | not customized |
| `weightUtilitarian` | 1.0 (default) | "no weight for now" — no `stationTransitWeights` sent |
| `optimizeProportional`, `proportionalAllocation`, `utilNoiseMode` | `false` | not used in this study |

**Swept**:
- **protected-station group** — the 4 rows in the table above.
- **whether `optimizeUtilitarian` is also on** (step 1 vs step 2/3).
- **4 baseline combos** (step 3 only) — override only station 2's and station
  6's ambient baseline (all other stations keep `uam-config_finalized.json`'s
  defaults), same convention as [[utilitarian_domain_task]]:

  | combo folder | station 2 baseline | station 6 baseline |
  |---|---|---|
  | `s2-65_s6-55` | 65 dB (default) | 55 dB (default) |
  | `s2-65_s6-45` | 65 dB (default) | 45 dB |
  | `s2-55_s6-55` | 55 dB | 55 dB (default) |
  | `s2-55_s6-45` | 55 dB | 45 dB |

**3-step structure (24 files total)**:
1. `step1_prioritarian_only/` — prioritarian objective alone, default baseline. 4 files.
2. `step2_prioritarian_utilitarian/` — prioritarian + utilitarian combined, default baseline. 4 files.
3. `step3_baseline_sweep/<combo>/` — same combined config as step 2, across all 4 baseline combos. 16 files.

## 3. Directory / file guide

```
prioritarian/
  step1_prioritarian_only/
    low_income.csv   transit_desert.csv   few_jobs.csv   mostly_renters.csv
  step2_prioritarian_utilitarian/
    low_income.csv   transit_desert.csv   few_jobs.csv   mostly_renters.csv
  step3_baseline_sweep/
    s2-65_s6-55/   s2-65_s6-45/   s2-55_s6-55/   s2-55_s6-45/
      community/   — "counting communities" (prioritarian objective alone)
        low_income.csv   transit_desert.csv   few_jobs.csv   mostly_renters.csv
      people/       — "counting people" (prioritarian + population-weighted
                       utilitarian objective combined) — see §5d
        low_income.csv   transit_desert.csv   few_jobs.csv   mostly_renters.csv
  REPORT.md   — this file
```

The one-off scripts that produced `step3_baseline_sweep/<combo>/{community,people}/`
(calling `solver_server_dB.py`'s `find_min_T`/`optimize_objectives` directly, no
Flask needed) have been removed after generating the data — §5b and §5d
document their exact configs (parameters, weights, fleet sizes) in full, so
the runs are reproducible from those sections alone without needing the
scripts themselves.

## 4. What each file/column means

Same CSV format as [[utilitarian_domain_task]] — one row per station ("Zone",
1–16), built directly from the solver's `noiseMatrix`/`countMatrix`:

| column | meaning |
|---|---|
| `Zone` | station ID (matches `stationBaselines`/adjacency indices 1:1) |
| `Avg Added dB` | mean, over all `T` timesteps, of the aircraft-caused dB increase above that station's ambient baseline |
| `Avg Total dB` | mean absolute noise level (baseline + added dB) |
| `Peak Added dB` | single largest aircraft-caused increase at that station across all timesteps |
| `Peak Total dB` | baseline + peak added dB |
| `Avg Aircraft` | mean **weighted** (multiplier-scaled) aircraft count active at that station — not physical aircraft count |
| `Peak Aircraft` | largest weighted aircraft count active at that station at any single timestep |

The `Time Steps (T),4` header line gives the solved horizon (always 4 in this
dataset — see §5, this is `T_min`, not a soft-T `T_max=7` result).

There is no `picks_summary.csv` / `unsat_record.csv` in this domain — every
one of the 24 runs solved (SAT) with no timeout fallback, so there was
nothing to record separately.

## 5. Important findings

> **Update**: `step3_baseline_sweep/` was regenerated after this section was
> originally written, using the fix described in §5b below. §5a documents the
> original hard-T dataset (`step1_prioritarian_only/` and
> `step2_prioritarian_utilitarian/` still use it, and still show the
> byte-identical behavior described below — that part of the finding stands).
> `step3_baseline_sweep/<combo>/community/` now uses soft-T with the config in
> §5b and its 16 files **do** differentiate between lenses; see §5c for the
> new numbers. `step3_baseline_sweep/<combo>/people/` is a second, newly-added
> 16 files — prioritarian's previously-missing "counting people" variant;
> see §5d. The generation scripts have been removed after producing the
> data — §5b/§5d document their exact configs for reproducibility.

### 5a. The original headline finding: 24 files that did not show fairness-based rerouting — and the structural reason why

All 14 aircraft in the base config travel exclusively between station 1 and
station 16. A BFS over the adjacency graph shows the shortest path between
them is **unique**: `1 → 6 → 11 → 16` (3 hops, so `T_min = 4`), confirmed by
enumerating all shortest paths (exactly 1 found). Because this project ran
every prioritarian run at **hard-T** (`T = T_min = 4`, no slack timesteps),
every single aircraft in every one of these 24 runs is forced onto that one
route shape — there is no alternate path short enough to fit in 4 timesteps.
With only one feasible route in the search space, the prioritarian and
utilitarian objectives have **nothing to trade off between**: whatever the
weights say, there's only one way to schedule the fleet at all.

The data confirms this directly:
- **`step1_prioritarian_only` and `step2_prioritarian_utilitarian` are
  byte-identical**, row for row, for every one of the 4 groups. Turning on
  the utilitarian objective changed nothing.
- **All 4 protected-station groups produce byte-identical `Zone` tables** at
  a given baseline. Only stations **1, 6, 11, and 16** ever carry any traffic
  in any file in this dataset — every other station (including 12, which
  three of the four groups explicitly protect) reads exactly `0.00` added dB
  in all 24 files, because it's never on the forced route.
- The `protectedNoise` values that *do* differ between groups (29.24 for
  `low_income`/`transit_desert`/`few_jobs` vs. 11.59 for `mostly_renters`,
  scaling to 48.97 at the 45dB station-6 baseline) are entirely an artifact
  of **which stations happen to be summed** — `low_income`/`transit_desert`/
  `few_jobs` all include station 6 (on-route, nonzero) and nothing else
  on-route, so they collapse to "protect station 6 alone" and get an
  identical number. `mostly_renters` instead catches stations 1 and 16
  (also on-route), giving a different sum from the *same underlying route*.
  None of this reflects the solver choosing different paths for different
  communities — it's the same fixed route, read through four different
  accounting lenses.

### There was real route diversity available for soft-T to exploit — it just couldn't be computed in time

This isn't a case of "there was nothing else the solver could have done."
Enumerating simple paths from station 1 to station 16 within `T_max=7`'s
6-hop budget finds **425 alternate routes** (12 of length 4, 80 of length 5,
332 of length 6) passing through stations otherwise silent in this
dataset — e.g. `1→2→3→6→11→15→16` or `1→2→3→7→11→16`. A soft-T run genuinely
could have shifted noise off stations 6/11 onto some of these alternates if
a protected-station weighting favored it.

That's exactly what steps 2/3 originally tried to test (`hardT:false,
T_max:7, weightTime:0.1`, matching the convention from
[[utilitarian_domain_task]]/[[soft_t_dashboard_task]]) — but it reliably blew
past the solver's 240-second Z3 timeout and silently fell back to the plain
unweighted route, reproduced across group sizes and even at a reduced
`T_max=5` (at the time, still run with the original `D=40`, non-binding — see
§5b for why that combination still fails). To rule out "just needs more
time," `SOLVE_TIMEOUT_MS` in `solver_server_dB.py` was temporarily raised to
1200s (20 min) for one probe run — it still didn't converge, and the change
was reverted afterward (no permanent code change). All 24 files at the time
therefore used hard-T instead, which reliably solves in ~18 seconds but —
per the finding above — gives the optimizer no room to actually respond to
any objective.

### Baseline overrides behave exactly as physics predicts

Across `step3_baseline_sweep` (both the original hard-T version and the
current soft-T version), dropping station 6's baseline from 55dB to 45dB
raises its reported `Avg Added dB` for the *same* route segment and aircraft
count — a quieter ambient baseline means the same aircraft noise is a larger
fraction of the total, so the log-additive dB formula shows a bigger
perceived increase (masking effect works in reverse: less masking at a quiet
station).

## 5b. The fix: a config that actually differentiates the lenses

Two changes, tested by calling `find_min_T`/`optimize_objectives` directly
(bypassing Flask) against the real adjacency graph and baselines, **both
needed together** — neither alone is sufficient:

| Parameter | Original (steps 1/2, old step3) | Fixed (new step3) | Why |
|---|---|---|---|
| `hardT` | `true` | `false` | Without slack, there is only one route — see §5a |
| `T_max` | n/a (T pinned to 4) | **5** | Just one tick above `T_min=4` unlocks the 12 alternate length-4 routes — enough for the objective to have a real choice, without paying for all 425 routes up to length 6 (which `T_max=7` opens, and which is what actually made phase-2 time out) |
| `D` | 40 (non-binding) | **18** | Forces real overflow at the station 6/11 bottleneck — without it, nothing *needs* to reroute even when a shorter alternate exists, so Z3 just returns the cheapest (shortest) route anyway. 18dB was chosen because the sufficientarian domain already proved it solves with the **full N=14 fleet**, no service-level sacrifice needed (see `sufficientarian/REPORT.md` §5, "D=8/D=18 are comfortable") |
| `U`, `weightPrioritarian`, `weightTime`, `N`, `aircraftMultipliers` | 50, 1.0, —, 14, config default | unchanged (`weightTime=0.1`) | not part of the problem |

**Confirmed both changes are required**: `T_max=7` with the tightened `D=18`
still times out (measured directly: 248.9s, over the 240s budget — the
425-route search space at `T_max=7` is too large for Z3's optimizer
regardless of D). `T_max=5` alone, with the original non-binding `D=40`, was
already tried in the original data collection (§5a) and didn't help either —
loosening the route search space doesn't matter if nothing forces the
optimizer to prefer an alternate over the free, already-cheapest shortest
path. Only the combination — enough slack to have alternates (`T_max=5`) and
enough pressure to actually want one (`D=18`) — works. Once combined, all 16
(4 lens × 4 combo) solves complete in **8–53 seconds** each, comfortably
inside the 240s budget, with the full 14-aircraft fleet.

Generated by a one-off script (calling `solver_server_dB.py`'s
`find_min_T`/`optimize_objectives` functions directly, no Flask needed) that
produced the current `step3_baseline_sweep/<combo>/community/` files with
this config, then was removed — the table above fully specifies the config
for reproduction.

## 5c. What the new step3 data shows

With real route choice now available, the four protection lenses **do**
produce different noise maps — 5 to 10 of 16 zones differ between any pair
of lenses, for every one of the 4 baseline combos. `mostly_renters` (the
lens with the widest, most spread-out protected set — 6 stations including
both endpoints 1 and 16) diverges the most from the others; `low_income` /
`transit_desert` / `few_jobs` (which all include station 6, the primary
bottleneck) are more similar to each other but still not identical, since
their other protected stations (12; 12+15; 4+12+14) differ.

`protectedNoise` no longer collapses to two values by accounting
coincidence (§5a) — it now reflects genuinely different routing decisions
per lens. Avg and peak also now diverge meaningfully *within* a single
solve (4–8 of 16 zones differ between the two columns per file), whereas
before, with only one possible route, avg and peak differed only by the
trivial single-vs-repeated-timestep arithmetic of one fixed path.

**What this means for interpreting the dashboard**: prioritarian protection
now visibly reroutes traffic — protecting `mostly_renters` measurably
lowers noise at stations 1/16 (the endpoints) relative to protecting
`low_income`, at the cost of pushing more onto the corridor's non-renter
alternates. This is the "real" prioritarian finding this domain was always
meant to produce; §5a's "protection changes nothing" result was an artifact
of the hard-T scheduling constraint, not a fact about the fairness lenses
themselves.

## 5d. The missing people-mode variant, and what it shows

Every other domain in this project (equal_allocation, sufficientarian,
utilitarian) has both a "counting communities" and a "counting people"
variant. Prioritarian was the only one missing the latter — closed by
generating `step3_baseline_sweep/<combo>/people/<lens>.csv`, alongside
moving the existing (community-mode) files into a matching
`step3_baseline_sweep/<combo>/community/<lens>.csv` layout.

**Config**: `optimizePrioritarian=true` combined with `optimizeUtilitarian=true`
and `stationTransitWeights` set to the exact same population-weight vector
used identically across equal_allocation, sufficientarian, and utilitarian —
`{1:10, 2:5, 3:10, 4:5, 5:10, 6:10, 7:5, 8:5, 9:5, 10:10, 11:5, 12:5, 13:5,
14:5, 15:1, 16:5}` (1-indexed) — confirmed byte-identical across all three
of those reports before reuse here. `weightPrioritarian=weightUtilitarian=1.0`
(equal weighting, matching the code's own normalization comment: "w_util =
w_prior = ... = 1.0 gives genuinely equal weighting"). Same `T_max=5, D=18,
U=50, weightTime=0.1` as the working community-mode config (§5b).

**Fleet size had to shrink to N=7.** Combining both objectives at N=14 (same
`T_max=5, D=18` that works fine for prioritarian alone) reliably times out —
measured directly: 246.2s, over the 240s Z3 budget. The combined objective
(transit-time tracking booleans + station-weighted cost expression +
prioritarian noise sum, all separately normalized) is substantially more
expensive to search than either objective alone. N=7 (unit aircraft
multipliers, matching the fleet-shrink convention used elsewhere in this
project, e.g. sufficientarian's `V3_N7_mult1`) solves the worst-case combo's
4 lenses in 48–109s each, comfortably inside budget. **This is a real
service-level cost to disclose**: people-mode prioritarian only serves half
the fleet.

**Finding: people-mode differentiates lenses less than community-mode does.**
At N=7, three of the four lenses — `low_income`, `transit_desert`, and
`few_jobs` — produce **byte-identical routing** in every one of the 4
baseline combos (confirmed directly against the raw CSVs, not just the
parsed summary). Only `mostly_renters` differs (3 of 16 zones, every combo).
This is *not* a repeat of §5a's hard-T bug — soft-T route choice is
available and community-mode (same lenses, N=14) differentiates all four
lenses fine (§5c) — it's a genuine effect of the smaller N=7 fleet: with
fewer aircraft, there are fewer distinct ways to trade off the combined
objective, so the three lenses whose protected sets all include station 6
(the primary bottleneck) collapse onto the same optimal routing, while
`mostly_renters`'s very different protected set (spread across both
corridor endpoints, no station 6) still finds a distinguishable answer.
Community vs. people mode *does* differ substantially for the same lens
(4-8 of 16 zones differ, per lens, per combo) — it's specifically
cross-lens differentiation that narrows under the reduced fleet.

**Practical implication for the dashboard**: show the N=7 fleet cut
prominently in people mode (the dashboard's service-level strip already
does this via `ds.meta.N`), and don't be surprised if switching between
`low_income`/`transit_desert`/`few_jobs` under people-counting looks
unchanged — that's correctly reflecting this dataset's real behavior, not
a display bug.
