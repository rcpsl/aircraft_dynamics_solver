# dB Target Sweep — Data Collection Report

## 1. Purpose

For a fixed traffic scenario (Austin UAM network, `uam-config_finalized.json`), find — for
several "how loud is this getting" targets (**3dB / 8dB / 18dB**) and two ways of measuring
loudness (**average** and **peak**) — the most representative achievable noise level, by
searching over the solver's disparity parameter (`U`), aircraft loading, and two ambient
baseline stations. All solves went through the existing `solver_server_dB.py` Flask API
unmodified — nothing in the solver or frontend was changed; this is purely black-box
data collection against that API.

## 2. Base scenario

- Config: `uam-config_finalized.json` — N=14 aircraft, M=16 stations, adjacency graph,
  fixed start/end positions, `dbPerCraft=55`.
- **D = 50** ("noise cap," the solver's hard per-station dB-increase limit) — deliberately
  set high enough to never bind. The worst physically-reachable increase at any station,
  given this scenario's aircraft multipliers, tops out around 37dB, so D=50 acts as "don't
  care" rather than a real constraint.
- **Soft-T mode**: `hardT=false, T_max=7, weightTime=0.1` — the optimizer gets a 7-timestep
  horizon (vs. the ~4-timestep minimum-feasible T) and a small penalty for using extra time,
  so it has room to trade schedule length for better routing.

## 3. Two fairness modes

| Mode | Solver flags |
|---|---|
| **community_equal** | No optimization objective beyond the soft-T time penalty above — the solver just finds *any* feasible routing under the hard D/U constraints. |
| **people_equal** | `optimizeUtilitarian=true, weightUtilitarian=2`, **count mode** (`utilNoiseMode=false` — dB-sum mode is never used), station-weighted transit cost with per-station weights (1-indexed): `1:10, 2:5, 3:10, 4:5, 5:10, 6:10, 7:5, 8:5, 9:5, 10:10, 11:5, 12:5, 13:5, 14:5, 15:1, 16:5`. Higher weight = more expensive for an aircraft to be "in transit" through that station, so the optimizer is pushed to route around stations 1/3/5/6/10 when it can. |

`optimizePrioritarian`, `optimizeProportional`, and `proportionalAllocation` are **off** in
every run — only the community/people distinction above varies between the two modes.

## 4. Four baseline combinations

Two stations' ambient baseline dB were varied independently (all other stations fixed at
their `uam-config_finalized.json` values):

| combo folder | station 2 baseline | station 6 baseline |
|---|---|---|
| `s2-65_s6-55` | 65dB (config default) | 55dB (config default) |
| `s2-65_s6-45` | 65dB | 45dB |
| `s2-55_s6-55` | 55dB | 55dB |
| `s2-55_s6-45` | 55dB | 45dB |

`s2-65_s6-55` is the unmodified config and doubles as the reference/"current" scenario.

## 5. What "average" and "peak" mean

This was clarified mid-collection and is important for interpreting the numbers:

- **Peak** = the single largest instantaneous dB *increase* (added noise above ambient
  baseline) at any station, at any timestep, in the solved schedule. Straightforward max.
- **Average** = **not** a grand mean over the whole station×time grid (that undercounts
  badly, since most of the 16 stations see zero traffic most of the time — early exploration
  found that metric could never exceed ~2dB even at maximum traffic concentration). Instead,
  it's **the largest per-station time-average**: average each station's dB-increase over the
  active time window, then take the max across all 16 stations. I.e., "how loud does it get,
  on average, at the single most-affected station."

Both are computed over the *trimmed active window* — trailing timesteps where every aircraft
has already parked at its destination are excluded (mirrors the frontend's `effectiveT`
logic in `App.jsx`/`utils.js`).

## 6. Search methodology

For each of the 8 (combo × mode) pairs, four aircraft-loading variants were swept across
`U = 0, 1, 2, …, 16` (68 solves per pair, 544 total):

| variant | meaning |
|---|---|
| `baseline_mult` | Original config aircraft multipliers (sum of weighted traffic = 56). |
| `N14_mult1` | All 14 flights kept, but each multiplier forced to 1 (lightest possible per-flight weighting; sum = 14). |
| `N7_mult1` | Every other flight removed (7 remain), multiplier 1 each (sum = 7). |
| `N4_mult1` | Only 4 flights remain, multiplier 1 each (sum = 4). |

**Why reduce flight count/weight at all**, rather than just sweeping U on the original
traffic: multiplier scaling was probed first (0.1x–5x) and found that per-aircraft weight
floors at 1 (can't go lower), giving a noise *ceiling* around avg=4.5dB/peak=9.0dB at N=14 —
not low enough to reach the 3dB targets. Only actually removing flights pushes the ceiling
down further. Scaling multipliers *up* past ~1.5x, conversely, hits the solver's own
memory-safety guard (`noise_domain_too_large` — a deliberate Z3-blowup protection in
`solver_server_dB.py`, not a real infeasibility) rather than a genuine noise limit.

**Why U only up to 16, not higher**: empirically confirmed (full 0–50 sweep on the reference
combo) that every configuration's solution *plateaus* at a fixed ceiling once U passes
roughly 15 — looser disparity stops changing anything because the routing is already at its
structural maximum concentration. U beyond 16 is redundant.

For each (combo × mode), the closest achievable value **strictly below** each target was
picked from all 68×4 = 272 candidate (config, U) results. Full per-point raw data is in
`<combo>/<mode>/_search_log/search_log.csv`; anything that came back unsat, timed out, or
errored is separately logged in `<combo>/<mode>/unsat_timeout_record.csv` (31–55 bad points
per pair — see §8 caveats).

## 7. Output files, per `<combo>/<mode>/` folder

- **`3dB_avg.csv`, `8dB_avg.csv`, `18dB_avg.csv`** — the chosen solution's full per-station
  noise/traffic breakdown for the average-noise target.
- **`3dB_peak.csv`, `8dB_peak.csv`, `18dB_peak.csv`** — same, for the peak-noise target.
- **`picks_summary.csv`** — one row per target/metric: which aircraft variant and U value
  were chosen, and the resulting value.
- **`unsat_timeout_record.csv`** — every (config, U) point in the search that did *not*
  return a usable sat result, with the failure reason.
- **`_search_log/search_log.csv`** — the complete raw sweep (all 68×4 points, sat or not).

### CSV column reference (each target file)

```
Time Steps (T),<effective horizon after trimming>
Flights (N),<how many aircraft in this solution>
Total Traffic (sum of aircraft multipliers),<total weighted traffic>

Zone,Avg Added dB,Avg Total dB,Peak Added dB,Peak Total dB,Avg Aircraft,Peak Aircraft
```
One row per station (1–16). "Added" = increase above that station's ambient baseline;
"Total" = baseline + added. This exactly replicates the frontend's own "Save Results (CSV)"
per-zone export format (`buildZoneSummaryCSV` in `frontend/src/utils.js`), plus the
Flights/Traffic header line added on request so noise numbers are traceable to how much air
traffic produced them.

## 8. Final results table

| Combo | Mode | avg-3dB | avg-8dB | avg-18dB | peak-3dB | peak-8dB | peak-18dB |
|---|---|---|---|---|---|---|---|
| s2-65_s6-55 (default) | community | 2.51 | 7.51 | 7.51† | 3.01‡ | 7.78 | 14.77† |
| | people | 2.89 | 7.31 | 7.31† | 3.01‡ | 6.99 | 14.77† |
| s2-65_s6-45 | community | 2.80 | 6.26 | 6.26† | 4.77‡§ | 7.78 | 15.91† |
| | people | 2.04 | 6.25 | 6.25† | 4.77‡§ | 4.77 | 14.91† |
| s2-55_s6-55 | community | 2.39 | 6.58 | 6.58† | 3.01‡ | 7.78 | 12.55† |
| | people | 2.39 | 7.31 | 7.31† | 3.01‡ | 6.99 | 14.77† |
| s2-55_s6-45 | community | 2.96 | 7.93 | 8.95 | 3.01‡ | 7.78 | 15.91† |
| | people | 2.95 | 7.37 | 8.61 | 3.01‡ | 7.78 | 15.68† |

† = value is a hard ceiling for that combo/mode (nothing achievable is closer to the target
from below than this).
‡ = **peak-3dB is structurally unreachable** strictly under 3dB in every combo (see §9) —
these are the closest *available* values instead, on explicit instruction, not values that
satisfy "strictly below 3dB."
§ = this combo's closest-available peak-3dB point is 4.77dB rather than the 3.01dB floor
seen everywhere else — see §9 for why.

## 9. Key findings

**The 3.0103dB physical floor.** Peak noise repeatedly landed on exactly **3.0103dB**
(= 10·log₁₀(2)) across many different flight counts (N=3 through N=7 tested exhaustively in
early exploration) and U values. This is not a search artifact — it's the acoustic model's
behavior when exactly *one* aircraft (`aircraft_dB=55`) is present at a station whose ambient
baseline is *also* 55dB: `10·log10(10^5.5 + 1·10^5.5) − 55 = 10·log10(2) = 3.0103`. This
network's structural bottleneck stations (6 and 11) both sit at 55dB baseline in three of the
four combos, and essentially all traffic is forced through one of them, so any nonzero
routing hits at least this floor. **Peak strictly under 3dB is not achievable in this graph**
short of routing zero aircraft.

**Why `s2-65_s6-45` breaks the 3.0103 pattern.** In that combo, station 6 (one of the two
bottleneck hubs) is dropped to 45dB. A lone aircraft there produces `10·log10(11) ≈ 10.4dB`,
not 3.0103 — much louder relative to the now-quieter ambient. The *other* hub (station 11)
is still 55dB and should in principle still offer a 3.0103dB solution, but within the sampled
search space (N=14/7/4, integer U steps) the routing never isolated exactly one aircraft
there — the closest found was 4.7712dB (`10·log10(3)`, two aircraft at a 55dB station). A
denser search (finer U steps, N=3/5/6 variants — as was done for the reference combo) would
likely find 3.0103dB here too; it just wasn't run for the other three combos to keep the
search tractable. Treat 4.7712 as "closest found," not "closest possible," for this one cell.

**avg-18dB frequently collapses to the same answer as avg-8dB.** In 3 of 4 combos, both
targets pick the exact same (config, U, value) — the ceiling value happens to be under 18dB
too, so there's nothing closer to 18 than the same solution that's closest to 8. Only
`s2-55_s6-45` has enough headroom (quieter station 6 → different traffic distribution) to
produce genuinely different avg-8dB and avg-18dB answers.

**Non-monotonic U behavior near the sat/unsat boundary.** For every combo, noise vs. U is
*not* a smooth curve — Z3 finds structurally different tied-optimal solutions at nearby U
values (since with `community_equal` there's often no noise-related objective at all, just
"any feasible routing"), so avg/peak actually dip and spike within the boundary region
(~U=8–14) before settling into the flat ceiling above U≈15.

**Getting low targets required removing flights; getting high targets didn't.** Every
avg-3dB and peak-8dB pick came from a reduced-flight-count variant (`N14_mult1`, `N7_mult1`,
or `N4_mult1`). Every peak-18dB pick, and most avg-8dB/avg-18dB picks, came from the
unmodified `baseline_mult` traffic — the original scenario is already loud enough to satisfy
the higher targets, no modification needed.

## 10. Caveats / limitations

- **Search is not exhaustive.** Only 4 aircraft-loading variants and integer U steps 0–16
  were tested per combo/mode (68 points each). Finer U resolution or additional flight-count
  variants (as was done ad hoc for the reference combo, finding N=3/5/6 points) could
  possibly find marginally better answers, particularly for the s2-65_s6-45 peak-3dB case
  noted above.
- **31–55 of the 68 points per (combo, mode) pair did not return usable data** — either
  genuinely unsat (U too tight to route within the 7-timestep horizon), or the solve timed
  out against Z3's internal 240s budget, or (in a handful of cases) a solver server process
  died mid-sweep and the in-flight request errored out quickly rather than timing out
  properly. None of these affected the final picks (there was always overlapping coverage
  from another variant/U), but the raw `search_log.csv`/`unsat_timeout_record.csv` files are
  not a complete picture of every point in the grid.
- **`peak-3dB` values marked ‡ do not satisfy "strictly below 3dB."** They're the closest
  *available* values (used per explicit instruction after confirming true sub-3dB solutions
  don't exist), included so every target has a populated output file rather than a blank
  placeholder.
- A sibling `dB_target_sweeps/sufficientarian/` folder exists from a separate, independent
  data-collection session (testing the D parameter rather than U) — it is not part of this
  report and uses its own methodology; mentioned here only so it isn't mistaken for part of
  this dataset.
