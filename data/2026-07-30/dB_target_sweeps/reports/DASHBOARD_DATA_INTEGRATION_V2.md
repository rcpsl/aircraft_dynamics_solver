# Dashboard Data Integration V2 — full_routes/ + the proportional domain

**Audience**: the chat session that wires this data into the fairness
dashboard (v3, or whichever version follows `fairness-dashboard-v2.html`).

**Relationship to `../DASHBOARD_DATA_INTEGRATION.md` (the "v1" doc)**: that
document is still correct and not superseded on the base model — the 12
fixed communities, `Sample Communities.xlsx`, station numbering, the
station-6↔8 swap, the 4 CYO slots / 4-combo (`s2-{65|55}_s6-{55|45}`)
structure, the Communities/People toggle, and its 8 numbered findings (§5 in
that doc) all still hold and are not repeated here. **What changed since
that doc was written**: (1) every one of its 4 domains now has a
routing-table-enriched twin in this folder (`full_routes/`), and (2) a fifth
fairness domain — **proportional** (benefit-follows-burden) — was added by a
separate session and has never been described in the v1 doc at all. This
document covers only what's new; read the v1 doc first for everything else.

---

## 1. What's new

1. **Per-aircraft routing paths.** Every domain's CSVs previously stored
   only aggregated per-station summaries. `full_routes/<combo>/<domain>/...`
   re-solves each scenario from its exact documented config and adds the
   actual `station-per-aircraft-per-timestep` table on top — see §4 for the
   format. This is the first time flight-path-on-map visualization is
   possible; the v1 doc's §7 "suggested dashboard changes" has no
   path-rendering item because the data didn't exist yet.
2. **A fifth fairness domain: proportional.** Alongside equal /
   utilitarian / sufficientarian / prioritarian, `proportional/` asks the
   solver to make noise *burden* follow the vertiport network's *benefit*
   (a deterministic income-based overlay) — see §3.5 and
   `full_routes/proportional/REPORT.md` in full.
3. **The dashboard is not wired to any of this yet.** `build_dashboard_data.py`
   still reads only the original flat files the v1 doc describes. Nothing
   needs to change for the dashboard to keep working today; §6 is the
   concrete work list for whoever picks up the wiring.

## 2. Current dataset completion status

**equal_allocation / sufficientarian / utilitarian / prioritarian
(`full_routes/<combo>/{equal_allocation,sufficientarian,utilitarian,utilitarian_peak,prioritarian}/`,
120 files total, 30/combo)**: **115/120, retries stopped (not abandoned —
paused with cause).** The 5 still missing are **not one uniform gap** — see
`full_routes/REPORT.md` §4 for full detail, summarized here:

- **4 files** (`s2-65_s6-45/utilitarian/weighted/result.csv`;
  `s2-55_s6-45/equal_allocation/people_equal/8dB_peak.csv`,
  `sufficientarian/weighted/D8.csv`, `utilitarian/weighted/result.csv`) hit a
  **real, still-unexplained Z3 tractability wall** — every attempt (420s,
  900s, 900s with a fixed random seed, 600s at a reduced `T_max`) failed at
  within ~1-2% of whatever time budget was given, meaning Z3 genuinely isn't
  converging regardless of clock time or search seed. A real fix needs
  `optimize_objectives` code changes, not more retries.
- **1 file** (`s2-65_s6-55/equal_allocation/people_equal/3dB_avg.csv`) has
  **no valid evidence either way** — its only retry attempts used a wrong
  fleet config (a debugging bug, since fixed) and so don't tell you anything
  real about its difficulty. `retry_multiseed.py` has the corrected config
  and is ready to run when someone wants to finish this one.

**Check `REPORT.md` §4 directly before building on this** — it's the source
of truth; don't assume this summary is still current by the time you read
it.

**proportional (`full_routes/<combo>/proportional/`, 12 files total, 3/combo)**:
**complete, 12/12** — `high_benefit.csv`, `all_benefited.csv`,
`all_benefited__c11-tech.csv` per combo. All 8 underlying solves (2 modes ×
4 combos; `high_benefit` is CYO-invariant so only counted once) came back
SAT with no phase-2 fallback. No known gaps in this domain.

**Grand total**: 132 target files (120 + 12) across the two most-recent
generation passes; treat any file the count above flags as absent from
`full_routes/` as "use the original (non-routing) file from the v1-described
folders instead" — the plain per-zone data for every scenario has existed
since before this folder, only the routing table is what's still catching up.

## 3. The complete data-set + report manifest

Everything the wiring session needs, in one place. Paths are relative to
`dB_target_sweeps/`.

### 3.1 Base model (unchanged from v1)

| File | What it is |
|---|---|
| `Sample Communities.xlsx` | Canonical community/station data — 3 sheets (Communities, Dashboard Location, CYO Options). See v1 doc §1. |
| `../uam-config_finalized.json` (repo root, referenced by both v1 doc and `full_routes/_solve_helpers.py`) | Solver config: adjacency, station baselines, aircraft multipliers, start/end positions. |

### 3.2 Reports — read in this order

| Report | Domain | Read for |
|---|---|---|
| `DASHBOARD_DATA_INTEGRATION.md` (v1, this folder's parent) | all | base model, station numbering, CYO/combo structure, Communities/People toggle semantics, control-state→file lookup for the original 4 domains, findings #1–8 |
| `equal_allocation/README.md` | equal | search methodology (U-sweep), the 3.0103dB physical floor, avg/peak definitions, tied-optimal caveat origin |
| `sufficientarian/REPORT.md` | sufficientarian | D-as-hard-cap semantics, D=3 infeasibility proof, fleet-shrink ladder |
| `utilitarian/utilitarian_data_report.md` | utilitarian + utilitarian_peak | why D=12 vs D=8/10.5, weighted-vs-unweighted route diversion findings |
| `prioritarian/REPORT.md` | prioritarian | the hard-T→soft-T fix (§5b) that made lenses actually differentiate, people-mode fleet cut rationale (§5d) |
| `full_routes/REPORT.md` | equal/sufficientarian/utilitarian/prioritarian, routing-enriched | file format, tied-optimal-reproduction caveat, **current missing-file list (§4 — check before use)** |
| `full_routes/proportional/REPORT.md` | proportional (new, 5th domain) | benefit-map rule, the two modes, the station-11 CYO lever (F7, its best interactive finding), all findings F1–F7 |
| `full_routes/DASHBOARD_DATA_INTEGRATION_V2.md` | all — this file | delta since v1, current file-completion status, wiring work list (§6) |

### 3.3 Data — canonical source per domain

**Recommendation: read from `full_routes/` for all five domains**, not the
original flat folders, once §2's completion count reaches 120/120 (or for
any individual file already present there). `full_routes/` files are
schema-supersets of the originals (§4 confirms `build_dashboard_data.py`'s
existing parser already reads them correctly, unchanged) — same per-zone
table, plus the routing block, plus explicit demand-fulfilled figures. Any
file still missing from `full_routes/` can be read from the corresponding
original folder as a stopgap (same Zone-table numbers, just no routing
block).

| Domain | full_routes path | Original (fallback / always-complete) path |
|---|---|---|
| Equal | `full_routes/<combo>/equal_allocation/{community_equal\|people_equal}/<T>dB_<metric>.csv` | `equal_allocation/<combo>/{community_equal\|people_equal}/<T>dB_<metric>.csv` |
| Utilitarian | `full_routes/<combo>/{utilitarian\|utilitarian_peak}/{no_weight\|weighted}/result.csv` | `utilitarian/{utilitarian\|utilitarian_peak}/<combo>/{no_weight\|weighted}.csv` |
| Sufficientarian | `full_routes/<combo>/sufficientarian/{unweighted\|weighted}/{D8\|D18\|Dmin_3.02}.csv` | `sufficientarian/<combo>/{unweighted\|weighted}/{D8\|D18\|Dmin_3.02}.csv` |
| Prioritarian | `full_routes/<combo>/prioritarian/{community\|people}/<lens>.csv` | `prioritarian/step3_baseline_sweep/<combo>/{community\|people}/<lens>.csv` |
| Proportional (new) | `full_routes/<combo>/proportional/{high_benefit\|all_benefited\|all_benefited__c11-tech}.csv` | **none — this domain only exists in `full_routes/`, there is no pre-routing original** |

### 3.4 Reusable scripts (all in `full_routes/`)

| Script | Purpose |
|---|---|
| `_solve_helpers.py` | shared solve+format logic, config parsers, fleet-subsample helper |
| `run_combo.py <combo>` | regenerates all 30 (equal/sufficientarian/utilitarian/prioritarian) files for one combo; safe to re-run, skips existing files |
| `retry_extended_timeout.py <combo> [timeout_ms]` | same, with a configurable (longer) Z3 timeout for that process only |
| `extract_station_income.py` | station→income lookup from the xlsx, for the proportional domain |
| `proportional_benefit.py` | deterministic benefit-map + station-set computation |
| `run_proportional.py [combo]` | generates the 12 proportional CSVs |
| `analyze_proportional.py` | prints the proportional domain's F1/F2 headline numbers from the generated CSVs |

## 4. File format — confirmed compatible with the existing dashboard parser

`full_routes/` CSVs add a `#`-prefixed metadata preamble, a `Time Steps (T),<T>`
line, then a new **routing block**, then the *exact same* Zone table schema
every other `dB_target_sweeps/` CSV uses:

```
# domain,<...>
# combo,<...>
# mode,<...>
# <domain-specific params: D,U,hardT,T_max,...>
# N,<N>
# aircraftMultipliers,<[...]>
# totalTraffic,<sum>
# maxTraffic,56
# demandFulfilledPct,<pct>
Time Steps (T),<T>

Routing (station per aircraft per timestep):
Aircraft,Multiplier,Start,End,T0,T1,...,T<T-1>
1,<mult>,<start>,<end>,<station@t0>,...

Zone,Avg Added dB,Avg Total dB,Peak Added dB,Peak Total dB,Avg Aircraft,Peak Aircraft
Zone 1,...
...
Zone 16,...
```

Proportional's files append 4 more zone-table columns
(`Benefit,Tier,Income,Demand Served` — see `proportional/REPORT.md` §4).

**Verified, not assumed**: `build_dashboard_data.py`'s existing
`parse_zone_csv()` was tested directly against a `full_routes/` file and
parsed it correctly with zero code changes — it silently skips any row it
doesn't recognize (the routing block, the aircraft rows), so the new
preamble lines and routing table are transparent to it:

```
parse_zone_csv('full_routes/s2-55_s6-55/equal_allocation/people_equal/3dB_peak.csv')
→ {"T": 7, "N": 7, "traffic": 7, "variant": "N7_mult1"}, 16 zones parsed correctly
```

No parser rewrite is required to switch data sources; only the file paths
in `build_dashboard_data.py`'s domain loop need to change (§6.1), plus new
logic to read and expose the routing block and proportional's 4 extra
columns, which the current parser drops on the floor since it only extracts
`aa/at/pa/pt/ac/pc`.

## 5. Known caveats to disclose in the dashboard (new, beyond v1's §5)

1. **The routing-enriched re-solve doesn't always reproduce the original
   published zone-table numbers exactly**, even for files that solved
   without a timeout. Confirmed directly on 2 files: `equal_allocation`'s
   `people_equal/3dB_peak.csv` (s2-55_s6-55) matched its target metric
   exactly but had a different per-zone distribution; `utilitarian_peak`'s
   `weighted/result.csv` (same combo) differed on both average and peak
   values at several zones despite an identical solver config. This is Z3
   landing on a different **tied-optimal** solution — multiple structurally
   different routings score equally well on the actual minimized objective
   (transit cost, not noise, for utilitarian). `full_routes/REPORT.md` §3
   only documented this for `equal_allocation`; it now provably also
   affects `utilitarian`. **If the dashboard shows exact historical values
   as ground truth anywhere, note that a `full_routes/`-sourced number may
   legitimately differ from the number currently baked into
   `dashboard_data.json`** (which reads the un-touched original files).
2. **A handful of files may still be missing** — see §2. Anything absent
   from `full_routes/` has a complete non-routing original to fall back on
   (§3.3); the *dataset* is not actually incomplete, only the *routing
   table* for a few cells is pending.
3. **Proportional's benefit map is a value judgment, not a neutral
   default** — it allocates benefit *proportional to income* (the opposite
   direction from the prioritarian lens's protection of low-income tiles).
   `proportional/REPORT.md` §6 finding F6 says this should be disclosed
   explicitly in the UI, and §8 flags it as a one-line, discussable code
   change (`_ADD_BY_INCOME` in `proportional_benefit.py`) if the team wants
   the opposite direction instead.
4. **Proportional's two modes aren't cross-comparable on absolute dB** —
   `high_benefit` runs N=14, `all_benefited` needs an N=7 fleet cut to stay
   inside the solver's time budget. Compare *which tiles bear the burden*
   relative to the benefit map within a mode, not raw dB across modes
   (`proportional/REPORT.md` §8).

## 6. Work list for the wiring session

### 6.1 Minimum viable: keep today's dashboard working, just repoint it

- In `build_dashboard_data.py`, change each domain's file path to the
  `full_routes/` location (§3.3 table) once §2's completion count is
  acceptable. No parser change needed (§4).
- Add a `proportional` block to the `data[principle][combo][...]` structure
  `build_dashboard_data.py` produces — this is a genuinely new principle,
  not a variant of an existing one, so it needs its own card/toggle
  wiring, not just a new file path. Control-state: `combo` (as usual) ×
  `mode` ∈ {high_benefit, all_benefited} × (for all_benefited only)
  `cyoSlotC` ∈ {default, tech} — see `proportional/REPORT.md` §5 for the
  full lookup table.

### 6.2 New capability the data now supports

- **Render the actual flight paths** on the station grid using the new
  routing block (station-per-aircraft-per-timestep) — a timeline scrubber
  or animated playback becomes possible for the first time. This is new
  relative to every "suggested changes" item in the v1 doc.
- **Proportional's benefit choropleth** (`Benefit`/`Tier`/`Income` columns)
  as a second map next to the noise map, per `proportional/REPORT.md` §5 —
  "here's who benefits / here's who bears the noise" is the domain's
  intended visual.
- **The station-11 CYO-slot-C lever** (`proportional/REPORT.md` §7, "F7") is
  flagged by that report as the single best interactive teaching moment in
  the whole dataset — a live toggle that visibly completes or breaks
  "burden follows benefit" depending on one community pick. Worth
  prioritizing in the UI design.

### 6.3 Before treating this as done

- Re-check `full_routes/REPORT.md` §4 for the live missing-file count — do
  not hardcode "120/120" or "132/132" into any UI copy without verifying.
- Decide (and disclose in-product, per §5.1) whether the dashboard should
  show `full_routes/`'s possibly-different tied-optimal numbers or keep
  showing the original historical values it ships with today. This is a
  judgment call for whoever does the wiring, not something this document
  resolves.
