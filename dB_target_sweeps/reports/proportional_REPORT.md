# Proportional-Benefit Domain — Data Report & Dashboard Integration

**Audience**: the chat session wiring the fairness dashboard. This is the fifth
fairness domain, alongside equal / utilitarian / sufficientarian / prioritarian.
It is built *on top of* the existing Z3 solver — no new solver, no changes to
`solver_server_dB.py`.

---

## 1. What this domain is

The other four domains shape a **burden** (noise) map. Proportional adds a
**benefit** map and then asks the solver to make **burden follow benefit**:
the tiles that get the vertiport's upside should absorb proportionally more of
its noise.

Two separate objects:

1. **The benefit map** — deterministic, no solver. A pure function of vertiport
   location + grid adjacency + each tile's income (see §2).
2. **The routing** — the *existing* solver's `optimizeProportional` objective,
   fed the benefited stations as `proportionalStations`. That term has a
   **negative coefficient** (`solver_server_dB.optimize_objectives`,
   *"negative coefficient = maximize"*), so it **maximizes** noise at those
   stations. That is the "burden follows benefit" mechanic, already in the code.

## 2. The benefit rule (deterministic)

```
every tile starts at benefit 0
vertiport tile                       -> 3  (High)
grid-adjacent tile (next + diagonal):
    income High                      -> 2  (Medium)
    income Medium                    -> 1  (Low)
    income Low                       -> 0  (None)
overlap (adjacent to 2 vertiports, or vertiport+adjacent) -> max()
```

- **"Adjacent (next + diagonal)"** = the 4×4 grid king-move neighborhood. This is
  *exactly* the solver's `adjacency` matrix minus its self-loops — verified: the
  config adjacency **is** the king-move grid (e.g. station 6 → `{1,2,3,5,7,9,10,11}`).
  So no separate geometry is needed; `king_neighbors()` in `proportional_benefit.py`
  reads the same matrix the solver uses.
- **Income** is **not** in `uam-config_finalized.json` (which only has baselines,
  populations, adjacency). It is extracted straight from **`Sample Communities.xlsx`**
  by `extract_station_income.py`, which reads all three sheets, resolves the CYO
  slot options, and applies the documented **station 6↔8 swap**
  (`DASHBOARD_DATA_INTEGRATION.md` §1). Slot **defaults** are used (per spec).

**Base-scenario benefit map** (vertiports = `{1,16}`, default income):

| St | Benefit | Income | | St | Benefit | Income |
|--|--|--|--|--|--|--|
| **1** | **3 Vertiport** | High | | 9 | 0 | Medium |
| 2 | 1 Low | Medium | | 10 | 0 | Low |
| 3 | 0 | Low | | 11 | 0 (⚠ CYO) | Low |
| 4 | 0 | High | | 12 | 0 | Low |
| 5 | 2 Medium | High | | 13 | 0 | Medium |
| 6 | 1 Low | Medium | | 14 | 0 | Medium |
| 7 | 0 | High | | 15 | 0 | Low |
| 8 | 0 | Low | | **16** | **3 Vertiport** | Low |

→ **high-benefit tiles** (benefit==3) = `{1, 16}`
→ **all-benefited tiles** (benefit>0) = `{1, 2, 5, 6, 16}`

**⚠ The benefit map is combo-independent but NOT fully CYO-independent.** Income
doesn't change across the four `s2/s6` combos (they only move ambient dB), so the
benefit map is identical across all four. **But station 11 is CYO slot C**, and
its income flips **Low → High** if the participant picks *Suburban Tech Campus*
instead of the default *Working-Class Homeowner*. Station 11 is adjacent to
vertiport 16, so that pick raises station 11 from benefit **0 → 2**, adding it to
the `all_benefited` set. Since station 11 is also the corridor's loudest tile
(§6), this is a genuine dashboard lever — **both slot-C states ship** (default +
`__c11-tech`), see §7. No other CYO slot touches a vertiport-adjacent tile (slot
A/st2 and slot B/st6 are Medium either way; slot D/st13 isn't adjacent).

## 3. The datasets (2 modes × CYO scenarios × 4 combos = 12 files)

| Mode | CYO scenario | `proportionalStations` | N | Demand | File |
|--|--|--|--|--|--|
| `high_benefit` | any (CYO-invariant) | `{1, 16}` (benefit==3) | **14** | 100% | `high_benefit.csv` |
| `all_benefited` | default | `{1, 2, 5, 6, 16}` (benefit>0) | **7** | 12.5% | `all_benefited.csv` |
| `all_benefited` | c11-tech | `{1, 2, 5, 6, 11, 16}` | **7** | 12.5% | `all_benefited__c11-tech.csv` |

**Why `high_benefit` is one file per combo (not per CYO):** its set is `{1,16}`,
the vertiports, whose benefit==3 never depends on any CYO choice — so it's
generated once and is valid for every CYO combination. **Why `all_benefited` has
two variants:** only **slot C (station 11)** changes the benefit map (§2), and it
does so only for the benefit>0 set — see §7.

**Why N differs by mode:** `high_benefit` ({1,16}) is tractable at the full N=14
fleet (~37 s/combo). `all_benefited` reliably times out at N=14 (measured 253 s >
240 s Z3 budget) and needs the N=7 "every-other" fleet cut — the **same
tractability fix and convention** as prioritarian people-mode
(`prioritarian/REPORT.md` §5d), solving in ~8–14 s. N is held **fixed across each
mode's combos**, so combo-to-combo comparison within a mode is clean; the
**cross-mode** dB comparison is confounded by N (see §6 — compare *where* burden
lands, not absolute dB).

**Solver config** (both modes, all combos — mirrors the working prioritarian
community config): `hardT=false`, `T_max=5`, `D=18`, `U=50`,
`weightProportional=1.0`, `weightTime=0.1`, `optimizeProportional=true`, all other
objectives off. `T_max=5`/`D=18` is the combination proven to leave real route
choice while staying in budget (`prioritarian/REPORT.md` §5b). All 8 solves
succeeded (SAT, no phase-2 fallback).

## 4. File format

`full_routes/<combo>/proportional/{high_benefit,all_benefited}.csv`. Identical to
the other `full_routes/` files (preamble + routing table + per-zone table), with
**four benefit columns appended** to the zone table:

```
Zone,Avg Added dB,Avg Total dB,Peak Added dB,Peak Total dB,Avg Aircraft,Peak Aircraft,Benefit,Tier,Income,Demand Served
```

- `Benefit` (0–3), `Tier` (Vertiport/Medium/Low/None), `Income` (High/Medium/Low)
  — the deterministic overlay, same for both modes at a given combo (default CYO).
- `Demand Served` — weighted demand originating/terminating at that tile; nonzero
  only at vertiports (56 at N=14, 7 at N=7). Kept a **separate column** (per spec),
  not folded into the benefit score.
- Preamble adds `proportionalStations`, `vertiports`, `benefitRule`, `incomeSource`,
  `proportionalNoise` (the solver's maximized objective value) on top of the usual
  `N`/`totalTraffic`/`demandFulfilledPct`.

The zone table's dB columns are byte-compatible with every other domain, so
`build_dashboard_data.py`'s `parse_zone_csv` reads them unchanged; only the four
extra columns are new.

## 5. Control-state → file lookup (for the dashboard)

| Principle | Knobs | File |
|--|--|--|
| Proportional | mode=high_benefit | `full_routes/<combo>/proportional/high_benefit.csv` |
| Proportional | mode=all_benefited, slot C = Working-Class (default) | `.../all_benefited.csv` |
| Proportional | mode=all_benefited, slot C = Tech Campus | `.../all_benefited__c11-tech.csv` |

`combo` from slots A/B as usual; `metric` ∈ {avg, peak} switches displayed dB
columns (same as other domains). **The slot-C pick only matters for
`all_benefited`** — for `high_benefit`, read `high_benefit.csv` regardless of slot
C (and recolor station 11's `Benefit` cell live: 0 if Working-Class, 2 if Tech
Campus — the routing/noise is identical either way, only the overlay differs).
The benefit overlay (Benefit/Tier/Income) is a **second choropleth** the card
should show *next to* the noise map — the whole point is the visual comparison
"here's who benefits / here's who bears the noise."

## 6. Findings the dashboard should show

**F1 — Burden follows benefit, on average.** In every combo and both modes, mean
`Avg Added dB` at benefited tiles (benefit>0) exceeds non-benefited tiles, ~2.5–3×:

| combo | high_benefit (ben / non) | all_benefited (ben / non) |
|--|--|--|
| s2-65_s6-55 | 1.86 / 0.69 | 1.06 / 0.27 |
| s2-65_s6-45 | 3.01 / 1.00 | 2.12 / 0.27 |
| s2-55_s6-55 | 2.16 / 0.69 | 1.21 / 0.28 |
| s2-55_s6-45 | 3.04 / 0.96 | 2.22 / 0.28 |

The objective genuinely concentrates noise onto benefited tiles. **This is the
headline: proportional allocation works directionally.**

**F2 — …but it CANNOT load the highest-benefit tiles, because vertiports are
parked-quiet.** The single loudest tile is almost always the **benefit-0 bridge
station 11** (or benefit-1 station 6), *never* a vertiport. In `high_benefit`
mode the maximize target is `{1,16}` — yet stations 1/16 read only ~1.5 dB while
z11 reads ~7.5 dB (benefit 0). **Why:** aircraft parked at their start/end
produce no noise (the solver's `active` window excludes parked aircraft), and all
traffic must cross the mandatory `1→6→11→16` bridge. So "maximize noise at the
vertiports" is structurally near-impossible — the burden physically lands on the
un-benefited corridor middle. This is the domain's most important teaching point:
**the tiles that benefit most (endpoints) are exactly the ones that can't absorb
burden; the burden falls on bottleneck tiles that get nothing.**

**F3 — Broadening the set (`all_benefited`) does pull burden onto the adjacent
tiles.** Adding `{2,5,6}` makes stations 5 (benefit 2) and 2 (benefit 1) light up
(z5 ≈ 1.2 in every combo, absent in `high_benefit`), and station 6 becomes the
loudest tile instead of 11. So the wider benefit definition improves tile-level
burden-follows-benefit — **at the cost of the N=7 fleet cut (finding F5).**

**F4 — The quiet-community paradox amplifies the objective.** In `s6-45` combos
(station 6 ambient dropped to 45), z6's added dB jumps (e.g. 5.7 → 10.4 in
high_benefit) and `proportionalNoise` roughly doubles (26.5 → 53.0 in
all_benefited). A quieter ambient makes the same aircraft a *larger* increase,
and the maximize objective actively seeks that — so picking the "quiet" Exurban
option makes station 6 bear even more relative noise. Consistent with
`DASHBOARD_DATA_INTEGRATION.md` finding #6.

**F5 — Wider proportional burden costs service.** `all_benefited` only solves with
half the fleet (N=7, 12.5% of demand) where `high_benefit` runs the full 14. Show
this on the service-level strip: "spreading the burden-follows-benefit rule to
more tiles is only operable at reduced service." This is the fairness↔service
tradeoff (`DASHBOARD` finding #2) surfacing in a new place.

**F6 — The benefit rule is spatially lopsided by income — a standalone finding
that needs no solver.** Vertiport 1 (Downtown) spreads benefit to 3 neighbors
(2/5/6); vertiport 16 (Airport) spreads benefit to **none** — its neighbors
11/12/15 are all Low-income (Working-Class Homeowner, Del Valle, Industrial) and
the rule zeroes Low-income adjacency. So *as specified*, the rule gives the
affluent-adjacent downtown corridor benefits and the low-income airport corridor
nothing. **Disclose the value judgment explicitly:** this rule allocates benefit
*proportional to income* (ability to use UAM) — the deliberate inverse of the
prioritarian lens, which *protects* low-income tiles. Present the two side by side.

## 7. The station-11 CYO lever — F7, the headline interaction (data included)

Station 11 is CYO **slot C**: **Working-Class Homeowner** (Low income, default) vs
**Suburban Tech Campus** (High income). It is adjacent to vertiport 16, so the
Tech Campus pick flips it benefit **0 → 2**, adding it to the `all_benefited` set
(`all_benefited__c11-tech.csv`). Station 11 is also the corridor's loudest tile
(F2), so this one community choice transforms the fairness outcome:

| combo | metric | default (`all_benefited`) | c11-tech |
|--|--|--|--|
| s2-65_s6-55 | loudest tile | z6 (3.6, benefit 1) | **z11 (3.4, benefit 2)** |
| s2-55_s6-55 | loudest tile | z6 (3.1, benefit 1) | **z11 (3.4, benefit 2)** |
| all 4 | mean non-benefited dB | 0.27–0.28 | **0.00** |
| all 4 | mean benefited dB | 1.06–2.22 | 1.41–2.38 (higher) |

**F7 — one community choice completes burden-follows-benefit.** Under default
income, station 11 (the loud bottleneck) has benefit 0, so the domain's whole
tension (F2: burden lands on an un-benefited tile) holds. Picking Tech Campus makes
station 11 benefited, and then **every noise-bearing tile is a benefited tile** —
the mean non-benefited dB drops to **0.00 in all four combos**, and in the s6-55
combos station 11 becomes the single loudest *and* benefited tile. So the answer
to "does burden follow benefit?" literally flips (partial → essentially complete)
on a single slot-C pick. This is the domain's best interactive teaching moment:
surface it as *"what if a tech campus moved in next to the airport?"* and show the
non-benefited map going dark. (In the s6-45 combos the quiet-community paradox, F4,
keeps station 6 loudest even in c11-tech — worth showing that the two effects
stack.)

## 8. Caveats / to confirm with the team

- **Cross-mode dB isn't comparable** (N=14 vs N=7). Compare *pattern* (which tiles
  bear burden vs. the benefit map), or compare combos *within* a mode. The report's
  F1 table is within-mode-consistent.
- **Regressive-by-design.** The income direction (High→2, Low→0) is taken verbatim
  from the spec. If the intent was progressive (benefit the under-served), flip
  `_ADD_BY_INCOME` in `proportional_benefit.py` and rerun — one-line change.
- **Vertiports fixed at `{1,16}`** (per spec). The generator reads them from a
  constant; `routeVertiports` in the config is unused here.
- **Parked-vertiport limit (F2)** means "maximize at endpoints" is weak. If the
  team wants benefit tiles to genuinely bear the most noise, the benefit rule
  should reward *corridor* tiles (6/11), or vertiports should be interior stations
  — a modeling decision, not a code bug.

## 9. Reproduce

All in `full_routes/`, no Flask, no code changes to `solver_server_dB.py`:

- `extract_station_income.py` — station→income from the xlsx (6↔8 swap, CYO-aware).
- `proportional_benefit.py` — the deterministic benefit map + the two station sets.
  Run standalone to print the benefit table.
- `run_proportional.py [combo]` — runs all solves via the existing solver and writes
  the CSVs; skips files that already exist (safe to re-run). The `SCENARIOS` list at
  the top drives the CYO matrix: add a `(label, cyo_choices, jobs)` entry to generate
  a new user-choice combination (e.g. `("c11-tech", {11:1}, [("all_benefited","__c11-tech")])`).
  The N=7 cut for `all_benefited` and N=14 for `high_benefit` are wired via `MODE_N`.
- `analyze_proportional.py` — prints the F1/F2 numbers from the generated CSVs.
- `make_travel_time_summary.py` → **`proportional/travel_time_summary.csv`** — supplementary
  dataset: average aircraft travel time per scenario (one row per data file). Travel time =
  timestep index of first arrival at End (0-indexed = move-steps to finish; shortest 1↔16
  route = 3). Columns: `combo, mode, cyoScenario, N, T, avgTravel, avgTravelWeighted,
  minTravel, maxTravel`. Pure post-processing of the routing tables (no re-solve); `avgTravel`
  vs `avgTravelWeighted` diverge only at N=14 (non-uniform multipliers). All aircraft finish
  in 3–4 steps; the c11-tech variant has identical travel times to its default (same N=7
  routing shape). Regenerate any time with `python make_travel_time_summary.py`.

**CYO matrix note:** the only benefit-relevant CYO choice is slot C (station 11);
`high_benefit` is CYO-invariant. So the complete surface is the 12 shipped files
(4 combos × [high_benefit + all_benefited-default + all_benefited-c11-tech], with
high_benefit counted once per combo). Slots A/B are the s2/s6 combos; slot D has no
effect. If the income *direction* or vertiport set changes, everything regenerates
from these three scripts with no solver edits.
