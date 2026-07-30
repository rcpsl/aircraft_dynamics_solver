# Sufficientarian D-Sweep — Data Report

## 1. What this data is

A "sufficientarian" fairness search over the UAM noise-fairness model: instead of
optimizing an average or comparing stations against each other, `D` is used
directly as a **hard per-station, per-timestep cap** on how much aircraft noise
is allowed to raise a station above its own ambient baseline. `U` (the
station-to-station disparity cap) is set to a large non-binding value (999) so
it never constrains the search — this run is only about "does everyone stay
under the ceiling," not "are stations equal to each other."

The question asked: for each of 4 station-baseline scenarios, what aircraft
loading is needed to keep every station under D=8dB, D=18dB, and — after D=3
turned out to be mathematically impossible — the true smallest D achievable?

## 2. How the data was collected

**Solver**: `solver_server_dB.py`'s existing `/solve` HTTP API (Z3-based
route/timing solver), unmodified. All results come from real solver output —
`countMatrix` / `noiseMatrix` per station per timestep — not hand computation.

**Base scenario**: `uam-config_finalized.json` — N=14 aircraft, M=16 stations,
fixed adjacency graph, fixed start/end positions (aircraft only travel between
station 1 and station 16, in both directions), `aircraftDB` (per-aircraft
noise level) = 55dB.

**Fixed across every run**:
| Parameter | Value | Meaning |
|---|---|---|
| `hardT` | `false` | soft-T mode: arrival time is a soft objective, not a hard deadline |
| `T_max` | 7 | upper bound on timesteps the soft-T optimizer may use |
| `weightTime` | 0.1 | light penalty for late arrival |
| `optimizeUtilitarian` | `true` | transit-time objective is active |
| `weightUtilitarian` | 1.0 | no extra emphasis ("no weight") |
| `optimizePrioritarian`, `optimizeProportional`, `proportionalAllocation` | `false` | not used in this study |
| `utilNoiseMode` | `false` | utilitarian objective minimizes transit *time*, not summed dB |
| `U` | 999 | disparity cap effectively disabled ("don't care") |

**Swept**:
- **D** (hard noise-increase cap): 8, 18, and an adaptively-searched minimum near 3 (see §5).
- **4 baseline combos** — override only station 2's and station 6's ambient baseline (all other stations keep `uam-config_finalized.json`'s defaults):

  | combo folder | station 2 baseline | station 6 baseline |
  |---|---|---|
  | `s2-65_s6-55` | 65 dB (default) | 55 dB (default) |
  | `s2-65_s6-45` | 65 dB (default) | 45 dB |
  | `s2-55_s6-55` | 55 dB | 55 dB (default) |
  | `s2-55_s6-45` | 55 dB | 45 dB |

- **2 station-weighting modes**:
  - `unweighted` — no `stationTransitWeights` sent (uniform weight 1 in the transit-cost objective).
  - `weighted` — `stationTransitWeights` set to the project's people_equal weights (1-indexed): `1:10 2:5 3:10 4:5 5:10 6:10 7:5 8:5 9:5 10:10 11:5 12:5 13:5 14:5 15:1 16:5`.

**Fleet-shrink ladder**: at very tight D values, the full 14-aircraft fleet
can't fit under the cap, so each task tried progressively smaller/lighter
loadings and stopped at the first one that solved (SAT):

| variant | N (aircraft) | aircraftMultipliers | meaning |
|---|---|---|---|
| `V1_N14_origMult` | 14 | `[2,5,5,5,5,5,5,5,5,2,5,3,2,2]` (config default, sums to 56 "virtual" aircraft) | full fleet, original per-aircraft weighting |
| `V2_N14_mult1` | 14 | all 1s | full fleet, no per-aircraft weighting |
| `V3_N7_mult1` | 7 | all 1s | half the fleet, evenly subsampled across both travel directions |
| `V4_N4_mult1` | 4 | all 1s | quarter fleet, evenly subsampled |

Each `/solve` call gave Z3 a 240-second internal solving budget (hardcoded in
`solver_server_dB.py`, not something this study changed). 12 solver instances
ran in parallel (one per port) to cover the 4 combos × 3 D values × 2 weight
modes = 24 tasks, plus a follow-up 8-task search for the true D≈3 minimum.

**Infrastructure note**: an earlier attempt at this sweep ran on the
project's conventional ports (5061–5066, 5071–5076) and produced
self-contradictory results, traced to *another, independent Claude Code
session on the same machine* also using those same ports — Windows let both
sessions' processes bind the same port and routed requests unpredictably
between them. All data in this report comes from a clean rerun on a private,
uncontested port range after that was fixed. Mentioned here only so the
numbers can be trusted; it has no bearing on how to read the CSVs.

## 3. Directory / file guide

```
dB_target_sweeps/sufficientarian/
  <combo>/
    unweighted/
      D8.csv           D18.csv           Dmin_3.02.csv
    weighted/
      D8.csv           D18.csv           Dmin_3.02.csv
  picks_summary.csv     — which fleet variant satisfied D=8/D=18 for each combo x weight mode
  unsat_record.csv       — historical record of the original D=3 attempts (all timed out; superseded, see §5)
  min_d_summary.csv      — which D/variant satisfied the minimum-D search (all landed on D=3.02)
  REPORT.md               — this file
```

## 4. What each file/column means

### Per-result CSV (`D8.csv`, `D18.csv`, `Dmin_3.02.csv`)

Metadata preamble (`#`-prefixed lines):

| field | meaning |
|---|---|
| `combo` | which station-baseline scenario (see table in §2) |
| `weighted` | whether the station-weighted transit objective was used |
| `D` | the hard per-station dB-increase cap that was enforced |
| `U` | the disparity cap used (always 999 = non-binding) |
| `variant` | which fleet-shrink step (§2 table) produced this SAT result |
| `N` | number of aircraft actually modeled |
| `aircraftMultipliers` | per-aircraft virtual-fleet-size weight used |
| `startPositions` / `endPositions` | 1-indexed station IDs for each modeled aircraft (a subset of the full 14 if N<14) |
| `T_used` | number of timesteps in the solved schedule (soft-T mode picks this, bounded by `T_max=7`) |

Data table — one row per station ("Zone", 1–16, matching `stationBaselines`/adjacency indices 1:1):

| column | meaning |
|---|---|
| `Zone` | station ID |
| `Avg Added dB` | mean, over all `T_used` timesteps, of the aircraft-caused dB increase above that station's ambient baseline |
| `Avg Total dB` | mean absolute noise level (baseline + added dB) |
| `Peak Added dB` | single largest aircraft-caused increase at that station across all timesteps — **this is the value checked against `D`; by construction it never exceeds D** |
| `Peak Total dB` | baseline + peak added dB |
| `Avg Aircraft` | mean **weighted** (multiplier-scaled) aircraft count present/active at that station |
| `Peak Aircraft` | largest weighted aircraft count present at that station at any single timestep |

**Aircraft counts are weighted, not physical counts.** E.g. a `Peak Aircraft`
of 29 with only N=14 real aircraft modeled means the multiplier-scaled virtual
count reached 29 — some aircraft "count for more" per the `aircraftMultipliers`
array (this only happens in the `V1_N14_origMult` variant; all others use
multiplier=1, so weighted count = physical count there).

### `picks_summary.csv`

Columns: `combo, weighted, D, variant, N, out_path`. One row per (combo ×
weight × D∈{8,18}) task that reached SAT, pointing at the CSV it produced.
Only successful tasks appear here.

### `unsat_record.csv`

Columns: `combo, weighted, D, status, last_reason, last_detail`. Every
combo × weight combination at **D=3** timed out (`status=unsat,
last_reason=timed out`) across all four fleet variants — Z3's 240s budget was
exhausted every time, for every combo. As shown in §5, this is because D=3
is actually infeasible, not merely hard to search. **`Dmin_3.02.csv` is the
useful answer for "smallest achievable D," not this file** — this file is
kept only as a record of the original (unsuccessful) attempt.

### `min_d_summary.csv`

Columns: `combo, weighted, min_D, variant, N, out_path`. Result of an
adaptive follow-up search over candidate D values `[3.02, 3.5, 4, 5, 6, 7,
8]` (smallest tried first, per combo × weight, stopping at first SAT). All
8 rows converged on `min_D = 3.02`.

## 5. Important findings

### D=3 is mathematically impossible — not just hard to solve

All 14 aircraft travel only between station 1 and station 16. The only
stations quiet enough that even **one** aircraft stays under a 3dB increase
are the 65dB-baseline stations: `{1, 2, 12, 15, 16}` for the `s2-65_*`
combos, or `{1, 12, 15, 16}` for the `s2-55_*` combos (station 2 itself
drops to 55dB there). In the adjacency graph, that "safe" station set is
**disconnected** — it splits into `{1,2}` and `{12,15,16}` with no direct
edge between them (verified by BFS over the adjacency matrix) — so *every*
route between station 1 and station 16 must pass through at least one
55dB-baseline "bridge" station along the way.

Physically, a single aircraft (55dB itself) at a 55dB-baseline station
produces exactly `10·log₁₀(2) ≈ 3.0103 dB` of increase (two equal-power
sources double the power, which is +3dB) — already above a 3dB cap. This
holds regardless of aircraft count, multipliers, or fleet size: even one
lone aircraft making the trip cannot avoid it. That's why the original D=3
attempts timed out rather than quickly reporting infeasible — the solver's
fast structural pre-check only reasons about worst-case per-station
capacity, not full route connectivity, so Z3 was left to search a space
that a graph-reachability argument shows has no solution at all.

### The true floor is D=3.02, and it's achievable everywhere

Once D is nudged just above the 3.0103dB physical floor, all 8 (combo ×
weight) combinations do solve — right at the floor:

- **Unweighted**: solvable with a 7-aircraft fleet (`V3_N7_mult1`).
- **Weighted**: needed a smaller, 4-aircraft fleet (`V4_N4_mult1`) to solve
  within Z3's time budget — see next finding.

### Station weighting doesn't change feasibility, but it does change solve difficulty

The `D`/`U` hard constraints are completely independent of
`stationTransitWeights` — station weights only affect the *objective*
(which routes are preferred among the feasible ones), not which
configurations are feasible at all. So the fact that `weighted` mode needed
a smaller fleet (N=4 vs N=7) to solve D≈3.02 within the 240s budget is a
**solver-performance** effect (the weighted objective adds phase-2
optimization overhead), not evidence that weighting makes the problem
actually harder in principle.

### Stations 6 and 11 are the consistent hot spots

Across every scenario, stations 6 and 11 show the highest `Peak Added dB`
and `Peak Aircraft` values. These are the graph's hub/bridge stations
connecting the two halves of the network, and at low-baseline settings
they're also where the 45–55dB "quiet" stations concentrate — so they
absorb the most through-traffic and the most noise.

### D=8 / D=18 are comfortable; only D≈3 required shrinking the fleet

For every combo and both weight modes, D=8 and D=18 solved with the **full
14-aircraft fleet** (`V1_N14_origMult` or `V2_N14_mult1` — no aircraft
removed). Only the extremely tight D≈3 case required reducing to 4–7
aircraft, confirming that 8dB and 18dB are well within this network's
practical capacity, while ~3dB is right at its physical limit.
