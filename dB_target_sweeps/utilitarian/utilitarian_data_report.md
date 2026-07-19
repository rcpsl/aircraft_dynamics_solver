# Utilitarian & Peak-Noise Data Report

Covers `utilitarian/` and `utilitarian_peak/`. Both use the same base scenario
(`uam-config_finalized.json`, N=14 aircraft, M=16 stations) and the same
`solver_server_dB.py` Z3 solver, called through its HTTP API only — the
solver itself was never modified.

## 1. Base scenario

- **N=14 aircraft, M=16 stations.** All 14 aircraft travel between station 1
  and station 16 only — 8 aircraft go 1→16 (indices 0-3, 10-13), 6 go 16→1
  (indices 4-9). No other station pair is used as an origin/destination
  anywhere in this dataset.
- **Aircraft multipliers** (how many "virtual" aircraft each of the 14
  represents): `[2,5,5,5,5,5,5,5,5,2,5,3,2,2]`, taken unchanged from the base
  config.
- **`dbPerCraft` = 55** (per-aircraft noise level used in the dB combination
  formula).
- **Adjacency graph**: station 1 and 16 are connected only through a
  three-hop backbone, 1↔6↔11↔16. This is the *only* shortest path (length 3)
  between them — confirmed by exhaustive path enumeration, there is no other
  path of the same length. The next-shortest alternates are length 4, and
  route through a *different* set of stations depending on which side is
  taken, e.g. `1-2-6-11-16`, `1-2-7-11-16`, `1-2-7-12-16`, `1-5-6-11-16`,
  `1-5-10-11-16`, `1-5-10-15-16`, `1-6-7-11-16`, `1-6-7-12-16`,
  `1-6-10-11-16`, `1-6-10-15-16`, `1-6-11-12-16`, `1-6-11-15-16`. This matters
  a lot for interpreting the results (see Finding 1 below).
- **4 baseline combos**, overriding `stationBaselines` only at station 2
  (index 1) and station 6 (index 5); all other stations keep their config
  defaults:

  | combo folder | station 2 baseline | station 6 baseline |
  |---|---|---|
  | `s2-65_s6-55` | 65 dB (default) | 55 dB (default) |
  | `s2-65_s6-45` | 65 dB | 45 dB |
  | `s2-55_s6-55` | 55 dB | 55 dB |
  | `s2-55_s6-45` | 55 dB | 45 dB |

- **Objective**: `optimizeUtilitarian=true` in both domains, `weightUtilitarian`
  left at its default (1.0) throughout — never customized. Two weight
  variants per combo:
  - `no_weight.csv` — no `stationTransitWeights` sent (every station costs
    the same to pass through).
  - `weighted.csv` — `stationTransitWeights` set to (1-indexed):
    `1:10, 2:5, 3:10, 4:5, 5:10, 6:10, 7:5, 8:5, 9:5, 10:10, 11:5, 12:5,
    13:5, 14:5, 15:1, 16:5`. Higher number = more expensive for the
    optimizer to route traffic through that station.
- **Soft-T mode** in both domains: `hardT=false`, `T_max=7`, `weightTime=0.1`.
  `optimizePrioritarian`, `optimizeProportional`, `proportionalAllocation`,
  `utilNoiseMode` are always `false`.
- **U (global dB-disparity cap) = 50** in both domains — high enough to never
  bind (the old dB-target-sweep work found disparity effects plateau by
  U≈16, so 50 is comfortably "don't care").

## 2. What each domain optimizes, and how D is used differently

**D** is the solver's literal hard cap: *"max dB increase (from aircraft) at
any station, at any timestep."* It is enforced as a hard constraint, not a
soft preference — no station's added noise can ever exceed D.

- **`utilitarian/`** — total/average-noise domain. **D=12**, fixed the same
  for every combo and every weight variant. D=12 was *not* chosen to
  represent a "peak noise target" — it was chosen deliberately to create hub
  congestion (see Finding 1). The actual objective being minimized is total
  weighted transit cost, not noise directly.
- **`utilitarian_peak/`** — peak-noise domain. Here D itself *is* the
  quantity being minimized. For each combo, the smallest feasible D was
  found by binary search (see Finding 3 for why the D actually used in the
  final CSVs ends up higher than that floor).

## 3. How the data was collected

1. `uam-config_finalized.json` is loaded once per run; only `stationBaselines`
   (combo override) and `D` change between calls in a given domain.
2. Each data point is one `POST /solve` call to a `solver_server_dB.py`
   instance (Flask dev server, one process per port, imported unmodified).
   The solver runs two phases internally:
   - **Phase 1** (`find_min_T`): pure feasibility search — is there any
     assignment of aircraft to stations/timesteps satisfying D, U, the
     adjacency graph, and start/end pins? Finds the minimum T for which a
     solution exists. This phase does *not* look at the objective/weights at
     all.
   - **Phase 2** (`optimize_objectives`): a Z3 `Optimize()` pass, fixing T to
     the soft-T value (`T_max=7` here), that actually picks the
     lowest-weighted-cost solution among all feasible ones. This is the
     phase that `stationTransitWeights` affects.
3. The response's `noiseMatrix` (added dB per station per timestep) and
   `countMatrix` (aircraft count per station per timestep) are turned into
   the per-station summary CSV using the exact same formula as the
   dashboard's own "Save Results (CSV)" export
   (`frontend/src/utils.js: buildZoneSummaryCSV`), so these files match what
   the UI would show for the same solve.
4. `utilitarian_peak/` additionally ran a **binary search on D** per combo
   (phase-1-only probes, `optimizeUtilitarian=false`, for speed) to find the
   smallest D at which the routing problem is feasible at all, before the
   final phase-2 solves.

### CSV columns

| Column | Meaning |
|---|---|
| `Zone` | Station number (1-16), one row per station |
| `Avg Added dB` | Time-averaged noise increase at this station, above its baseline |
| `Avg Total dB` | `Avg Added dB` + station baseline |
| `Peak Added dB` | The single largest instantaneous noise increase at this station across the whole solve |
| `Peak Total dB` | `Peak Added dB` + station baseline |
| `Avg Aircraft` | Time-averaged aircraft count present at the station |
| `Peak Aircraft` | Largest instantaneous aircraft count at the station |

`d_min.txt` (only in `utilitarian_peak/`) records:
- `D_feasibility_min` — the true hard floor found by binary search (any
  solution exists at all).
- `D_used_for_final_csvs` — the D value actually used to generate the CSVs
  in that folder (see Finding 3 for why these two numbers differ).

## 4. Key findings

**1. At D=40 (the original "don't care" value), the station weight is a
complete no-op.** Every one of the 14 aircraft has *exactly one* possible
shortest route (confirmed by exhaustive path counting — `num_shortest_paths
= 1` for all 14). Combined with T_max=7 being exactly equal to the minimum
feasible T (zero timing slack), there is no decision left for any objective
to bias — Z3 returns the one feasible schedule regardless of weights. This
is why D was lowered to 12 for `utilitarian/`: it's tight enough to
congest the single-hub route (6, 11) and force some traffic onto the
longer alternates (2, 5, 7, 9, 10, 12, 15), which gives the weighted
objective something real to trade off.

**2. Once there's real route choice, the weighted objective visibly avoids
the expensive hub.** E.g. combo `s2-65_s6-55`: no_weight puts 7.29 avg
aircraft through both Zone 6 and Zone 11 and nothing through Zone 7/2/12;
weighted drops Zone 6 to 4.71 avg aircraft and Zone 11 to 5.14, moving the
difference onto Zone 2/7/12 (weight 5, versus Zone 6's weight 10). This
pattern repeats across all 4 combos.

**3. In `utilitarian_peak/`, the reported "minimum peak noise" is *not* the
true theoretical minimum — it's the tightest D at which Z3's phase-2
optimizer could reliably converge within its 240s budget.** The binary
search found true feasibility floors of D=8.0 (`s2-65_s6-55`,
`s2-55_s6-55`) and D=10.5 (`s2-65_s6-45`, `s2-55_s6-45`) — meaning *some*
schedule exists at those tighter caps. But at those exact boundary values
(and for a good distance above them), phase-2 optimization consistently
timed out and fell back to an arbitrary unoptimized route rather than a
true optimum — for the "-55" combos this only cleared at D=12, and for the
"-45" combos only at D=13.5. **The peak dB values actually observed in the
final CSVs (11-13 dB) are meaningfully higher than the true achievable
floor (8-10.5 dB).** This is a solver-tractability limit, not evidence that
D=8/10.5 is unreachable in principle.

**4. Combos with station 6 lowered to 45 dB are consistently the hardest.**
`s2-65_s6-45` and `s2-55_s6-45` had higher D floors (10.5 vs 8.0) and needed
a larger buffer above that floor to get a clean phase-2 solve (13.5 vs
12.0) than the two combos where station 6 stays at 55. Station 6's baseline
appears to be the single biggest lever on how hard this scenario is to
solve, more than station 2's.

**5. The weighted objective changes the noise *distribution*, not
necessarily the *peak*.** In `utilitarian/`, comparing no_weight vs weighted
for the same combo, the peak added-dB at the busiest station barely moves
(e.g. `s2-65_s6-55`: 11.76 → 11.76 dB) even though the average load shifts
substantially. The weighting acts on total (summed) transit cost, so it
redistributes load across the week but doesn't by itself suppress the
worst-case instant — that's specifically what the D search in
`utilitarian_peak/` targets instead.

## 5. Known limitations / caveats

- **Non-determinism near the D boundary.** Repeated solves at the exact same
  D sometimes succeeded and sometimes timed out (observed directly: 3/3
  isolated retries failed for `s2-65_s6-45` weighted at D=12, despite an
  earlier `utilitarian/` run succeeding cleanly at that same D). Treat single
  data points near a feasibility boundary as noisy; the buffered D values
  used here were chosen empirically for reliability, not because they're a
  precise threshold.
- **D is shared between weighted and no_weight per combo** in both domains,
  by design, so the peak-noise cap is directly comparable between the two
  variants within a combo. It is *not* comparable across combos with
  different D values (e.g. don't directly compare `s2-65_s6-55`'s peak of
  ~11.76 against `s2-65_s6-45`'s ~13.22 as if the same cap applied).
- **`utilitarian/`'s D=12 was chosen for route diversity, not noise
  minimization** — don't read it as "the noise floor for this scenario."
  `utilitarian_peak/`'s D values are the ones that speak to minimum
  achievable noise.
- All solves used soft-T with `T_max=7`; a different T_max would likely
  change both the feasibility floors and which routes are chosen.
