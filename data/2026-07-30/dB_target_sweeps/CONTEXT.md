# dB_target_sweeps — orientation for a fresh session

**Read this file first.** It is the only file in this folder written to be
self-verifying: every factual claim below was checked against the actual CSVs,
the config JSON, or `solver_server_dB.py` at the time of writing. §8 lists the
checks and the three places where the prose reports in `reports/` disagree with
the data.

**Trust order** when something conflicts:

1. `../solver_server_dB.py` — the solver. Defines what every number *means*.
2. The `#`-preamble inside each CSV — written by the code that produced that
   exact file. Self-documenting and per-file accurate.
3. `scripts/*.py` — the generators. Show exactly which config produced which file.
4. `reports/*.md` — **narrative, partly unverified, and known to contain at
   least three errors (§8.2).** Useful for "why", not authoritative for "what".

---

## 1. What this dataset is

A workshop tool asks: *if we fly an urban air-mobility (UAM) network over
Austin, who eats the noise?* The 16 "stations" are a 4×4 grid of Austin
community archetypes. A Z3 solver routes aircraft between vertiports; each
**fairness principle** is a different objective handed to that solver. This
folder is the swept output — every principle × every scenario knob — so a
dashboard can show participants how the choice of principle moves the noise.

**Five fairness domains** (`equal_allocation`, `sufficientarian`,
`utilitarian` (+`utilitarian_peak`), `prioritarian`, `proportional`), each
solved across **4 baseline combos** (§4).

---

## 2. Folder map — what each thing is

```
dB_target_sweeps/
├── CONTEXT.md          ← you are here
│
├── reports/            ── PROSE. Methodology + findings. No data. See §7.
│   ├── DASHBOARD_DATA_INTEGRATION.md      base model, station numbering, findings #1-8
│   ├── DASHBOARD_DATA_INTEGRATION_V2.md   what changed: routes + the 5th domain
│   ├── HANDOFF_DASHBOARD_WIRING.md        read-order + prompt for a wiring session
│   ├── full_routes_REPORT.md              route-CSV format spec, tied-optimal caveat, the 5 gaps
│   ├── equal_allocation_README.md         ┐
│   ├── sufficientarian_REPORT.md          │ per-domain methodology
│   ├── utilitarian_data_report.md         │ ("why is this number what it is")
│   ├── prioritarian_REPORT.md             │
│   ├── proportional_REPORT.md             ┘
│   ├── travel_time_README.md              derived travel-time table
│   └── alt_selection_maxdemand_README.md  alternate target-pick rule (analysis, not a domain)
│
├── data/               ── ALL NUMBERS. Two generations of it — see §3.
│   ├── full_routes/    ★ NEW SET (primary). Per-aircraft flight paths + zone summary.
│   │   └── <combo>/<domain>/<mode>/<scenario>.csv        127 files
│   ├── aggregate_only/   OLD SET. Zone summary only, no paths. 155 CSVs + search logs.
│   │   ├── equal_allocation/<combo>/<mode>/
│   │   ├── sufficientarian/<combo>/<mode>/
│   │   ├── utilitarian/{utilitarian,utilitarian_peak}/<combo>/
│   │   └── prioritarian/{step1_…,step2_…,step3_baseline_sweep/<combo>/<mode>}/
│   ├── base_model/
│   │   ├── uam-config_finalized.json    the scenario: N, M, adjacency, baselines, multipliers
│   │   └── Sample Communities.xlsx      the 12 communities + 8 CYO options + grid layout
│   ├── summaries/                       derived cross-scenario tables (§6)
│   └── dashboard_data.json              precomputed blob, built from aggregate_only/
│
├── scripts/            ── EVERY .py. Nothing else imports from here.
│   ├── _paths.py           canonical roots — all other scripts import these
│   ├── _solve_helpers.py   solve + CSV-write core (imports ../solver_server_dB directly)
│   ├── run_combo.py        regenerates one combo's 30 route files
│   ├── run_proportional.py regenerates the proportional domain
│   ├── retry_*.py          longer-timeout / seeded retries for the 5 gaps (§5)
│   ├── build_dashboard_data.py  aggregate_only/ → dashboard_data.json (+ injects into v2 html)
│   ├── compute_travel_time.py, make_travel_time_summary.py   derived tables
│   ├── proportional_benefit.py, extract_station_income.py    benefit-map inputs
│   ├── analyze_proportional.py, reselect_maxdemand.py        post-hoc analyses
│   └── logs/               stdout from past retry rounds
│
├── dashboards/         ── HTML prototypes.
│   ├── fairness-dashboard-v2.html   ★ real data inlined; extend this one
│   ├── fairness-dashboard-v1.html     OUTDATED MOCK — invented numbers, do not copy data
│   └── uam-dashboard-standalone-2026-07-20.html
│
└── archive/            ── superseded handoff txt + zip snapshots. Ignore.
```

---

## 3. The two data sets — which one do I want?

Both describe **the same scenarios**. The difference is what got recorded.

| | `data/aggregate_only/` (OLD) | `data/full_routes/` (NEW) |
|---|---|---|
| Per-zone noise summary | ✅ | ✅ (identical schema) |
| Per-aircraft flight paths | ❌ never recorded | ✅ station per aircraft per timestep |
| Demand-fulfilled figures | ❌ implicit | ✅ explicit `totalTraffic`/`maxTraffic`/`demandFulfilledPct` |
| Solver config in-file | partial | ✅ full `#` preamble on every file |
| Coverage | 100% of the 120 scenarios | **115/120** + 12 proportional = 127 files |
| Search logs, `picks_summary.csv`, `d_min.txt`, unsat records | ✅ only here | ❌ |
| Prioritarian step1/step2 exploratory runs | ✅ only here | ❌ (step3 only) |
| Proportional domain | ❌ didn't exist yet | ✅ only here |
| Feeds `dashboard_data.json` | ✅ currently | ❌ not wired yet |

**Rule of thumb**

- **Default to `full_routes/`.** It is a strict superset for the 115 scenarios
  it covers, and the only source of flight paths and the proportional domain.
- **Fall back to `aggregate_only/`** for the 5 files `full_routes/` is missing
  (§5), and go there for anything about *how a target was chosen* — the search
  logs, `picks_summary.csv` (which `U`/fleet variant won), `d_min.txt`
  (feasibility floors), and unsat/timeout records live only there.
- **Caveat:** `full_routes/` was re-solved, not copied. For
  `equal_allocation` the objective is weak enough that many routings tie for
  optimal, so **25 of 46 files landed on a different (equally valid) tie than
  the old set** — flagged in-file as `matchesHistorical,False`. Never assume a
  `full_routes` number equals its `aggregate_only` twin for that domain; the
  other domains have strong-enough objectives that they do match.

---

## 4. The scenario, verified against `base_model/uam-config_finalized.json`

- **M=16** stations = a 4×4 grid, read **row-major** (row 1 = stations 1–4).
  Adjacency is *exactly* the king-move neighborhood plus self-loops — verified
  for all 16 stations. Self-loops matter: soft-T mode requires them.
- **`stationBaselines` = `[65,65,55,45,55,55,55,55,55,55,55,65,45,45,65,65]`**
  (ambient dB per station: 65=Loud, 55=Moderate, 45=Quiet).
- **N=14** physical aircraft, `dbPerCraft=55`.
  `aircraftMultipliers = [2,5,5,5,5,5,5,5,5,2,5,3,2,2]`, **summing to 56** —
  each physical aircraft stands for that many "virtual" flights. 56 is the
  denominator for every `demandFulfilledPct`.
- **All 14 aircraft fly between station 1 and station 16 only.** 7 go 1→16
  (indices 0–3, 10–12, weight 27), 7 go 16→1 (indices 4–9, 13, weight 29).
- **The only shortest 1↔16 path is `1-6-11-16`** (length 3) — verified by
  exhaustive enumeration. Everything else is length ≥4. This is why stations
  6 and 11 dominate every result, and why station 6's baseline is a swept knob.
- **4 baseline combos** override exactly two stations, leaving the other 14 at
  their config values:

  | combo folder | station 2 | station 6 |
  |---|---|---|
  | `s2-65_s6-55` | 65 (default) | 55 (default) |
  | `s2-65_s6-45` | 65 | 45 |
  | `s2-55_s6-55` | 55 | 55 |
  | `s2-55_s6-45` | 55 | 45 |

  **Only station 2 is a CYO (Create-Your-Own) slot** — slot A, 65 = New
  High-Density vs 55 = Historic Black Neighborhood, so that axis really is the
  participant's pick. **Station 6 is not**: audit A1 (§8.1) confirms it is
  Dove Springs, a fixed community, and its sweep is a researcher sensitivity
  knob — station 6 sits at grid `(2,2)` on the unique shortest path, so its
  ambient dB is the highest-leverage single number in the model. The CYO slots
  are stations **2, 8, 11, 13**; slots B/C/D were never swept. Earlier drafts
  of this file and `DASHBOARD_DATA_INTEGRATION.md` call both swept stations CYO
  slots — that is wrong for station 6.

### How the solver actually produces a row (`../solver_server_dB.py`)

Read this before interpreting any number:

- **Noise model.** A station's *increase* is
  `10·log10(10^(baseline/10) + n·10^(55/10)) − baseline`, where `n` is the
  **weighted** count of aircraft present. Louder stations mask added aircraft
  better, so the same `n` yields a *smaller* increase at a 65 dB station than
  at a 45 dB one. All dB is scaled ×100 to integers for Z3.
- **`D`** = hard cap on that *increase*, per station per timestep. It is
  **not** a cap on total level, and a station with 0 aircraft can never
  violate it. `D=50` in `equal_allocation` is deliberately non-binding.
- **`U`** = hard cap on the *disparity* between any two stations' increases.
  `U=999` (sufficientarian) disables it; `U=50` is effectively "don't care".
- **Aircraft are only noisy while in transit** — from the first timestep they
  leave their start until the timestep they arrive. Parked aircraft at t=0 and
  arrived aircraft are silent. This is why a station can host aircraft and
  still show 0 added dB.
- **Two phases.** Phase 1 (`find_min_T`) searches upward for the smallest
  feasible `T` under `D`/`U` alone — no objectives. Phase 2
  (`optimize_objectives`) rebuilds everything in a `z3.Optimize` at fixed
  `T` and minimizes a weighted sum. **All objectives are normalized by their
  theoretical maxima**, so `weight=1` means genuinely equal weighting.
- **Soft-T** (`hardT=false`, used by *every* file here): phase 2 runs at
  `T = max(T_min, T_max)` and adds a small `weightTime` penalty per pre-arrival
  timestep. The optimizer gets slack to trade schedule length for better
  routing. `T_max` is a budget, not a deadline.
- **Prioritarian** minimizes summed dB at `protectedStations`.
  **Proportional** uses a **negative** coefficient on `proportionalStations` —
  i.e. it *maximizes* noise there. That is intentional: burden follows benefit.
- **Phase-2 failure falls back to the phase-1 route** with a `warning`. Such a
  route ignores the weights entirely. No file in this dataset is a fallback —
  failures were dropped, which is why 5 files are missing rather than wrong.

---

## 5. Per-domain config — read straight from the CSV preambles

Every file carries its own config. This table is the verified summary.
`weighted` / `people_*` modes all mean **one identical thing**: the solver was
given `stationTransitWeights = [10,5,10,5,10,10,5,5,5,10,5,5,5,5,1,5]`
(cost of routing *through* each station — higher = avoid), i.e. "count people,
not communities."

| domain | modes | D | U | T_max | fleet | objective |
|---|---|---|---|---|---|---|
| `equal_allocation` | `community_equal` / `people_equal` | 50 (non-binding) | swept, from `picks_summary.csv` | 7 | varies per pick: `baseline_mult` (56) / `N14_mult1` (14) / `N7_mult1` / `N4_mult1` | none, or util w=2 + station weights |
| `sufficientarian` | `unweighted` / `weighted` | **8 / 18 / ~3.02** (the sweep) | 999 (off) | 7 | N=14, unit multipliers (traffic 14) | utilitarian w=1 |
| `utilitarian` + `utilitarian_peak` | `no_weight` / `weighted` | 12 | 50 | 7 | full fleet (traffic 56) | utilitarian w=1 |
| `prioritarian` | `community` (N=14) / `people` (N=7) | 18 | 50 | **5** | ⚠ **differs by mode** | prioritarian w=1 |
| `proportional` | `high_benefit` / `all_benefited` | 18 | 50 | 5 | N=14 / N=7 | proportional w=1 (maximizes) |

⚠ **Prioritarian's two modes are not comparable head-to-head** — verified:
all 16 `community` files are N=14, all 16 `people` files are N=7. The mode
changes fleet size *and* objective at once, so a community-vs-people delta
conflates the two.

**Prioritarian lenses** (the `protectedStations` list, verified in-file):

| lens file | protected stations | equity framing |
|---|---|---|
| `low_income` | 6, 12 | low-income communities of color |
| `transit_desert` | 6, 12, 15 | already a transit desert |
| `few_jobs` | 4, 6, 12, 14 | few local jobs |
| `mostly_renters` | 1, 3, 5, 10, 15, 16 | mostly renters |

**The 5 files missing from `full_routes/`** — verified present-or-absent by
enumeration, and the list in `reports/full_routes_REPORT.md` §4 is **correct**:

```
s2-65_s6-55/equal_allocation/people_equal/3dB_avg.csv
s2-55_s6-45/equal_allocation/people_equal/8dB_peak.csv
s2-55_s6-45/sufficientarian/weighted/D8.csv
s2-55_s6-45/utilitarian/weighted/result.csv
s2-65_s6-45/utilitarian/weighted/result.csv
```

All five exist in `aggregate_only/` — use those, minus flight paths. Four hit
a genuine Z3 wall (failure time tracks the timeout regardless of seed); the
`s2-65_s6-55` one was only ever retried with the wrong fleet config, so its
difficulty is **unknown** — don't lump it in. `scripts/retry_multiseed.py` has
the corrected config ready.

---

## 6. File formats

**Route CSV** (`data/full_routes/**.csv`) — three blocks:

```
# domain,combo,mode,<domain-specific params>,N,aircraftMultipliers,
# totalTraffic,maxTraffic,demandFulfilledPct[,historicalValue,reproducedValue,matchesHistorical]
Time Steps (T),7

Routing (station per aircraft per timestep):
Aircraft,Multiplier,Start,End,T0,T1,...,T6
1,1,1,16,1,6,11,16,16,16,16          ← this aircraft's whole flight

Zone,Avg Added dB,Avg Total dB,Peak Added dB,Peak Total dB,Avg Aircraft,Peak Aircraft
Zone 1,0.52,65.52,1.46,66.46,1.40,4   ← exactly 16 rows, always
```

Verified: all 127 files have the routing block and exactly 16 zone rows.
`Avg`/`Peak` are over timesteps; `Total = baseline + Added`.

**Aggregate CSV** (`data/aggregate_only/**.csv`) — the same `Zone,…` block with
a thin `Time Steps / Flights / Total Traffic` header and no routing block.

**`data/summaries/`**

| file | what |
|---|---|
| `travel_time_summary.csv` | one row per route file (127) — avg/min/max travel time, derived from the routing tables, no re-solve |
| `proportional_travel_time_summary.csv` | same, proportional only (12 rows) |
| `picks_maxdemand.csv` | equal_allocation targets re-picked under a max-demand rule (alternative analysis; does not replace `picks_summary.csv`) |

---

## 7. Where to look, by task

| I want to… | Go to |
|---|---|
| Draw flight paths on a map | `data/full_routes/<combo>/<domain>/<mode>/*.csv`, Routing block |
| Compare fairness principles on noise | `data/full_routes/` zone tables (all domains, one combo) |
| Show noise-vs-demand tradeoff | `demandFulfilledPct` in any route-CSV preamble |
| Know why a target/`U` was chosen | `data/aggregate_only/equal_allocation/<combo>/<mode>/picks_summary.csv` + `_search_log/` |
| Know what was infeasible | `aggregate_only/.../unsat_timeout_record.csv`, `sufficientarian/unsat_record.csv`, `utilitarian/**/d_min.txt` |
| Understand a domain's *why* | `reports/<domain>_*.md` — but re-verify numbers (§8) |
| Wire a new dashboard | `reports/HANDOFF_DASHBOARD_WIRING.md`, then the two `DASHBOARD_DATA_INTEGRATION*.md` |
| Extend the existing dashboard | `dashboards/fairness-dashboard-v2.html` + `scripts/build_dashboard_data.py` |
| Re-solve / fill a gap | `cd scripts && python run_combo.py <combo>` (skips existing files — always safe) |
| Change what a number *means* | `../solver_server_dB.py` — nothing here has ever modified it |

**Regenerating.** All scripts import `scripts/_paths.py`, which derives every
root from its own location — no absolute paths, nothing to edit. Solving needs
`z3` and a few minutes per file; the derived/build scripts are instant:

```bash
cd scripts
python build_dashboard_data.py     # aggregate_only/ → data/dashboard_data.json (+ v2 html)
python compute_travel_time.py      # full_routes/    → summaries/travel_time_summary.csv
python run_combo.py s2-55_s6-45    # re-solve one combo (slow; skips existing)
```

---

## 8. Verification ledger

### 8.1 Checked and confirmed

- `full_routes/` holds **127** CSVs; **all 127** have a routing block and
  **exactly 16** zone rows.
- The 5 missing files are exactly the ones `full_routes_REPORT.md` §4 names.
- Config: N=14, M=16, `dbPerCraft=55`, multipliers sum to 56, baselines array,
  king-move adjacency, `1-6-11-16` as the unique shortest path — all confirmed.
- Prioritarian mode/fleet mismatch (community N=14, people N=7) — confirmed
  across all 32 files.
- `people`/`weighted` station weights `[10,5,10,5,10,10,5,5,5,10,5,5,5,5,1,5]` —
  match between `equal_allocation_README.md`, `scripts/_solve_helpers.py`, and
  the CSV preambles.
- **Audit A1 — station↔community map (2026-07-21).** Re-derived from
  `base_model/Sample Communities.xlsx` against the config and the CSV
  preambles. **Numbering is strict row-major over the `Dashboard Location` 4×4
  grid, with NO 6↔8 swap.** Three independent confirmations: `stationBaselines`
  16/16 (neutral on 6 vs 8 — both 55); `stationTransitWeights`
  `[10,5,10,5,10,10,5,5,5,10,5,5,5,5,1,5]` 16/16 under "CYO slot → 5, else
  High=10/Medium=5/Low=1", where the four stations pinned to 5 are exactly
  **2, 8, 11, 13** = the CYO slots in row-major position and station 6 carries
  10 = High population = Dove Springs; and all four prioritarian lens lists
  regenerating exactly from Excel attribute columns (15/15 references, no
  tuning). `DASHBOARD_DATA_INTEGRATION.md`'s swap rests on the single fact that
  `s6` sweeps {55,45} like CYO slot B's options — better explained by station 6
  being `(2,2)` on the unique shortest path `1-6-11-16`, i.e. the highest-
  leverage ambient-dB knob in the model. See §9.2.4.
- **Audit A2 — prioritarian lens correctness (2026-07-21).** Downstream of A1.
  Lists are correct as authored (`low_income` = Income=Low ∧ Mostly-Hispanic;
  `transit_desert` = Transport=Desert; `few_jobs` = Employment="Few local
  jobs"; `mostly_renters` = Housing=Renters) — no remap needed. But the
  objective is **degenerate for 3 of 4 lenses**; see §9.1.9.
- **End-to-end**: after the reorganization, `build_dashboard_data.py`,
  `compute_travel_time.py`, and `make_travel_time_summary.py` were re-run and
  reproduced `dashboard_data.json`, `travel_time_summary.csv`, and
  `proportional_travel_time_summary.csv` **byte-for-byte identically**.

### 8.2 Report claims that are WRONG — corrections

1. **`reports/utilitarian_data_report.md` §1 states "8 aircraft go 1→16
   (indices 0-3, 10-13), 6 go 16→1 (indices 4-9)."** The config says
   `startPos = [1,1,1,1,16,16,16,16,16,16,1,1,1,16]` — it is **7 and 7**
   (index 13 flies 16→1, not 1→16). Use §4 above.
2. **`reports/full_routes_REPORT.md` §3 states "44 equal_allocation files: 19
   matched, 25 differed."** Actual count is **46 files: 21 matched, 25
   differed**. The §3 text predates the retries its own §4 describes and was
   never updated. The 25-differed figure is right; the totals are stale.
3. **`archive/README_FOR_DASHBOARD.superseded.txt`** describes the pre-reorg
   layout and only 4 domains. Superseded by this file; kept for history only.

### 8.3 Not verified — treat as unknown

- Every **finding/interpretation** in `reports/*.md` (the numbered findings,
  the proportional F1–F7, the "does the lens change anything" conclusions).
  The configs and file inventories check out; the *conclusions drawn from
  them* were not re-derived. Re-check any number before quoting it.
- ~~The **station↔community mapping** and the documented **station 6↔8
  swap**~~ — **resolved by audit A1, see §8.1.** Row-major, no swap.
- The **prioritarian people-mode preambles are not self-describing.**
  `run_combo.py` passes `stationTransitWeights` and `weightUtilitarian`
  through from the `step3` source but omits both from the emitted `#` header,
  so the 16 `full_routes/*/prioritarian/people/*.csv` files do not record that
  they are population-weighted *or* that they run a combined
  prioritarian+utilitarian objective. Read the `aggregate_only/` step3 twin to
  recover them. Note "people" here does **not** mean the same thing as in the
  other domains: it is a different scenario (N=7, unit multipliers, combined
  objective), not a weighting variant of the community run.
- The **old set's** provenance. Its generating scripts were not kept, so
  `aggregate_only/` cannot be regenerated or re-verified — only compared
  against `full_routes/`, which was re-solved independently.

---

## 9. Known problems — read before presenting any of this

From a prior audit of the data and of `dashboards/fairness-dashboard-v2.html`.
Items marked ✅ were re-verified against the files while writing this doc;
unmarked ones were not.

### 9.1 Data / methodology

1. ✅ **`equal_allocation`'s selection rule is broken for the `avg` metric.**
   The rule is "closest achievable value strictly below the target," which
   *maximizes* noise subject to the target. The avg ceiling (~6–9 dB) sits far
   under the 18 dB target, so the rule degenerates into "pick the loudest
   available" — and that rewards *small* fleets, because avg is a max-over-
   stations of a per-station time average and a light fleet concentrates
   traffic. Verified consequences: **the 18 dB pick is byte-identical to the
   8 dB pick in 6 of 8 avg cells (and 0 of 8 peak cells)**; and
   `s2-55_s6-45/community_equal` @18 dB is **strictly dominated** — 8.948 dB at
   25% demand vs 7.933 dB at 100% demand, i.e. louder *and* 75% less service.
   **`peak` is unaffected.** Do not present avg 8 dB vs 18 dB as a tradeoff.
2. ✅ **The dB target labels in `equal_allocation` are not constraints.**
   `D,50` in **all 46 files** — non-binding, 8 dB and 18 dB alike. The labels
   are post-hoc selection tags over a `U`-sweep, but read naturally as "we
   capped noise at 8/18 dB." Label them carefully in any UI.
3. ✅ **`sufficientarian_REPORT.md` hides a demand cut.** It says D=8 and D=18
   both used "the full 14-aircraft fleet — no aircraft removed." True for
   *physical* aircraft, false for service: **D=8 runs unit multipliers
   (traffic 14 = 25% demand); D=18 runs the real multipliers (traffic 56 =
   100%)**. The `demandFulfilledPct` field that `full_routes/` added is what
   exposes this — another reason to prefer the new set.
4. ⚠️ **D=18 in `sufficientarian` is effectively inert — but the audit's number
   is wrong.** The cap never binds, so the conclusion stands. However the
   claimed max of 14.77 dB is not sufficientarian's: the true max Peak Added dB
   under D=18 is **17.85 dB** (`s2-55_s6-45/unweighted`), **identical in both
   data sets**. The margin is 0.15 dB, not 3.2 dB. 14.7712 is an
   *`equal_allocation`* peak-18 pick value, appearing in three cells.
5. **Tied-optimal divergence is broader than `full_routes_REPORT.md` §3
   documents.** §3 scopes it to `equal_allocation`; it also hits
   `utilitarian_peak/weighted`. Sharpest case: `s2-65_s6-55/community_equal`'s
   8 dB and 18 dB avg files have *provably identical* solver inputs
   (`baseline_mult`, U=12, D=50) yet different routings and noise maps
   (4.4719 vs 5.3320) — pure Z3 non-determinism, no config difference to blame.
6. **The four §5 wall files are not a patience problem.** They fail at ~1–2% of
   whatever timeout is given (425/420 s, 907–912/900 s, 609/600 s), regardless
   of seed or reduced `T_max`. A fix needs `optimize_objectives` code changes.
7. ✅ **The demand denominator conflates two different cuts.** N=7 drops
   aircraft 14→7 *and* resets multipliers from real weights (sum 56) to 1
   (sum 7) — an **8× traffic drop, not 2×**. Legitimate as a swept variant for
   equal/sufficientarian; a solver artifact for prioritarian people-mode and
   proportional `all_benefited`. Verified: all 16 prioritarian people files
   report `demandFulfilledPct,12.5`.
8. ✅ **`prioritarian_REPORT.md` §5d understates its own number 4×.** It says
   people-mode "only serves half the fleet." Half the *aircraft* (7/14), but
   **12.5% of demand** (7/56). The prose is wrong; 12.5% is right.
9. ✅ **The prioritarian objective is degenerate for 3 of the 4 lenses — the
   "4/4 distinct outcomes" are tie-breaks, not fairness.** Read straight off
   the solver's own reported objective in all 32
   `aggregate_only/prioritarian/step3_baseline_sweep/**` preambles:
   `protectedNoise = 0.0` for **`low_income`, `transit_desert` and `few_jobs`
   in every one of the 8 combo×mode cells**. Only `mostly_renters` binds
   (11.59 / 13.55 community, 2.60 people). A zero optimum means the routings
   those three lenses produce are an arbitrary pick from a large tied-optimal
   set, so the differing community-mode zone tables carry no fairness signal.
   Confirmed structurally: **every aircraft starts or ends at station 1 or 16**,
   so any list touching 1/16 is forced nonzero, and empirically stations
   **1, 11, 16 are never avoidable** while **3, 4, 8, 9, 13, 14 carry zero
   traffic in all 32 files** — protecting those six is a no-op. Net effect:
   `few_jobs [4,6,12,14]` is really a lens on station 6 alone, `transit_desert`
   on {6,15}, `low_income` on {6,12}. Cross-lens check is clean otherwise —
   each lens's own routing is minimal on its own stations in all 8 cells, so
   the objective does do what it says; there is just nothing left to trade.
   **In people mode it collapses further**: only **2/4** distinct routings
   (`low_income`/`transit_desert`/`few_jobs` are identical), because N=7 at
   12.5% demand plus `totalTransit = 15500` in all 16 files leaves the combined
   objective fully tied. *Consequence for the pending lens redefinition
   (§9.2.4): `people_of_color [6,12]`, `transit_desert [6,12,15]` and
   `few_jobs [4,6,12,14]` all avoid 1/11/16, so all three stay degenerate. Only
   the widened `low_income [3,6,10,12,15,16]` would bind, via station 16.
   Dropping `mostly_renters` therefore removes the domain's only currently
   binding lens.*

### 9.2 Dashboard (`dashboards/fairness-dashboard-v2.html`) — not yet fixed

Zone numbers are exact across all 124 control states. The problems are
**coverage, three UI bindings, and disclosure** — not the underlying data.

1. **Proportional is one-third wired.** Only `high_benefit.csv` loads. The 8
   `all_benefited` / `all_benefited__c11-tech` files are unused, which removes
   finding F3 and the station-11 slot-C lever (F7) that
   `proportional_REPORT.md` calls the dataset's best interactive moment.
   `comboKey()` ignores `cyo1`; the UI says "Nothing to choose for this
   principle." *This is the real work.*
2. **The benefit overlay never recolors for slot C.** The blob hardcodes
   `[3,1,0,0,2,1,0,0,0,0,0,0,0,0,0,3]` in all four combos. Combo-independence
   is correct; CYO-independence is not — station 11 must recolor to benefit 2
   when slot C = Suburban Tech Campus, even in `high_benefit` mode. Currently
   picking Tech Campus leaves it reading "Benefit: None." *Cheapest fix: a
   conditional at `benefitLabel`'s two call sites, no new data.*
3. **`protectedNoise` ignores the Peak/Average toggle.** It is a single scalar,
   always max avg added dB over protected stations. Switch to Peak and every
   other value moves while this one doesn't — `s2-65_s6-55`/`mostly_renters`
   shows 1.18 dB where peak is 5.91. *Contained fix.*
4. ✅ **RESOLVED — the lens lists are right; the dashboard layout is wrong.**
   This item previously read "prioritarian protected-station lists use pre-swap
   numbering … the actual low-income tile, station 8 (Dove Springs), goes
   unprotected." **That is backwards.** Audit A1 (see §8.1) re-derived the
   numbering from `Sample Communities.xlsx` and found strict row-major with
   **no 6↔8 swap**: station 6 *is* Dove Springs, station 8 is CYO slot B. All
   four lens lists regenerate exactly from Excel attribute columns, 15/15
   station references. So `low_income = [6,12]` is correct as authored and
   needs no remap; what must change is the **dashboard's tile layout**, which
   follows `DASHBOARD_DATA_INTEGRATION.md`'s swap recommendation. Un-swapping
   it is the open work, and it costs CYO slot B its dB data (station 8 was
   never swept) — see the audit note for the disposition options.
5. **None of the three required disclosures shipped** — zero hits for the
   tied-optimal caveat (25 equal_allocation cells differ from the historical
   values still inlined in the html), the proportional income-direction value
   judgment (F6 — regressive by design), or F5.
6. **No regeneration script for the dashboard blob.** The 148 KB blob was
   hand-inlined. `scripts/build_dashboard_data.py` rebuilds only the
   `aggregate_only/` four-domain `dashboard_data.json`, not the v2 blob — so if
   one of the 5 outstanding solves lands, there is no path to re-emit.
7. **Two denominators in one card.** Copy says "≈58 flights per hour"
   (from the 800-traveler demand assumptions) while demand % divides by the
   solver's 56.
8. **Three `unpkg` CDN scripts** (floating-ui ×2, lucide) plus a CSP allowing
   several external hosts. Both are null-guarded, so offline it degrades to no
   tooltips and no icons rather than breaking — but the handoff asked for a
   self-contained file, which matters if the workshop room has no wifi.
9. **Route direction is folded** (16→1 legs reversed into 1→16), so the map
   can't show 27 outbound vs 29 return. Almost certainly intentional — flagged
   so it stays a decision rather than an accident.
