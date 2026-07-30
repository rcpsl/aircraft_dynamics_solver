# Wiring the dB_target_sweeps dataset into the new Fairness Dashboard

**Audience**: the Claude Code session implementing the new (real-data) fairness dashboard.
**Status of this folder**: `fairness-dashboard-v1.html` is an OUTDATED mock — its community
list, ambient dB values (50/60/66–68), grid arrangement, prioritarian 10/5/1 scoring, and all
scenario numbers are invented. Do not copy data or assumptions from it; reuse only its UX
skeleton (steps → communities / measurement / fairness / compare, side panel, pin-to-compare)
if useful. The canonical base model is **`Sample Communities.xlsx`** plus the four data
domains described below. A working v2 prototype built exactly per this report exists as
`fairness-dashboard-v2.html` (data inlined by `build_dashboard_data.py`) — extend it or
rebuild from it.

---

## 1. The base model (`Sample Communities.xlsx`)

Three sheets:

1. **Communities** — the 12 fixed communities (#1–12), each with: External Name, narrative,
   internal Austin equivalent, Population (High/Medium/Low), Income, Race, Life stage,
   Housing, Transport, Employment, Land use, Noise (Quiet/Moderate/Loud), `noise_db`
   (**45 / 55 / 65** — these replace the mock's 50/60/66–68 values), Landmarks.
2. **Dashboard Location** — a 4×4 grid placing the 12 fixed communities and 4
   "Create Your Own" (CYO) slots.
3. **Create Your Own Community Optio(ns)** — 8 pre-authored option communities (#13–20).
   Each CYO slot offers **exactly two** of them (an "OR" pair). This replaces the mock's
   free-form Admin form: participants don't invent arbitrary communities, they pick one of
   two pre-modeled options per slot.

### Station numbering = grid position (verified)

`uam-config_finalized.json` has `stationBaselines = [65,65,55,45,55,55,55,55,55,55,55,65,45,45,65,65]`.
Reading the Dashboard Location grid **row-major** (row 1 left→right = stations 1–4, row 2 =
5–8, etc.) reproduces this array **16 / 16 exactly** (every Loud=65, Moderate=55, Quiet=45
lands in the right place, with each CYO slot's *default* option matching too). So:

| St | Community (internal) | Base dB | Pop | St | Community (internal) | Base dB | Pop |
|----|----|----|----|----|----|----|----|
| 1 | Downtown | 65 | High | 9 | Gentrifying Neighborhood (E Cesar Chavez/Holly) | 55 | Medium |
| 2 | **CYO slot A** (see §2) | 65 default | — | 10 | University (UT) | 55 | High |
| 3 | Mixed Urban Community (Rundberg/N Lamar) | 55 | High | 11 | **CYO slot C** | 55 (both options) | — |
| 4 | Affluent Suburban (Westlake) | 45 | Medium | 12 | Underdeveloped Neighborhood (Del Valle) | 65 | Medium |
| 5 | Retail & Entertainment Center (Domain) | 55 | High | 13 | **CYO slot D** | 45 (both options) | — |
| 6 | **CYO slot B** (see §2 — placement caveat) | 55 default | — | 14 | Rural-Suburban Outskirts (Buda) | 45 | Medium |
| 7 | Popular Urban Residence (South Congress) | 55 | Medium | 15 | Industrial Center (Burleson Rd) | 65 | Low |
| 8 | Lower-Income Urban Neighborhood (Dove Springs) | 55 | High | 16 | Airport (ABIA) | 65 | Medium |

Zone rows in every CSV are 1-indexed and match this station numbering 1:1.

Noise-band coloring for the UI: **Loud ≥ 65, Moderate 55–64, Quiet < 55** (works with total
dB too, since baselines are exactly 45/55/65).

### ⚠ One deliberate deviation from the Excel grid (station 6 ↔ 8)

The Excel grid literally places *Lower-Income Urban Neighborhood* at position 6 and the
International/Exurban CYO slot at position 8. **The solver dataset, however, sweeps station
6's baseline (55↔45)** — which only makes sense as the International-District(55) vs
Exurban-Commuter-Town(45) choice — and station 8 is never varied. The dataset is immutable
(hundreds of solver-hours), so the dashboard must follow the data: **place CYO slot B at
station 6 and Dove Springs at station 8**, i.e. swap those two tiles relative to the Excel
sheet. Both default to 55 dB so nothing else shifts. Two consequences to disclose rather
than hide:

- The frozen people-weights (§4) give station 6 weight 10 ("High population"), which
  actually matches Dove Springs, not the Medium-population CYO options. This is consistent
  with the project's **deliberate simplification: choosing a CYO option never updates
  populations/weights in the solver data** — only the ambient dB changes. State this in the
  dashboard's fine print.
- The prioritarian protected-station lists (§3.4) were generated with station 6 = Dove
  Springs semantics. Since the prioritarian noise tables turned out identical across all
  groups anyway (§5.4), this does not change any displayed number — but derive the
  "PROTECTED" badges from community *attributes* (Income, Transport, Employment, Housing
  columns of whichever community currently occupies a tile), not from the hardcoded station
  lists.

If the team later says the Excel placement is authoritative, the alternative reading is
"s6-45 ⇒ what if Dove Springs were quiet" — but then no CYO choice has any dB effect for
slot B and the 4-combo structure loses its meaning. Recommend confirming with Whit/Yasser;
build with the swap in the meantime.

## 2. The four CYO slots and the 4-combo structure

The 8 option communities pair up as:

| Slot (station) | Option 1 | Option 2 | dB effect |
|---|---|---|---|
| **A (st 2)** | New High-Density Development (E Riverside) — **Loud 65**, High pop, renters | Historic Black Neighborhood (Rosewood) — **Moderate 55**, Medium pop | **65 vs 55 → the `s2-65` / `s2-55` axis** |
| **B (st 6)** | International District (N Lamar) — **Moderate 55**, Medium pop | Exurban Commuter Town (Manor) — **Quiet 45**, Medium pop, transit desert | **55 vs 45 → the `s6-55` / `s6-45` axis** |
| C (st 11) | Working-Class Homeowner Nbhd (Montopolis) — Moderate 55 | Suburban Tech Campus (Parmer Ln) — Moderate 55 | none (both 55) — same data either way |
| D (st 13) | Retirement Community (Sun City) — Quiet 45 | Quiet Rural Low-Income (Hornsby Bend) — Quiet 45 | none (both 45) — same data either way |

Every data domain is collected at the **2 × 2 = 4 combos** of the A and B choices, in folders
named `s2-65_s6-55` (the config default: New High-Density + International District),
`s2-65_s6-45`, `s2-55_s6-55`, `s2-55_s6-45`. **This is the entire "choose your own
community" data surface**: slots C and D change the tile's story/attributes but reuse the
same solve (that's by design, and honest to display because their ambient dB — the only
thing the solver sees — is identical between their options). Population differences between
options (e.g. New High-Density is High-pop, Historic Black is Medium) are **deliberately not
reflected** in the solver runs; say so in the UI rather than pretending otherwise.

So: the dashboard's combo key is `s2-{65|55}_s6-{55|45}`, derived purely from the slot A and
slot B picks. Default when the participant hasn't chosen = `s2-65_s6-55`.

## 3. The four fairness domains → files

All CSVs share the per-zone table format (matches `frontend/src/utils.js:buildZoneSummaryCSV`):

```
Zone,Avg Added dB,Avg Total dB,Peak Added dB,Peak Total dB,Avg Aircraft,Peak Aircraft
```

"Added" = increase above that station's ambient; "Total" = ambient + added; Aircraft columns
are **multiplier-weighted traffic units, not physical aircraft** (label them "traffic", never
"aircraft count" — Peak Aircraft 29 happens with only 14 physical aircraft). Preamble lines
vary by domain (see each). Base scenario everywhere: 14 aircraft shuttling only between
stations 1 and 16, `dbPerCraft=55`, multipliers `[2,5,5,5,5,5,5,5,5,2,5,3,2,2]` (Σ=56).

### 3.1 Equal — `equal_allocation/<combo>/<mode>/`

- `mode` ∈ `community_equal` (plain feasibility under disparity cap U) | `people_equal`
  (utilitarian objective + population station-weights) → **this is the Communities/People
  toggle** for the Equal card.
- Files: `{3,8,18}dB_{avg,peak}.csv` → the Equal sentence's "within ___ dB" blank (3/8/18,
  matching the EPA reaction anchors) × the avg/peak measurement toggle.
- Preamble: `Time Steps (T)`, `Flights (N)`, `Total Traffic (sum of aircraft multipliers)`.
  **N and Traffic vary per file** (4–14 flights, 4–56 traffic) — surface this (§5.2).
- `picks_summary.csv` per folder gives the chosen search point and achieved value; the
  achieved value (e.g. avg 2.51 for the 3 dB target) is worth showing as "achieved: X dB".
- Caveats to disclose: `3dB_peak` never satisfies <3 dB (physical floor 3.0103, §5.1; the
  `s2-65_s6-45` files sit at 4.77); avg-18dB equals avg-8dB in 3 of 4 combos (ceiling —
  show "same routing as 8 dB" rather than a mysterious duplicate).

### 3.2 Utilitarian — `utilitarian/{utilitarian,utilitarian_peak}/<combo>/`

- Files: `no_weight.csv` | `weighted.csv` → **Communities/People toggle** (weighted =
  people). No target knob — the utilitarian card has no blank to fill.
- `utilitarian/` (solved at D=12 to force route diversity) backs the **"total noise over
  time" (avg)** measurement; `utilitarian_peak/` (D minimized per combo, see `d_min.txt`)
  backs the **"loudest moment" (peak)** measurement.
- No preamble lines; N=14 always.
- `d_min.txt`: `D_feasibility_min` (8.0 for s6-55 combos, 10.5 for s6-45) vs
  `D_used_for_final_csvs` (12.0 / 13.5, the tightest that reliably optimizes) — good
  footnote material: "a schedule exists down to X dB peak, but couldn't be reliably
  optimized below Y".
- Do **not** compare peak values across combos as if one cap applied — D differs per combo.

### 3.3 Sufficientarian — `sufficientarian/<combo>/{unweighted,weighted}/`

- `unweighted` | `weighted` → **Communities/People toggle** (weighted = people).
- Files: `D8.csv`, `D18.csv`, `Dmin_3.02.csv` → the sufficientarian sentence's cap blank.
  Offer caps **"8 dB over today" / "18 dB over today" / "the absolute minimum (3.02 dB)"**.
  Drop the mock's "55 dB total" and free-number custom cap — no data. If a custom-cap
  input is kept for discussion, it must be presented as "nearest available data" snapping
  to {3.02, 8, 18}.
- D is a cap on **Peak Added dB** (never exceeded by construction). For the avg/peak
  measurement toggle, use the same file and switch displayed columns.
- `#`-prefixed preamble carries `variant`, `N`, `T_used` etc. `picks_summary.csv` +
  `min_d_summary.csv` at domain root summarize fleet variants: D8 needed multipliers
  stripped to 1 (N=14, traffic 14), D18 ran the full weighted fleet (traffic 56), Dmin
  needed the fleet cut to 7 (unweighted) or 4 (weighted). Surface as service level (§5.2).
- D=3.00 is **infeasible** (proved by graph connectivity, `unsat_record.csv` is the failed
  attempt log) — the 3.02 floor is a headline teaching moment (§5.1).

### 3.4 Prioritarian — `prioritarian/step3_baseline_sweep/<combo>/{community,people}/`

- Files: `low_income.csv`, `transit_desert.csv`, `few_jobs.csv`, `mostly_renters.csv` — four
  equity lenses (protected station sets {6,12}, {6,12,15}, {4,6,12,14}, {1,3,5,10,15,16},
  derived from the Excel attribute columns under the pre-swap layout). Replace the mock's
  eight 10/5/1 dimensions with **these four data-backed lenses only**.
- **`community/`**: prioritarian objective alone. Preamble `Time Steps (T),5` (soft-T,
  `T_max=5`), plus `protectedNoise`, `protectedStations`, `D`, `U`. N=14, traffic 56 —
  full fleet, no service-level cost.
- **`people/`**: prioritarian + `optimizeUtilitarian` combined, with `stationTransitWeights`
  set to the exact same population-weight vector used identically by equal_allocation,
  sufficientarian, and utilitarian (`{1:10, 2:5, 3:10, ...}` — see §4). This was **missing
  entirely** until it was generated to close this gap — prioritarian was the only domain
  without a people-counting variant. N=7 (not 14) — combining the two objectives at N=14
  reliably timed out (measured: 246.2s, over the 240s Z3 budget) even with the same
  `T_max=5, D=18` that works for `community/`; N=7 solves the worst combo's 4 lenses in
  48–109s each, comfortably inside budget. Disclose the fleet cut in the UI (`ds.meta.N`).
- `step1_prioritarian_only/` and `step2_prioritarian_utilitarian/` still use the *original*
  hard-T config (`T=4`, byte-identical across lenses — see below) and are kept only as a
  historical record; `step3_baseline_sweep/` covers all 4 combos with the fixed config and
  is the one the dashboard reads.
- **This data was regenerated after an initial hard-T collection produced identical results
  across all four lenses** (a real, separately-documented finding — every 1↔16 route was
  forced onto the single shortest path `1→6→11→16` at `T=T_min=4`, so no protection choice
  could change anything). The fix — confirmed empirically, see `prioritarian/REPORT.md` §5b —
  is `hardT=false, T_max=5, D=18` (down from 40) instead of the originally-attempted
  `T_max=7` (which reliably timed out even after tightening D alone). `T_max=5` opens just
  the 12 alternate length-4 routes, enough for the objective to have a real choice, while
  staying inside the 240s Z3 budget with the full N=14 fleet (8–53s per solve, all 16
  combo×lens solves succeeded). **The four lenses now produce genuinely different zone
  tables** — 5 to 10 of 16 zones differ between any pair, per combo. Present this as the
  dashboard's real prioritarian finding (§5.4 below has been updated accordingly) rather than
  the old "protection changes nothing" framing.

## 4. The Communities / People toggle — what it really is

"People" mode = the solver was given per-station transit weights (1-indexed)
`{1:10, 2:5, 3:10, 4:5, 5:10, 6:10, 7:5, 8:5, 9:5, 10:10, 11:5, 12:5, 13:5, 14:5, 15:1, 16:5}`
≈ population coded High=10 / Medium=5 / Low=1 (matches the Excel populations at 15 of 16
stations; station 13 is 5 where its options are Low-pop — a known wart, and the weights are
frozen regardless of CYO choices). Routing through heavy stations costs more, so traffic is
pushed away from where the most people live. "Communities" mode = unweighted (every zone
counts once). The weights never change feasibility, only which feasible routing is preferred.

Per domain: `community_equal`/`people_equal`, `no_weight`/`weighted`, `unweighted`/`weighted`,
`community`/`people` (prioritarian — added later; runs a smaller 7-aircraft fleet since the
combined prioritarian+utilitarian objective isn't tractable at N=14 within the solve budget).

## 5. Findings the dashboard should actively show

These came out of data collection and are exactly the kind of insight the workshop wants:

1. **The +3 dB floor is physics, not policy.** One aircraft (55 dB) over a 55 dB-ambient
   station adds exactly 10·log₁₀(2) = 3.0103 dB. Every 1↔16 route must cross a 55 dB bridge
   station (the "quiet-station set" {1,2,12,15,16} is disconnected in the adjacency graph),
   so **no amount of routing gets any scenario strictly under +3 dB** — a cap of 3 is
   UNSAT, and the "3 dB" equal/sufficientarian options bottom out at 3.01–3.02 (or 4.77 for
   equal-peak in `s2-65_s6-45`). Show this as an explicit "why can't we do better?" callout,
   not an error.
2. **Strict fairness costs service.** Hitting tight targets required shrinking the fleet:
   equal-3dB picks run 4–7 flights instead of 14 (traffic 4–14 vs 56); sufficientarian
   Dmin runs N=7/N=4; D8 keeps 14 aircraft but strips multipliers (traffic 14). Add a
   **service-level indicator** (e.g. "flights operated: 7 of 14 · traffic 12.5% of demand")
   to every scenario — the fairness↔service tradeoff is the workshop's core tension and the
   data encodes it in the `Flights (N)` / `Total Traffic` / `variant` preambles.
3. **Stations 6 and 11 are structural bottlenecks.** They bridge the two halves of the
   graph; every scenario concentrates burden there. Tile-level data shows it; consider a
   persistent "corridor" marker on those tiles.
4. **Prioritarian protection now visibly reroutes traffic — in community mode.** An initial
   hard-T collection (`T=T_min=4`) found exactly one feasible route (`1→6→11→16`), so every
   protected-station choice produced byte-identical noise — a real finding about that config,
   kept as a discussion point about infrastructure constraints, but not the final dataset.
   Regenerating with `T_max=5, D=18` (still full N=14 fleet, 8–53s per solve — see
   `prioritarian/REPORT.md` §5b) opened enough alternate routing for the four equity lenses to
   genuinely diverge: 5–10 of 16 zones differ between any pair of lenses, per combo. Show the
   *comparison* between lenses (which zones gain/lose noise when the protected set changes) as
   the headline, not a static single map — that's the actual "does prioritizing X protect X"
   answer this domain was built to give.
5. **People-mode prioritarian differentiates lenses *less* — a real result, not a bug.**
   Generated to close prioritarian's missing people-counting variant (§3.4, §5d in the
   report), it needed a smaller N=7 fleet (combining prioritarian + utilitarian objectives at
   N=14 reliably times out). At N=7, `low_income`/`transit_desert`/`few_jobs` collapse onto
   **byte-identical routing** in every combo — only `mostly_renters` still differs (3/16
   zones). This isn't the old hard-T bug (soft-T route choice is available, and the same
   lenses *do* differentiate under community-mode's N=14); it's the smaller fleet leaving
   fewer distinct ways to trade off the combined objective. Community vs. people mode for the
   *same* lens still differs substantially (4–8/16 zones) — disclose this nuance rather than
   hiding it: switching between those three lenses under "people" counting will look
   unchanged, and that's correct.
6. **The quiet-community paradox.** Choosing the quiet Exurban option (s6-45) makes that
   community's *perceived increase* larger, not smaller — same aircraft over 45 dB ambient
   reads +12.24 avg / +24.6 peak added dB (vs +7.3 at 55 dB ambient), because there's less
   masking noise. The s6-45 combos are also the hardest to solve (higher feasible-D floors:
   10.5 vs 8.0). Surface when the participant picks Exurban: "quiet places feel new noise
   the most."
7. **People-weighting redistributes averages, not peaks.** E.g. utilitarian s2-65_s6-55:
   weighted mode cuts station 6's average traffic 7.29→4.71 by detouring through zones
   2/7/12, but the worst instant stays 11.76 dB. Good side-by-side for the
   Communities→People switch: "the average person hears less; the worst moment is unchanged."
8. **EPA anchors line up with the targets by design**: +3 dB ≈ no community reaction,
   +8 ≈ sporadic complaints, +18 ≈ widespread complaints. Keep the mock's EPA chip; drive it
   from the real max Added dB (use Peak or Avg per the active measurement).

## 6. Control-state → file lookup (the whole wiring in one table)

State: `combo` (from slots A/B), `mode` ∈ {community, people}, `metric` ∈ {avg, peak},
`principle` + its knob.

| Principle | Knob | File |
|---|---|---|
| Equal | target T ∈ {3,8,18} | `equal_allocation/<combo>/{community_equal\|people_equal}/<T>dB_<metric>.csv` |
| Utilitarian | — | `utilitarian/{utilitarian if avg \| utilitarian_peak if peak}/<combo>/{no_weight\|weighted}.csv` |
| Sufficientarian | cap ∈ {3.02, 8, 18} | `sufficientarian/<combo>/{unweighted\|weighted}/{Dmin_3.02\|D8\|D18}.csv` (metric switches displayed columns only) |
| Prioritarian | lens ∈ {low_income, transit_desert, few_jobs, mostly_renters} | `prioritarian/step3_baseline_sweep/<combo>/{community\|people}/<lens>.csv` (metric switches columns only; `people` uses a 7-aircraft fleet — disclose) |

Display columns: metric=avg → `Avg Added dB` / `Avg Total dB`; metric=peak → `Peak Added dB`
/ `Peak Total dB`; the view toggle (increase vs. new level) picks Added vs Total. Never
recompute Total as base+Added yourself — read the CSV's Total column (it already reflects
the combo's baseline overrides at stations 2 and 6).

**Recommended loading strategy**: don't fetch 104 CSVs at runtime (the tool is opened as a
local file; `fetch()` on `file://` fails in Chrome). Precompute once into an inlined JSON
blob — `build_dashboard_data.py` in this folder does exactly that (run
`python build_dashboard_data.py` → regenerates `dashboard_data.json` and can re-inject it
into the HTML). Keys: `data[principle][combo][mode][metric][knob]` → `{meta:{T,N,traffic,
note}, zones:[16 × {aa,at,pa,pt,ac,pc}]}` plus a `communities` block carrying everything
from the Excel sheets (names, narratives, attributes, CYO pairs).

## 7. Suggested dashboard changes vs. the v1 mock

1. **Step 1 becomes the "choose your own community" step**: the four slots are two-option
   pickers (card-flip or A/B buttons showing each option's full profile), not an Admin form.
   Choosing at slots A/B visibly switches the active combo ("your choices changed the noise
   baseline map"); choosing at C/D changes only the tile's identity — say so on screen
   ("same noise footprint either way — that's deliberate").
2. **Kill all mock generators** (`priorScenario`, `suffCustomScenario`, `+2 dB peak fudge`,
   invented `SCENARIOS`) — every number now comes from the blob. Where the mock had a
   `datastate` warning box, put the real per-scenario caveat (achieved value, fleet cut,
   "identical to 8 dB target", "floor is 3.01", etc.).
3. **Add the service-level strip** (finding 2): flights, traffic %, T — pinned next to the
   EPA chip, and included in Compare cards so "fairer but 4 flights" vs "louder but full
   service" is visible side by side.
4. **Prioritarian card redesign** (finding 4): four lens buttons; map renders real,
   lens-differentiated data; an explainer panel highlights which zones changed versus another
   lens (the comparison is the point, not just the static map). Badges from attributes of
   currently-placed communities.
5. **Sufficientarian custom cap** → three data-backed caps + the impossibility explainer
   for anything ≤3.
6. **Compare cards** keep the 4×4 mini-grid but add the service strip and achieved-max
   chips; pins must store `(principle, knob, combo, mode, metric)` so re-render is exact.
7. Show **Total dB** as the default map view for absolute mode with band recolor when a
   tile crosses 55/65 (bands only ever move upward here), and label Added-dB view "+X dB
   above today".
8. Aircraft columns → label "traffic units (weighted)"; optionally show avg/peak traffic in
   the side panel per zone.
9. Keep the mock's excellent side-panel narrative content, but source every field from the
   Excel (the mock's `amb` values and some categories are stale — e.g. Airport income is
   Low in Excel, mock had it right, but Downtown race is Mixed in Excel vs mock Mixed ✓;
   regenerate rather than hand-copy).

## 8. Gaps / to confirm with the team

- Station 6↔8 placement (see §1 caveat) — data forces the swap; confirm intent.
- Prioritarian people-mode and soft-T rerouting data don't exist (solver-tractability
  limit); if the team fixes `optimize_objectives` scoping (`wdB_by_t` built for all 16
  stations regardless of protected-set size), a soft-T prioritarian re-collection would
  finally differentiate the four lenses.
- Equal-peak-3dB for `s2-65_s6-45` is "closest found" (4.77), not "closest possible"
  (3.01 likely exists with a denser search) — treat as provisional.
- No data for: absolute-dB sufficientarian caps, custom caps, participant-invented
  communities outside the 8 predefined options, or population changes from CYO choices.
  The dashboard should visibly mark these as "not modeled" rather than silently absorb them.
