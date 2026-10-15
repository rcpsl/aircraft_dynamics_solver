# Handoff: wiring dB_target_sweeps data into the dashboard

**Purpose of this file**: the exact file list and prompt to give a fresh
Claude session that will wire the dataset into a fairness dashboard, similar
to `fairness-dashboard-v2.html`. Give that session this file (or paste its
contents) plus repo access — it's self-contained.

---

## Files to hand to the other session

**Must read, in this order** (all under `dB_target_sweeps/`):

| # | File | Why |
|---|---|---|
| 1 | `DASHBOARD_DATA_INTEGRATION.md` | Base model — communities, station numbering, CYO/combo structure, Communities/People toggle, findings #1-8 |
| 2 | `full_routes/DASHBOARD_DATA_INTEGRATION_V2.md` | What's new since #1: routing paths, the 5th (proportional) domain, current file-completion status, the wiring work list |
| 3 | `full_routes/REPORT.md` | Routing-table file format spec, tied-optimal caveat, **live status of the 5 still-missing files** (§4 — check before use) |
| 4 | `full_routes/proportional/REPORT.md` | The 5th domain in full: benefit-map rule, findings F1-F7, the station-11 CYO lever |

**Reference data / tools to point at** (don't need full reads, just needs
access):

| Path | What |
|---|---|
| `Sample Communities.xlsx` | Canonical community/station source data |
| `../uam-config_finalized.json` | Solver config (adjacency, baselines, multipliers) |
| `build_dashboard_data.py` | Existing build script — the thing to extend |
| `fairness-dashboard-v2.html` | Existing dashboard prototype — the thing to extend or supersede |
| `full_routes/` (all combo subfolders) | Primary data source — routing-enriched CSVs, 115/120 + 12/12 proportional |
| `equal_allocation/`, `sufficientarian/`, `utilitarian/`, `prioritarian/step3_baseline_sweep/` | Fallback source for any of the 5 files still missing from `full_routes/` |

**Optional background** (domain methodology, cite only if the other session
asks "why" about a specific number): `equal_allocation/README.md`,
`sufficientarian/REPORT.md`, `utilitarian/utilitarian_data_report.md`,
`prioritarian/REPORT.md`.

---

## Prompt for the other session

```
You're wiring the UAM noise-fairness dataset in dB_target_sweeps/ into a
fairness dashboard, extending the existing fairness-dashboard-v2.html /
build_dashboard_data.py pipeline (or superseding it with a v3, your call).

Read these four files first, in order — they're the complete spec, don't
skip any:
1. dB_target_sweeps/DASHBOARD_DATA_INTEGRATION.md
2. dB_target_sweeps/full_routes/DASHBOARD_DATA_INTEGRATION_V2.md
3. dB_target_sweeps/full_routes/REPORT.md
4. dB_target_sweeps/full_routes/proportional/REPORT.md

Then look at dB_target_sweeps/build_dashboard_data.py and
dB_target_sweeps/fairness-dashboard-v2.html to see the current state.

Goal:
- Repoint the data pipeline at dB_target_sweeps/full_routes/ (routing-
  enriched, confirmed parser-compatible per doc #3 §4) instead of the
  original flat CSV folders, falling back to the originals only for
  whichever files doc #3 §4 currently lists as missing — check that section
  live, don't hardcode a file count.
- Add the proportional domain as a genuinely new principle/card (not a
  variant of an existing one) — combo x mode(high_benefit/all_benefited) x
  CYO-slot-C(default/tech) per doc #4 §5's lookup table.
- Use the new per-aircraft routing table to render actual flight paths on
  the station grid (a capability that didn't exist before this data) —
  doc #2 §6.2 has the concrete idea (timeline scrubber / animated
  playback).
- Add the proportional benefit choropleth as a second map next to the noise
  map, and make the station-11 CYO-slot-C lever (doc #4 §7, "F7") a live,
  prominent interactive toggle — it's flagged as the dataset's best teaching
  moment.
- Disclose in-product, not just in code comments: the tied-optimal caveat
  (doc #3 §3, doc #2 §5.1 — a full_routes number may legitimately differ
  from the historical value baked into dashboard_data.json), the
  proportional benefit rule's income-direction value judgment (doc #4 §6
  finding F6), and the service-level tradeoffs each domain report
  documents (fleet cuts, demand-fulfilled %).
- Precompute into a JSON blob like the existing build script does — don't
  fetch CSVs at runtime (file:// fetch() fails in Chrome, per doc #1's
  existing recommendation).
- Keep the output a single self-contained HTML file, no CDN dependencies.

Work incrementally: get the repointed existing 4 domains rendering
correctly first (should be a near-drop-in given confirmed parser
compatibility), then add the proportional domain and the two new
visualizations. Flag anything in the four docs above that seems wrong or
outdated rather than silently working around it.
```
