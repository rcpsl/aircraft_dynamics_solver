# dB45_collection — integration handoff

**Written for**: a fresh session that has to work inside `dB45_collection/`, and
in particular has to wire `uam-dashboard-standalone-2026-07-20-v2.html` onto
this collection's data.

**Everything below was verified by reading the files in this folder plus
`../solver_server_dB.py`, and by re-deriving the station map and running
file/hash comparisons.** Where a claim comes from a code comment rather than
measurement, it says so.

This document covers the **data and the dashboard**. The generation-side tooling
(`scripts/`, `data/probes/`) is deliberately not documented here — it is not
needed to consume the dataset, and nothing in the integration path should depend
on it.

---

## 0. Rules for whoever reads this

1. **`dB45_collection/` is the only live dataset.** Do not read, cite, copy
   numbers from, or "fall back to" `../dB_target_sweeps/`. That is the older
   55 dB-per-craft collection; its reports and CSVs come from **previous trials
   with different parameters, a different aircraft level, and a different
   station map**. They are stale by construction and nothing in them carries
   over.
2. **When the dashboard and the data disagree about an assumption, the data
   wins.** The dashboard was built against the earlier dataset, so every
   parameter, label, threshold, lens name and mode name baked into its HTML is a
   *prior assumption*, not a requirement. Where §7.2 lists a conflict, the
   resolution is always: change the dashboard to match the CSVs. Never reshape,
   relabel, interpolate or substitute data to fit the existing UI.
3. **`../solver_server_dB.py` is read-only.** The whole collection's
   comparability rests on one unmodified solver. Timeout changes are made at
   runtime, never by editing that file.
4. **`data/base_model/Sample Communities.xlsx` is the single canonical source**
   for community attributes. See §3.6 — a second, conflicting copy used to sit
   beside it and has been deleted.
5. `dB45_collection/` **is now committed** (as of 2026-07-30; it was untracked
   in git for the whole generation phase, which is what earlier revisions of
   this document warned about). Overwriting a file is recoverable from git
   history — but `dB45_collection.zip` is *not* tracked, since it only bundles
   files that are versioned individually.

---

## 1. What this collection is

A re-run of the whole UAM noise-fairness study at **45 dB per aircraft**
(`dbPerCraft: 45`), rebuilt from scratch rather than patched from the earlier
55 dB work. Four fairness domains plus one CYO-sensitivity domain, across four
map configurations ("combos"), all solved through the same unmodified solver.

```
dB45_collection/
├── uam-dashboard-standalone-2026-07-20-v2.html   ← the dashboard (55 dB data inside!)
├── data/
│   ├── base_model/
│   │   ├── uam-config_45dB.json                  ← THE config; dbPerCraft=45
│   │   └── Sample Communities.xlsx               ← canonical community attributes
│   ├── full_routes/<combo>/<domain>/<mode>/*.csv ← 156 result files — the dataset
│   │   └── .../_search_log/attempts*.csv         ← solve-attempt records (provenance)
│   ├── probes/                                   ← generation-side; not an input to the dashboard
│   └── summaries/                                ← derived roll-ups (§6.5 — one is STALE)
├── build/                                        ← dashboard-data builder + its JSON output
├── logs/                                         ← raw solver run captures (provenance for §7)
└── scripts/                                      ← generation-side; not an input to the dashboard
```

`logs/` used to sit inside `scripts/`, interleaved with the `.py` files; it was
split out on 2026-07-30 so `scripts/` holds code only. Nothing reads those
captures programmatically, so the move breaks no path.

Combos (the only four that exist anywhere in the tree):

| combo | station 2 baseline | station 6 baseline |
|---|---|---|
| `s2-65_s6-55` | 65 dB | 55 dB |
| `s2-65_s6-45` | 65 dB | 45 dB |
| `s2-55_s6-55` | 55 dB | 55 dB |
| `s2-55_s6-45` | 55 dB | 45 dB |

Stations 2 and 6 are Create-Your-Own slots whose two options carry different
ambient levels; the combo *is* those two picks. Slots 11 and 13 never move a
baseline, so they do not appear in the combo name — but they do matter (§5.5).

---

## 2. The model and the solver

### 2.1 Physics

Added noise at station *m* with weighted aircraft count *n*:

```
added_dB(m, n) = 10·log10( 10^(baseline_m/10) + n·10^(45/10) ) − baseline_m
```

Consequence that drives almost every finding in this collection — **at 45 dB per
craft the whole fleet (56 weighted units) cannot make a loud station loud**:

| baseline | added dB with all 56 units on it |
|---|---|
| 45 dB | **17.56** |
| 55 dB | **8.20** |
| 65 dB | **1.93** |

So a "cap" of D = 18 is physically unreachable everywhere, D = 12 is unreachable
except at 45 dB stations, and D = 8 binds only at 45 dB stations. That is not a
bug in the ladders; it is the finding (§5.2, §5.3).

Peak values you will actually see in the files: `14.7712` = 29 weighted units on
a 45 dB station; `5.9106` = 29 units on 55 dB; `8.1954`, `7.7815`, `6.2325` are
other counts on 55/45 dB stations.

### 2.2 Two-phase solve, soft T

Every scenario in this collection was solved exactly as the Flask `/solve` route
does for `hardT = false`:

1. **Phase 1** — `find_min_T(...)`: cheapest possible question, "does *any*
   routing satisfy D and U?" Returns `T_min`. `status != "sat"` here means
   **genuine infeasibility**.
2. **Phase 2** — `optimize_objectives(...)` at `T = max(T_min, T_max)`, with
   `soft_T=True`, `w_time=0.1`. Returns the objective-optimal routing.
   `status == "phase2_failed"` means **the optimiser ran out of compute budget**,
   not that the scenario is infeasible — phase 1 already proved a routing exists.

**This distinction is enforced throughout the dataset and must not be blurred.**
A `phase2_failed` cell was answered by reseeding Z3 and, failing that, by
*leaving the cell unwritten*. The fleet was never cut in response, because a
demand cut is published as `demandFulfilledPct` and would be read as "the
fairness rule cost us service" when it was really "the solver ran out of time".

Soft T also means aircraft may **park at Start before departing** to stagger
noise windows, and must stay put once arrived (sticky arrival). Travel time is
the arrival tick, including any parked time.

### 2.3 Objective knobs, and what each one actually does

`optimize_objectives` normalises every term by its theoretical maximum, so the
weights are dimensionless.

| kwarg | effect |
|---|---|
| `optimize_util=True, util_noise_mode=False` | minimise **weighted aircraft-timesteps in transit** (count-based, cheap, linear, **baseline-blind**) |
| `optimize_util=True, util_noise_mode=True` | minimise **summed added dB** over all stations/timesteps (nonlinear dB lookup, expensive — abandoned here, §5.3) |
| `station_transit_weights=[...]` | per-station cost multiplier on the transit term. **Only read when `optimize_util` is true** — with it false, `eff_w_util = 0` and the weights are silently dropped |
| `optimize_prior=True, protected_stations=[...]` | minimise summed added dB over the protected set; reported as `protectedNoise` |
| `optimize_prop=True` | *maximise* dB on `proportional_stations`. Tested and rejected here — §5.6 |
| `soft_T=True, w_time` | penalty on pre-arrival timesteps; pulls aircraft to earliest arrival |

The "people mode carries a utilitarian term" pattern in the prioritarian domain
exists purely because of the `station_transit_weights` guard above.

### 2.4 Network geometry

16 stations on a 4×4 grid with king-move adjacency plus self-loops. All 14
aircraft run Downtown (station 1) ↔ Airport (station 16), 7 each way. Shortest
path is **3 hops**, and there is exactly one 3-hop path: **1 → 6 → 11 → 16**. At
`T = 4` (the phase-1 floor at full fleet in all four combos) that path is the
*only* option and the routing is **forced**. At `T = 5`, sixteen 4-hop paths open
up.

`{1, 6, 11, 16}` are therefore the stations no routing can avoid, which is why
they decide whether a fairness lens can bind at all.

---

## 3. Base model

### 3.1 Config — `data/base_model/uam-config_45dB.json`

Load-bearing fields (the rest are UI defaults the collection never uses):

- `dbPerCraft: 45` — asserted at load time; a mismatched config raises immediately.
- `M: 16`, `adjacency` — the 4×4 king-move matrix with self-loops.
- `startPos` / `endPos` — 14 aircraft, all 1↔16.
- `aircraftMultipliers: [2,5,5,5,5,5,5,5,5,2,5,3,2,2]` — **sum = 56 = MAX_TRAFFIC**.
  `demandFulfilledPct` in every CSV is `sum(mult)/56`.
- `stationBaselines: [65,65,55,45,55,55,55,55,55,55,55,65,45,45,65,65]` — indices
  1 and 5 (stations 2 and 6) are overwritten per combo.

Fields present but **not** used by this collection: `protectedStn`,
`proportionalStn`, `weightUtil/Prior/Prop`, `D`, `U`, `tMax`, `routeVertiports`,
`useRouteMode`. Each domain sets its own. Do not read policy out of the config.

### 3.2 Fleet variants

The demand ladder, used only when a constraint is *genuinely* infeasible at full
fleet:

| variant | N | traffic | demand |
|---|---|---|---|
| `baseline_mult` | 14 | 56 | 100 % |
| `N14_mult1` | 14 | 14 | 25 % |
| `N7_mult1` | 7 | 7 | 12.5 % |
| `N4_mult1` | 4 | 4 | 7.14 % |

Only `equal_allocation` and `sufficientarian` ever walk it. Exactly **8 of 156
files** sit below 100 % demand, all at `N14_mult1` / 25 %, all in the two `s6-45`
combos, all at the tightest cap (§6.3).

### 3.3 Population weights

```
PEOPLE_WEIGHTS = [10, 5, 10, 5, 10, 5, 5, 10, 5, 10, 5, 5, 5, 5, 1, 5]
```

High = 10, Medium = 5, Low = 1, with the four CYO slots pinned to a neutral 5.
This regenerates exactly from the workbook's Population column — **verified**.
Note station 15 (Industrial Center, population Low) has weight 1, making it the
cheapest sink in the grid *and* a 65 dB station.

### 3.4 The station map

Derived from the canonical workbook, read row-major over the `Dashboard Location`
4×4 grid:

| st | occupant | pop | income | race | transport | employment |
|---|---|---|---|---|---|---|
| 1 | Downtown *(vertiport)* | High | High | Mixed | Oasis | Hub |
| 2 | **CYO A**: Historic Black Neighborhood / New High-Density Development | Medium | Medium | Mostly Black | Some | Balance |
| 3 | Mixed Urban Community | High | Low | Mixed | Some | Balance |
| 4 | Affluent Suburban Neighborhood | Medium | High | Mostly white | Oasis | Few local jobs |
| 5 | Retail and Entertainment Center | High | High | Mostly white | Some | Hub |
| 6 | **CYO B**: International District / Exurban Commuter Town | Medium | Medium | Mostly Asian | Some | Balance |
| 7 | Popular Urban Residence with Shops | Medium | High | Mostly white | Oasis | Balance |
| 8 | Lower-Income Urban Neighborhood *(Dove Springs)* | High | Low | Mostly hispanic | Desert | Few local jobs |
| 9 | Gentrifying Neighborhood | Medium | Medium | Mixed | Some | Balance |
| 10 | University | High | Low | Mixed | Oasis | Hub |
| 11 | **CYO C**: Working-Class Homeowner Neighborhood / Suburban Tech Campus | Medium | Low | Mostly Hispanic | Some | Balance |
| 12 | Underdeveloped Neighborhood | Medium | Low | Mostly hispanic | Desert | Few local jobs |
| 13 | **CYO D**: Retirement Community / Quiet Rural Low-Income Community | Low | Medium | Mixed | Some | Few local jobs |
| 14 | Rural-Suburban Outskirts | Medium | Medium | Mixed | Some | Few local jobs |
| 15 | Industrial Center | Low | Low | Mixed | Desert | Hub |
| 16 | Airport *(vertiport)* | Medium | Low | Mixed | Some | Hub |

(CYO attribute columns show option 0, the grid-cell default.)

The dashboard's own `communityLayout` **already matches this exactly** — all 16
names, both vertiports and all four CYO slots in the right cells. The map
geometry needs no fixing.

### 3.5 The four lenses

Column selectors over the workbook, restricted to the twelve **fixed**
communities, so a participant's CYO picks cannot move a protected set:

| lens | selector | protected stations |
|---|---|---|
| `low_income` | `Income == Low` | `[3, 8, 10, 12, 15, 16]` |
| `people_of_color` | race not Mixed and not "Mostly white" | `[8, 12]` |
| `transit_desert` | `Transport == Desert` | `[8, 12, 15]` |
| `few_jobs` | `Employment == "Few local jobs"` | `[4, 8, 12, 14]` |

**These four are the complete lens set.** There is no `mostly_renters` lens in
this collection — the workbook's Housing column is not used as a selector — and
`people_of_color` is fully solved in both trees.

Only `low_income` contains an on-path station (16). That single fact makes 3 of
4 lenses degenerate in the frozen tree (§5.4).

CYO sensitivity — what each lens *would* gain if picks fed lens membership:

```
low_income       +11 (Working-Class Homeowner), +13 (Quiet Rural Low-Income)
people_of_color   +2 (Historic Black),  +6 (International District), +11 (Working-Class Homeowner)
transit_desert    +6 (Exurban Commuter Town),   +13 (Quiet Rural Low-Income)
few_jobs          +6 (Exurban Commuter Town),   +13 (either option)
```

Slots 6 and 11 are **on the forced path**, so those gains are the ones with
teeth. That is the entire premise of the `prioritarian_cyo` domain (§5.5).

### 3.6 The station 6 / station 8 assignment — settled, and why it must stay settled

`data/base_model/` briefly held two workbooks whose `Dashboard Location` grids
disagreed at stations 5–8. **The conflicting copy
(`Sample Communities.ORIGINAL-rowmajor.xlsx`) has been deleted.**
`Sample Communities.xlsx` is now the only source, and it is the one every
existing result was solved against.

The canonical assignment is therefore:

- **station 6 = CYO slot B** (International District / Exurban Commuter Town)
- **station 8 = Dove Springs / Lower-Income Urban Neighborhood** (High
  population, Low income, Desert transport, Few local jobs)

All 156 result files, `PEOPLE_WEIGHTS`, every lens list, and the dashboard's
`communityLayout` agree with this. The collection is internally consistent.

Two things to know:

- **The older 55 dB collection uses the opposite assignment.** Any station-6 or
  station-8 claim carried over from there is wrong here. This is one more reason
  rule §0.1 exists.
- **`lens_definitions.py`'s module docstring contradicts the data it produces**
  (it says "station 6 is Dove Springs"). That sentence is stale; the code, the
  workbook and all 156 files are right. Fix the comment if you touch that file;
  do not "fix" the code.

Station 6 is on the forced path `1-6-11-16` and station 8 is not, so this
assignment decides which fairness lenses can bind at all. **Changing it means
re-solving all 156 files.**

---

## 4. File format contract

Every result CSV has three sections:

```
# <key>,<value>                ← domain-specific preamble, variable length
# dbPerCraft,45                ← always stamped
# N,14
# aircraftMultipliers,[2, 5, 5, ...]
# totalTraffic,56
# maxTraffic,56
# demandFulfilledPct,100.0
# avgTravelTimeWeighted,3.0
# minTravelTime,3
# maxTravelTime,3
Time Steps (T),5
                                ← blank line
Routing (station per aircraft per timestep):
Aircraft,Multiplier,Start,End,T0,T1,T2,T3,T4
1,2,1,16,1,6,11,16,16
...                             ← N rows
                                ← blank line
Zone,Avg Added dB,Avg Total dB,Peak Added dB,Peak Total dB,Avg Aircraft,Peak Aircraft
Zone 1,0.22,65.22,1.11,66.11,5.80,29
...                             ← exactly 16 rows
```

Notes that matter for any parser:

- Preamble values may contain commas (e.g. `protectedStations,[3, 8, 10]`, and
  long prose warnings). **Split on the first comma only.**
- `Avg Aircraft` / `Peak Aircraft` are **multiplier-weighted** counts, not
  physical vehicles. 29 weighted units, not 29 aircraft.
- `avgTravelTimeWeighted` is multiplier-weighted; `min`/`max` are not.
- Zone rows are always 16 and always in order.

Preamble keys actually present, by domain (measured):

| domain | notable keys |
|---|---|
| `utilitarian` | `D`, `Drole`, `U`, `T_max`, `optimizeUtilitarian`, `weightUtilitarian`, `utilNoiseMode`, `stationTransitWeights`, `maxAvgAddedDb`, `maxPeakAddedDb` |
| `equal_allocation` | `U`, `Urole`, `D`, `Dbinding`, `variant`, `fullFleetFeasible`, plus `solvedAs`/`substituted`/`substitutionBasis` on 2 files |
| `sufficientarian` | `D`, `Drole`, `Dbinding`, `U`, `Urole`, `objective`, `objectiveNote`, `capBehaviourWarning`, `variant`, `fullFleetFeasible`, `phase2TimeoutMs`, `totalTransit` |
| `prioritarian` | `lens`, `lensSelector`, `protectedStations`, `protectedNoise`, `protectedNoiseDegenerate`, `T_floor`, `routingForcedByT`, `demandRole`, `avgAddedDbComparability` |
| `prioritarian_cyo` | all of the above plus `lensIncludesCyo`, `lensFrozenStations`, `lensGainedFromCyo`, `gainedOnPathStations`, `cyoSlots`, `cyoSlotOrder`, `cyoSelectionsMappingHere` |

**Known preamble gap**: the four `utilitarian/*/result.csv` D=12 files carry no
`totalTransit` — they were written before that key was stamped. The
`utilitarian_peak` and all `sufficientarian` files do carry it. Don't assume the
key is present.

---

## 5. The domains

### 5.1 `equal_allocation` — U as a real cap

`U ∈ {3, 8, 18}` is the **hard disparity cap** between any two stations' added
dB. `D = 50` is deliberately non-binding. Filenames `U3/U8/U18` name the
constraint the file was solved under — there is no selection rule and no post-hoc
labelling, so there is no "achieved" figure to report.

Modes: `community_equal` (no objective at all) and `people_equal`
(`optimize_util`, `w_util=2.0`, population-weighted transit).

`T_max = 7` for the whole domain. `avg` and `peak` are two readings of one
solution, both present in every zone table — they are **not** separate files.

### 5.2 `utilitarian` / `utilitarian_peak` — minimise total burden

Same objective (count-based transit), one parameter apart:

- `utilitarian`: `D = 12.0` — above the physical ceiling everywhere except the
  four 45 dB-baseline stations.
- `utilitarian_peak`: `D` = the phase-1 feasibility floor (**2.0** for the
  `s6-55` combos, **4.0** for the `s6-45` combos), where the cap must bind.

Modes: `no_weight` (vehicle-steps) and `weighted` (population-weighted →
people-exposed). `weighted` is the expensive one, and is where most of this
domain's unsolved cells are.

Measured: `no_weight` and `weighted` produce **byte-identical routing** in both
`s6-55` combos, and **different routing but identical zone tables** in both
`s6-45` combos — i.e. re-weighting by population changed which tied-optimal
routing the solver returned, not the published outcome.

### 5.3 `sufficientarian` — D as a floor of acceptable conditions

`D ∈ {3, 8, 18}` is a hard cap on added dB at any station at any timestep;
`U = 999` switches disparity off entirely so the absolute cap is the only
constraint in force. Modes `unweighted` / `weighted`.

**The objective is count-based and baseline-blind.** It was originally specified
as summed-dB; that version was built, run, and abandoned — at D = 3 (which forces
T up to 6–7) phase 2 exhausted its budget on every attempt in all four combos.
Two consequences, both stamped into every file as `objectiveNote`:

1. The regressive pull is gone. A summed-dB objective would push traffic onto
   already-loud stations, because noise is cheapest to add where it is already
   loud (1.93 dB at 65 dB vs 17.56 dB at 45 dB). The count objective has no such
   preference.
2. The physics is unchanged. Where the count objective happens to put traffic
   still decides who suffers, so read the traffic distribution against the
   baselines rather than assuming neutrality.

**`capBehaviourWarning`, stamped into every file, is the most important caveat in
the collection**: D is a cap, not a target. It forbids exceeding and gives no
incentive to go below, and the objective contains no noise term. Measured
consequence — in both `s6-45` combos, relaxing D from 8 to 18 let the optimiser
buy one timestep of travel (4.089 → 3.000) by raising peak added dB from
**7.782 → 14.771**. A looser cap licensed a louder answer; it did not leave the
answer unchanged.

Note also D = 18 is inert (ceiling 17.56) and D = 8 binds only at 45 dB stations.
`Dbinding` in the preamble says which.

### 5.4 `prioritarian` — priority to the worst-off (frozen lenses)

Minimise summed added dB over the lens's protected stations. `D = 18` and
`U = 50` are both non-binding by construction — **this domain's constraint is its
objective**.

| mode | N | demand | T_max | objective |
|---|---|---|---|---|
| `community` | 14 | 100 % | **5** | prioritarian only |
| `people` | 14 | 100 % | **4** | prioritarian + utilitarian, population-weighted |

Why `people` runs at T_max = 4: the combined objective blew the phase-2 budget at
T_max = 5 — measured, 240 s → failed at 268 s; 1500 s → failed at 1521 s; unit
multipliers at 600 s → failed at 606 s; **T_max = 4 → solved in 19 s**. T is the
only lever that works. It is nearly free here because T_min = 4, where the single
3-hop path is forced — and at T = 5 the solver has sixteen 4-hop alternatives and
*still* picks the same diagonal. Freedom present, unused.

**Two comparability traps, both stamped in the preamble:**

- `avg` added dB is averaged over T, so the T = 4 mode reads higher (2.8982 vs
  2.3185) for the *identical physical routing*. **Compare the two modes on peak,
  never on avg.**
- `routingForcedByT` is true whenever `T ≤ 4`. In that regime you may not say the
  objective *chose* the routing — nothing else was available.

**Degeneracy — the headline result of this domain.** Identical in all four combos
and both modes:

| lens | protectedNoise | degenerate? |
|---|---|---|
| `low_income` | **1.04** | no |
| `people_of_color` | 0.0 | **YES** |
| `transit_desert` | 0.0 | **YES** |
| `few_jobs` | 0.0 | **YES** |

Three of four lenses have protected sets sitting entirely off `{1, 6, 11, 16}`,
so the objective is satisfied at zero before the solver starts; every
zero-achieving routing ties and the solver returns an arbitrary member. **The
files differ; the fairness content does not.** All four lenses share one zone
table and one routing per (combo, mode). `protectedNoise` in the preamble is the
direct evidence; `0.0` means the lens did nothing.

### 5.5 `prioritarian_cyo` — the same domain with CYO picks feeding lens membership

This is the domain that **un-degenerates** the study, because CYO slots 6 and 11
are on the forced path.

Structure: 16 CYO selections × 4 lenses × 2 modes = 128 nominal variants, which
dedupe to **9 distinct solves per (combo, mode) = 72 files**, since a solve is
fully determined by `(baseline, protectedStations, mode)`. Files are named by
what the lens *gained*: `<lens>__gain_<stations>.csv`, or `__gain_none`.
`data/summaries/cyo_selection_map.csv` maps all 128 selections onto the file that
answers them — look up through that map rather than re-deriving it.

**The coupling that makes this non-obvious**: slots A and B pick a *baseline and
a community at once*. `s6-45` necessarily installs the Exurban Commuter Town
(Quiet 45, Transport = Desert, Few local jobs), dropping station 6 into
`transit_desert` and `few_jobs`. `s6-55` installs the International District
(Moderate 55, Mostly Asian), dropping it into `people_of_color`. **The combo
decides which lenses can bind.**

Once CYO feeds membership, `protectedNoise == 0` no longer means "degenerate".
The classification in `data/summaries/prioritarian_cyo_summary.csv` is:

| effect | meaning |
|---|---|
| `no-op` | pn = 0, routing identical → the lens changed nothing |
| `succeeded` | pn = 0 **but routing differs** → the solver rerouted off the protected set entirely. The opposite of degenerate. |
| `forced` | pn > 0, routing identical → cost charged, not chosen; no behaviour change |
| `traded` | pn > 0, routing differs → moved aircraft, still couldn't reach zero |

Measured outcome: **every `succeeded` row is in `community` mode.** `people` mode
runs at T_max = 4 where the routing is forced, so enlarging a protected set
changes the reported `protectedNoise` but cannot move a single aircraft. That is
structural, not a lens finding, and any UI that lets a participant toggle CYO in
people mode must say so.

Examples of real reroutes (community mode): `transit_desert__gain_6` in both
`s6-45` combos drops peak from 14.771 → 7.709; `people_of_color__gain_11`
(`s2-65_s6-45`) 14.771 → 12.553; `people_of_color__gain_2_11` (`s2-55_s6-45`)
14.771 → 9.542. All of them pay for it in travel time (3.0 → 4.0).

### 5.6 Proportional — tested and **rejected**; there is no proportional data

**`full_routes/` contains no proportional domain, and none is planned.**

A benefit rule (vertiport = 3, adjacent-and-High-income = 2, adjacent-and-Medium
= 1, adjacent-and-Low = 0) was implemented and then measured to be unexpressible
as noise burden in this network:

- Stations 2 and 5 are vertiport-adjacent so the rule grants them benefit, but
  they sit off the route the traffic takes and received **exactly 0.000 added dB
  in every scheme tried** — flat and tier-weighted, all four combos. The tier
  ordering was violated in every case.
- Restricting benefit to the corridor did not fix it either: corridor stations 6
  and 11 are **serial waypoints on the one shortest path**, so every aircraft
  traverses both exactly once and their traffic counts are equal *by
  construction*. Where their added dB differs, it differs purely from ambient
  level, not from traffic.

Conclusion: **in a two-vertiport line network, benefit tiers cannot be reflected
in noise burden.** The dashboard must treat proportional as a domain that does
not exist here (§7.2, row 1).

---

## 6. Data completeness — measured, not assumed

### 6.1 Counts

Target per combo: utilitarian 2 + utilitarian_peak 2 + equal_allocation 6 +
sufficientarian 6 + prioritarian 8 + prioritarian_cyo 18 = **42**; ×4 combos =
**168**.

**Present: 156. Unavailable: 12.**

| combo | present | unavailable |
|---|---|---|
| `s2-65_s6-55` | 38 | 4 |
| `s2-65_s6-45` | 40 | 2 |
| `s2-55_s6-55` | 38 | 4 |
| `s2-55_s6-45` | 40 | 2 |

### 6.2 ⚠ Twelve cells are unavailable because they take too long to solve

**State this plainly wherever it surfaces — in the build output, in the UI, and
in any writeup: these twelve results do not exist because the solver could not
finish them in a reasonable time. They are not infeasible, not unfair, not
missing by oversight, and not a service limitation.** Phase 1 proved in every one
of these cells that a full-demand routing exists; only the optimisation step ran
out of compute budget.

| file | budget spent before giving up |
|---|---|
| `s2-65_s6-55/utilitarian_peak/no_weight/result.csv` | 1800 s → failed at 1879 s |
| `s2-65_s6-55/utilitarian_peak/weighted/result.csv` | 1800 s → failed at 1965 s |
| `s2-55_s6-55/utilitarian_peak/no_weight/result.csv` | 1800 s → timeout |
| `s2-55_s6-55/utilitarian_peak/weighted/result.csv` | 1800 s → timeout |
| `s2-65_s6-45/utilitarian_peak/weighted/result.csv` | 1800 s → timeout |
| `s2-55_s6-45/utilitarian_peak/weighted/result.csv` | 1800 s → timeout |
| `s2-65_s6-55/equal_allocation/people_equal/U3.csv` | 600 s × T_max ∈ {5,4,9} → failed at 625/624/644 s |
| `s2-55_s6-55/equal_allocation/people_equal/U3.csv` | 600 s × T_max ∈ {5,4,9} → failed at 628/637/633 s |
| `s2-65_s6-55/sufficientarian/weighted/D3.csv` | 900 s × 3 seeds → failed at 916/920/915 s |
| `s2-55_s6-55/sufficientarian/weighted/D3.csv` | 900 s × 3 seeds → timeout |
| `s2-65_s6-45/sufficientarian/weighted/D8.csv` | 900 s × 3 seeds → failed at 924/932/920 s |
| `s2-55_s6-45/sufficientarian/weighted/D8.csv` | 900 s × 3 seeds → timeout |

Note the pattern: **every failure lands within ~1–3 % of whatever budget it was
given**, across random seeds and across T_max values. The solver is not
converging, so this is not a clock problem — throwing more hours at it is
measurably not the fix. A real resolution needs a different objective
formulation, and this collection does not modify the solver.

**Do not paper over these cells.** Not by substituting the other mode's file, not
by borrowing a neighbouring combo, not by cutting the fleet, and not by hiding
the control. The correct UI behaviour is an explicit "not available — this
configuration exceeded the solver's time budget" state.

### 6.3 The 8 sub-100 %-demand files

All `variant=N14_mult1`, 25 % demand, `fullFleetFeasible=False`, all in the two
`s6-45` combos at the tightest cap. These are **genuine infeasibility** at full
fleet — phase 1 returned unsat — not a solver artefact:

```
s2-65_s6-45, s2-55_s6-45 ×
  equal_allocation/{community_equal,people_equal}/U3.csv
  sufficientarian/{unweighted,weighted}/D3.csv
```

Here the demand cut **is** the finding — "this is what the constraint costs in
service". Every other file in the collection is at 100 %. Do not conflate these
eight with the twelve in §6.2; they are opposite situations.

### 6.4 Two substituted files — not solved with the objective they claim

```
s2-65_s6-45/equal_allocation/people_equal/U8.csv
s2-55_s6-45/equal_allocation/people_equal/U8.csv
```

Both carry `# substituted,True`, `# solvedAs,community_equal`, and
`# optimizeUtilitarian,False (substituted file - people objective not applied)`.
The routing was **copied from the `community_equal` solve** at the same combo and
U, after phase 2 failed at 240 s across all seeds. Stated basis: all six
loose-constraint pairs that did solve (U = 8 ×2, U = 18 ×4) are byte-identical
across the two modes, so the population weighting provably does not change the
solution at that U.

That basis is defensible, but **these two files are not evidence that the people
objective produces this answer**. Any UI that lets a user toggle Communities →
People at U = 8 in an `s6-45` combo is showing the same solve twice. Disclose or
exclude.

### 6.5 One stale summary

`data/summaries/prioritarian_cyo_summary.csv` is **missing 4 rows**:
`community/low_income__gain_11` for all four combos. Those four CSVs were written
by a later extended-budget retry (all succeeded: protectedNoise = 12.63, T = 5)
after the summary had been generated. **The CSVs are correct; the summary is
behind.** Regenerate it before using it as an index.

`data/summaries/prioritarian_summary.csv` and `cyo_selection_map.csv` are
current.

### 6.6 Cross-combo redundancy — how much does the station-2 knob buy?

Measured by hashing routing blocks across the `s2-65` / `s2-55` pairs:

- **`s6-55` pair**: only **2 of 38** comparable cells have different routing
  (`equal_allocation/community_equal/U3`, `sufficientarian/unweighted/D3`).
- **`s6-45` pair**: **11 of 40** differ — the tight-cap cells (U3, U8, D3, D8),
  `utilitarian/weighted`, `utilitarian_peak/no_weight`, and two
  `transit_desert__gain_6*` CYO variants.

So slot A (station 2) is **mostly but not entirely inert**: it matters only where
a constraint is tight enough that a quieter station 2 becomes a usable
alternative sink. Zone *totals* always differ trivially (station 2's own ambient
level changes), so a naive whole-file diff reports 100 % differences — compare
routing blocks, not whole files.

---

## 7. The dashboard, and what integrating it requires

`uam-dashboard-standalone-2026-07-20-v2.html` — 2474 lines, single file, no build
step. Two CDN `<script>` tags at the bottom (`@floating-ui`, `lucide`), which
means it is **not** currently offline-safe.

### 7.1 How it works

A 4-step wireflow (`Session → Shared map → Measure → Results`) driven by one
`state` object and full re-renders. The parts that matter for data:

```js
state = { count: 'Communities'|'People',
          timePattern: 'Average exposure'|'Peak exposure',
          comparison: 'Added UAM noise'|…,
          principle: 'equal'|'utilitarian'|'sufficientarian'|'prioritarian'|'proportional',
          equalLimit: '3 dB'|'8 dB'|'18 dB',
          sufficientLimit: '3.02 dB'|'8 dB'|'18 dB',
          priority: <lens label>,
          mapChoices: { cyo1:st11, cyo2:st2, cyo3:st6, cyo4:st13 }, … }
```

Lookup functions:

```js
modeKey()   → 'people' | 'community'
timeKey()   → 'peak' | 'avg'
comboKey()  → `s2-${cyo2==='new_density'?65:55}_s6-${cyo3==='international'?55:45}`
resultFor() → dashboardData[principle][combo]…
```

The embedded blob's shape — the contract a new build step must satisfy:

```js
dashboardData = {
  equal:           {combo: {mode: {avg|peak: {"3"|"8"|"18": LEAF}}}},
  utilitarian:     {combo: {mode: {avg|peak: LEAF}}},
  sufficientarian: {combo: {mode: {"3.02"|"8"|"18": LEAF}}},
  prioritarian:    {combo: {mode: {<lens>: LEAF}}},
  proportional:    {combo: {default|c11tech: LEAF}}
}

LEAF = {
  meta:  {T, N, traffic,            // always
          achieved?,  note?,        // equal
          D_used?,                  // utilitarian
          variant?,                 // sufficientarian
          protectedNoise?, protected?[]},  // prioritarian
  zones: [ {aa, at, pa, pt, ac, pc} × 16 ],   // ← exactly the Zone-table columns
  routes:[ {path:[1,6,11,16], flights:4} ],   // consecutive duplicates collapsed
  travelTime: {avg, min, max}
}
```

`zones` maps 1:1 onto the CSV Zone table (`aa`=Avg Added, `at`=Avg Total,
`pa`=Peak Added, `pt`=Peak Total, `ac`=Avg Aircraft, `pc`=Peak Aircraft), so
**that part is a drop-in**. `routes` is rendered as animated SVG corridors
labelled `<flights>/hr`; `travelTime.avg` is compared against a hardcoded `3`
(the shortest path) to produce "+N % longer", which is still correct here.

### 7.2 What the dashboard currently ships, and every conflict

**The embedded `dashboardData` is 55 dB-per-craft data from the previous
collection.** Verified: `equal.s2-65_s6-55.community.avg["3"].meta` is
`{T:7, N:7, traffic:7, achieved:1.36}` — an N = 7 / 12.5 %-demand fleet with a
post-hoc "achieved" figure, which no file in this collection has. The 45 dB
equivalent is N = 14, traffic 56, max avg 1.300 / peak 2.788. **Nothing in that
blob may be reused.**

Every row below resolves the same way, per rule §0.2: **the data is right, the
dashboard changes.**

| # | Dashboard assumes | The data says | Resolution |
|---|---|---|---|
| 1 | `proportional` is a fifth principle, `{default, c11tech}` | **no proportional domain exists** (§5.6) | Remove the principle. Optionally replace it with a short "why burden cannot follow benefit in a two-vertiport line network" explainer — that is a genuine finding, not an omission. Do not synthesise data for it. |
| 2 | prioritarian lenses are `low_income, transit_desert, few_jobs, mostly_renters`, with `people_of_color` shown as a disabled "data not yet available" option | the lens set is **`low_income, people_of_color, transit_desert, few_jobs`**; there is no `mostly_renters` (§3.5) | **Ship exactly four selections: drop `mostly_renters`, enable `people_of_color`.** Remove the disabled-option markup entirely. |
| 3 | sufficientarian caps are `"3.02" / "8" / "18"` | files are `D3 / D8 / D18`, i.e. D = 3.0 | Rekey to `"3"` and relabel. 3.02 was a physical floor in the old model; here 3 is a chosen cap. |
| 4 | `equal.meta.achieved` ("Actual noise difference") | no such field — **U is the cap**, not a target to be approached | Drop the card, or replace it with the observed added-dB spread. The "achieved" concept came from a selection rule this collection deliberately removed. |
| 5 | `utilitarian.meta.D_used` | preamble `# D` (12.0, or the floor 2.0 / 4.0) | Map `D` → `D_used`. |
| 6 | utilitarian `avg`/`peak` are always both available | `peak` comes from `utilitarian_peak`, and **6 of its 8 cells are unavailable** (§6.2) | The peak view must be able to render "not available — exceeded the solver's time budget". |
| 7 | every (combo × mode × setting) cell is populated | **12 cells are unavailable** (§6.2) | Emit an explicit marker, never an omitted key, and render it as an explained empty state. |
| 8 | the Communities/People toggle compares two like-for-like solves | in prioritarian the two modes run at **different T_max** (5 vs 4) | `avg` is not comparable across that toggle; peak is. Disclose at the toggle itself. |
| 9 | CYO slots 1 and 4 (stations 11, 13) only affect `proportional` | with `prioritarian_cyo` they affect **prioritarian**, and that is the collection's best interactive finding (§5.5) | Wire `mapChoices` → `cyo_selection_map.csv` → the `prioritarian_cyo` file. New capability, not a port. |
| 10 | two CDN scripts are reachable | — | Inline or drop them if the file must run offline or from `file://`. |

### 7.3 Concrete build plan

Add a build step that regenerates the embedded blob from the CSVs. It must:

1. **Parse** with a reader that splits preamble lines on the *first* comma only,
   and reads all three sections.
2. **Emit `zones`** directly from the Zone table — 16 rows, `aa/at/pa/pt/ac/pc`.
3. **Derive `routes`** from the routing block: for each aircraft take its path,
   collapse consecutive duplicates (the parked tail), group identical paths, and
   sum `Multiplier` into `flights`. Sanity check: `sum(flights)` must equal
   `# totalTraffic`.
4. **Emit `travelTime`** from `# avgTravelTimeWeighted` / `# minTravelTime` /
   `# maxTravelTime`.
5. **Emit `meta`** = `{T, N, traffic}` plus the per-domain extras in §7.1, and
   additionally carry through — because the UI needs to *say* these things —
   `demandFulfilledPct`, `fullFleetFeasible`, `variant`, `Dbinding`,
   `protectedNoise`, `protectedNoiseDegenerate`, `routingForcedByT`,
   `substituted`, `phase2TimeoutMs`.
6. **Emit an explicit unavailability marker** for each of the 12 cells in §6.2,
   carrying the reason ("exceeded the solver's time budget") so the UI can render
   it rather than showing a blank or falling back to another cell.
7. **Path map:**

| dashboard slot | file |
|---|---|
| `equal[combo][community\|people][avg\|peak]["3"\|"8"\|"18"]` | `full_routes/<combo>/equal_allocation/<community_equal\|people_equal>/U<3\|8\|18>.csv` — **one file feeds both `avg` and `peak`** |
| `utilitarian[combo][community\|people].avg` | `full_routes/<combo>/utilitarian/<no_weight\|weighted>/result.csv` |
| `utilitarian[combo][community\|people].peak` | `full_routes/<combo>/utilitarian_peak/<no_weight\|weighted>/result.csv` — **6 of 8 unavailable** |
| `sufficientarian[combo][community\|people]["3"\|"8"\|"18"]` | `full_routes/<combo>/sufficientarian/<unweighted\|weighted>/D<3\|8\|18>.csv` |
| `prioritarian[combo][community\|people][lens]` | `full_routes/<combo>/prioritarian/<community\|people>/<lens>.csv` — four lenses (§3.5) |
| *(new)* `prioritarianCyo[combo][community\|people][variant]` | `full_routes/<combo>/prioritarian_cyo/<mode>/<lens>__gain_<…>.csv`, selected via `summaries/cyo_selection_map.csv` |

Mode-name mapping is domain-specific: `community → {community_equal, unweighted,
no_weight, community}` and `people → {people_equal, weighted, weighted, people}`.

8. **Inject** the blob between explicit `/*DATA-START*/ … /*DATA-END*/` markers
   in the HTML (the current file has none — add them), and also write the blob to
   a JSON file so it is inspectable without diffing a 250 KB HTML file.
   Precompute; do not `fetch()` CSVs at runtime — that fails under `file://`.

Refresh the stale summary in §6.5 before running the build.

### 7.4 What has to be visible in the product, not just in comments

These are the claims a workshop participant could otherwise walk away with,
wrongly:

1. **Some configurations have no result because they take too long to solve**
   (§6.2) — 12 cells, stated as a solver limitation, explicitly *not* as
   infeasibility, unfairness, or a service constraint.
2. **D is a cap, not a target** (§5.3) — with the measured 7.782 → 14.771
   example. A looser rule licensed a louder outcome.
3. **Three of four prioritarian lenses do nothing in the frozen tree** (§5.4).
   Showing four visually distinct "results" for four lens picks, when the
   underlying zone tables are identical and `protectedNoise = 0`, is the single
   most misleading thing this dashboard could do. Surface
   `protectedNoiseDegenerate`.
4. **In people mode the routing is forced** (T_max = 4) — CYO picks change the
   reported protected-noise number but cannot move an aircraft (§5.5).
5. **`avg` is not comparable across the Communities/People toggle** in
   prioritarian; peak is (§5.4).
6. **Two `people_equal/U8` files were not solved with the people objective**
   (§6.4).
7. **8 cells serve only 25 % of demand**, and *there* that genuinely is the
   fairness cost (§6.3) — the opposite of point 1, and must not be worded the
   same way.
8. **There is no proportional principle here, and the reason is structural** — a
   two-vertiport line network cannot express benefit tiers as noise burden
   (§5.6). Worth a panel, not a silent omission.

---

## 8. Open decisions for a human

1. **The 12 unavailable cells** (§6.2). Accept and disclose, or invest in
   reformulating the expensive objectives? More retry time is measurably not the
   answer.
2. **The two substituted files** (§6.4). Keep with disclosure, or withdraw them
   so the collection contains only files actually solved under the objective they
   name?
3. **Whether `prioritarian_cyo` becomes a UI feature or stays an analysis
   artefact.** It is 72 of the 156 files and the only place the fairness lenses
   demonstrably change behaviour — but only in community mode.
4. ~~**Commit this folder.**~~ Done 2026-07-30 — see §0.5.

---

## 9. Integration status — done (2026-07-22)

`uam-dashboard-standalone-2026-07-20-v2.html` is now wired onto this collection.
Every resolution in §7.2 was applied in the direction rule §0.2 requires: the
data was left alone and the dashboard changed.

**New build step** — `build/build_dashboard_data.py`, run with
`python build/build_dashboard_data.py` from `dB45_collection/`. It reads the 156
CSVs plus `summaries/cyo_selection_map.csv`, writes `build/dashboard_data.json`
for inspection, and injects the same blob between `/*DATA-START*/` and
`/*DATA-END*/` in the HTML. It asserts rather than assumes: every file stamps
`dbPerCraft = 45`, every routing's summed `flights` equals its `totalTraffic`,
all 16 CYO selections resolve for both modes and all four lenses, and exactly
the 12 known-unavailable cells are missing. Re-run it after any data change.

**What changed in the dashboard**

| §7.2 | resolution as shipped |
|---|---|
| 1 | `proportional` keeps its button but renders an explainer panel — the 0.000 dB benefited neighbours and the serial-waypoint problem — instead of data. No proportional numbers exist anywhere in the build. |
| 2 | Four lenses: `low_income`, `people_of_color`, `transit_desert`, `few_jobs`. `mostly_renters` and the disabled-option markup are gone. |
| 3 | Sufficientarian rekeyed to `3 / 8 / 18`. |
| 4 | `achieved` replaced by the spread that actually resulted, computed from the zone table in whichever reading is selected. |
| 5 | `D` → `D_used`. |
| 6, 7 | The 12 cells are explicit `{unavailable, reason, budget}` markers and render as a panel stating the solver ran out of time, that phase 1 proved a routing exists, and that nothing was substituted. |
| 8 | Disclosed at the Who-counts toggle itself and again in the results. |
| 9 | `prioritarian_cyo` is wired: a "Count Create-Your-Own communities too" checkbox routes `mapChoices` through `cyoSelectionMap` to the right variant. |
| 10 | Both CDN `<script>` tags removed — nothing in the page carried `data-tooltip` or `data-lucide`. The file has no external references and no runtime fetches. |

**One correction beyond §7.2.** Reading `protectedNoise == 0` as degeneracy is
right in the frozen tree and wrong in `prioritarian_cyo`, where it can equally
mean the solver rerouted clear of the protected set — the opposite result. The
build therefore stamps each CYO leaf with `meta.effect`
(`no-op`/`succeeded`/`forced`/`traded`), classified against a routing no lens
constrained, and the UI reads that instead of the bare number. Verified to agree
with `prioritarian_cyo_summary.csv` on all 72 leaves.

**§6.5 cleared.** `summaries/prioritarian_cyo_summary.csv` was regenerated from
the CSVs and is now 72 rows. The reference routing used for `same`/`differs`
reproduces all 68 pre-existing rows exactly, and the rebuilt file confirms the
§5.5 claim independently: all 12 `succeeded` rows are in `community` mode.

**Verification.** A jsdom harness drives the real page through all 1024
reachable results cells — 16 map configurations × 2 counts × 2 time patterns ×
every principle and setting. Zero uncaught errors, zero failures, no
`undefined`/`NaN` reaching the DOM. The disclosure counts reconcile against the
data: 72 unavailable panels (24 utilitarian-peak + 16 equal-U3 + 32
sufficientarian visits), 64 demand-cut warnings (the 8 files of §6.3 × 8
visits), 16 substitution warnings (the 2 files of §6.4 × 8 visits).

**Still open**: the four decisions in §8. Nothing here forecloses any of them.
Also unfixed: the stale `station 6 is Dove Springs` docstring in
`scripts/lens_definitions.py` (§3.6) — untouched because it sits outside the
integration path, but it is still wrong and still worth correcting.
