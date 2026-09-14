# Draft report: session 4, 2026-09-14

## Bottom line

| item | result |
|---|---|
| `tex/main.pdf` | **6 pages** including references (limit 8). Log: `Output written on main.xdv (6 pages)`. Built with Tectonic 0.15.0 (XeTeX engine), body in T1 Times; no overfull boxes, 0 unresolved references |
| `check_tex.py` | clean (`no structural problems found`) |
| `verify_sec4.py` | **31 checks, 31 passed**, 0 failed, 0 skipped |
| data | `harness/results/fleet_main_metrics.json`, setup `D6_protA`, ladder N = 6, 8, 14, 16, 22, 24; all 36 cells proven optimal in 4/4 aircraft orderings |
| compile time | 66 s for a full build (bibtex and TeX reruns); 10.4 s for one TeX pass including bibtex and PDF output; first build 120 s (package downloads) |
| tag | `submission-candidate` on the final commit |

Thesis, as the abstract, §I and §V state it: the five principles, encoded as constraints and
objectives in one routing solver, respond differently to fleet size in where they route,
how much they congest, what they cost in travel time and how much noise they add, and the
paper measures that response across N.

## What the paper rests on

* `FINDINGS.md` does not exist. The authority is `harness/NIGHT_REPORT.md`, `DECISIONS.md`
  and `CONTRADICTIONS.md`, including the 2026-09-14 addendum (Utilitarian's count
  objective is also attained by the baseline's routing).
* The one metrics file is `harness/results/fleet_main_metrics.json`, aggregated from
  `results/fleet_main.jsonl` (four OD-preserving orderings per cell). Setup `D6_protA`:
  D = 6 dB on every principle, protected set stations 4, 8 and 14, and Utilitarian and
  Proportional in count form. The figures (`export_plot_data.py`) and the text
  (`verify_sec4.py`) both read this file.
* The shipped-default ladder (`fleet_metrics.json`) appears once: one sentence in §III-C
  and one clause in §III-D. Those numbers are checked against that file, restricted to N ≤ 24.

## Instructions received mid-session, and how they were applied

1. **Ladder reported up to and including N = 24.** Every figure, table and number uses
   N ∈ {6, 8, 14, 16, 22, 24}. `routes_grid` rows are N = 8, 16, 24. `metric_vs_N`,
   `solve_time` and both tables stop at 24. Every sentence citing N = 30 or 32 is gone,
   and §IV-A states the range. `verify_sec4.py` loads only N ≤ 24. Its first check
   scans `sec4_results.tex` (and `main.tex`, §I, §III, §V) for any named fleet size and
   fails on one above 24; `sec4` currently has 69 fleet-size mentions, none above 24. The count includes range ends
   such as the 11 in "11–14", which the scanner reads conservatively.
   Because every cell to N = 24 is proven, the paper has no verified-feasible cells.
   Hollow markers and daggers are therefore never drawn, and the response table's
   "proven to" column became mean wall time at N = 24.
2. **Figures rebuilt in LaTeX.** `harness/export_plot_data.py` (new) writes the CSVs and
   generates the figure sources. The matplotlib PDFs are deleted from `tex/figs/`; see
   the mapping below.
3. **Rebuilt and re-checked**: 6 pages, `check_tex` clean, 31/31 checks.

## Page count per section (from the build)

Measured from the heading positions in the built PDF. A span includes whatever floats
LaTeX placed inside it: Figs. 2 and 3 (`figure*`) fall inside §IV-D's span, and Table III
falls inside §V's.

| section | starts | pages | budget |
|---|---|---|---|
| title + abstract | p1 | 0.28 | 0.2 |
| I Introduction | p1 col 1 | 0.49 | 0.8 |
| II Principles (with Table I, Prop. 1) | p1 col 2 | 0.45 | 0.8 |
| III Encoding and instance (with Fig. 1) | p2 col 1 | 1.10 | 1.2 |
| IV Results | p3 col 1 | 2.11 | 3.6 |
| &nbsp;&nbsp;IV-A setup | | 0.15 | 0.3 |
| &nbsp;&nbsp;IV-B routing, congestion | | 0.38 | 1.2 |
| &nbsp;&nbsp;IV-C travel time | | 0.49 | 0.7 |
| &nbsp;&nbsp;IV-D noise, capacity (+ Figs. 2, 3, Table II) | | 0.94 | 0.9 |
| &nbsp;&nbsp;IV-E solver (Fig. 4 beside it) | | 0.10 | 0.4 |
| &nbsp;&nbsp;IV-F summary | | 0.02 | 0.1 + table |
| V Conclusion (+ Table III) | p5 col 1 | 0.85 | 0.4 |
| References (18) | p6 col 1 | 0.71 | 0.8–1.0 |
| **total** | | **6.0** | 8.0 |

## Cuts made (12 pages → 6)

The session-3 draft built to 12 pages in Times; Latin Modern gave 13, which overstated
the length. Nothing on the brief's cut list beyond item 1 was needed.

* **§I**: four contributions (encoding, indifference test, non-neutral translation,
  tractability) became three measurements. The related-work subsection became one
  paragraph, and the closing "audit of our own" paragraph was removed.
* **§II**: five per-principle subsections (claim, assumption, domain note) and the
  two-distinctions discussion became one paragraph plus Table I. Proposition 1 is
  **kept**, because §IV-B cites it for Equal ≡ Sufficientarian. It is restated as an
  equivalence (converse under N < M) and moved here from §IV.
* **§III**, removed:
  * the activity-flag equations (`eq:start`, `eq:move`, `eq:mv`, `eq:ha`, `eq:ac`)
  * the pairwise-vs-max/min benchmark (`tables/pairwise.tex` and two paragraphs)
  * the per-principle encoding subsections
  * the benefit-measure discussion
  * normalisation and the weighted-scheme history
  * "when the clock runs out"
  * the rounding-concavity note

  The `table*` `tables/mapping.tex` was replaced by Table I.
* **§IV**: `tables/fleet_main.tex` was dropped; its numbers are in Fig. 3 and the text.
  The generated `tables/response.tex` was replaced by the hand-written Table III, which is
  asserted cell by cell. All N = 30/32 material was removed by instruction.
* **§V**: five "lessons" paragraphs (including the correction narrative and the 70×
  discussion) became four paragraphs.
* **References**: 24 entries became 18 cited. No longer cited: `austinnoise`, `crisp2003`,
  `harsanyi1955`, `kim2022indoor`, `moulin2003fair`, `walsh2020fairdivision`.
* **Brief's cut list items 2–6**: not applied. Proposition 1 stays (it is cited), §IV-E
  keeps its figure, `capacity.tex` stays, and `routes_grid` has three rows by instruction,
  not by cut.

## `\ref` audit

Labels from the brief:

| label | action | where it lands now |
|---|---|---|
| `sec:mismatch` | **deleted** | the Equal/Sufficientarian claim is Proposition 1 (`prop:equiv`, §II), cited in §IV-B |
| `sec:degeneracy` | **deleted** | the routing experiment is `sec:routing` (§IV-B) |
| `prop:collapse` | **renamed** `prop:equiv` | Proposition 1, restated as an equivalence; cited in §IV-B |
| `eq:capclosed` | kept, **moved** | now defined in §III-B where the cap is introduced (it used to live in §IV); cited in §III-B, Fig. 1 caption, §IV-D (twice), Table II caption |
| `sec:concavity` | **deleted** | the capacity argument is `eq:capclosed` plus §IV-D (`sec:noise`) |
| `sec:tractability` | kept | §IV-E; cited from §I contribution 3 |
| `sec:setup` | kept as a label | no longer cross-referenced; §II and §IV-A point to `sec:instance` |
| `sec:results` | kept as a label | not referenced |

Every reference in the built source, each read once against its target:

| ref | from | claim promised | lands on |
|---|---|---|---|
| `sec:routing` | §I, §III-C | routing/congestion vs N; "cap runs at full capacity at N=16" | §IV-B, which states utilisation 1.00 from N = 14 |
| `sec:travel`, `sec:noise` | §I | travel time; added noise | §IV-C; §IV-D |
| `sec:tractability` | §I | solve time, every cell proven | §IV-E |
| `tab:principles` | §II, §III-D, §IV-A | what the solver receives | Table I |
| `sec:encoding` | §II | notation | §III |
| `sec:instance` | §II, §IV-A | where P and π are defined; the operating point | §III-C |
| `eq:jtime` | Table I, §IV-C | arrival penalty | eq. (5) |
| `fig:capacity`, `eq:capclosed` | §III-B, §IV-D, Table II | capacity closed form | Fig. 1, eq. (3) |
| `prop:equiv` | §IV-B | Equal and Sufficientarian pose one problem | Proposition 1 |
| `fig:routes-grid`, `fig:metric-vs-N`, `fig:solve-time`, `tab:capacity`, `tab:response` | §IV | the figure or table named | Figs. 2–4, Tables II–III |

`tables/mapping.tex` is no longer `\input`, but it still contains `\ref{sec:mismatch}`.
It now carries a header comment saying so.

## Claim table: the abstract's findings

Row keys: `fleet|D6_protA|<condition>|<factor>|p0..p3`, with factor 0.25, 0.5, 0.75, 1.0,
1.25, 1.5 for N = 6, 8, 14, 16, 22, 24.

| abstract finding | figure / table | row keys | `verify_sec4` check |
|---|---|---|---|
| From N = 14 every principle holds the most-exposed community at exactly 4.77 dB in every ordering | Fig. 3 peak panel, §IV-D | five principles × `0.75, 1.0, 1.25, 1.5` × p0–p3 | "from N=14 every principle pins peak … ZERO band" |
| …where the baseline spans 4.77 to 10.00 dB | Fig. 3 peak band | `baseline` × `0.75…1.5` × p0–p3 | "the baseline's peak … spans 4.77-10.00 dB" |
| Free in travel time to N = 16, 3 aircraft-timesteps at N = 22 and 24 | Fig. 3 middle column, Table III | all six conditions × `0.25…1.5` | "travel: every principle attains the baseline's arrival …" |
| Equal, Sufficientarian, Prioritarian pay mainly in distance; Utilitarian, Proportional in departure delay | Fig. 3 middle column, Fig. 2 N = 24 row, Table III | five principles and `baseline` × `1.25, 1.5` | "caps pay in DISTANCE", "objectives pay in DEPARTURE TIME", "activation sizes" |
| Proportional confines the fleet to 6 of 25 tiles | Fig. 2 Proportional column, Table III | `proportional` × `0.25…1.5` × p0–p3 (band on tiles touched), per-tile peaks of the first ordering | "Proportional: the same 6 tiles …" |
| …and cuts summed added noise from 37.7 to 19.7 dB at N = 16 | Fig. 3 summed-noise panel | `proportional`, `baseline` × `1.0` × p0–p3 | "abstract: …", "Proportional summed noise …" |
| Every cell proven in all four orderings; Proportional's mean is 439 s at N = 24 | Fig. 4, Table III | all 144 runs; `proportional|1.5` | "every cell through N=24 is proven", "response table: mean wall …" |

## CSV → figure mapping

Every CSV is written by `harness/export_plot_data.py` from `fleet_main_metrics.json` (N ≤ 24).
The route CSVs also use the routings in `results/fleet_main.jsonl`, through the loader and the
leg-count rule `figures.py` uses. Figure sources live in `tex/figs/*.tex` and are `\input` by the
sections. `figs/style.tex` (colours, axis style) is `\input` by `main.tex`. Metric CSVs
have columns `N, <cond>, <cond>_lo, <cond>_hi, <cond>_open`: mean, band, and the value of an
unproven cell. `_open` is empty on this ladder.

| figure | source | CSVs |
|---|---|---|
| Fig. 1 capacity (§III) | `figs/capacity.tex` | `data/capacity.csv` (D, cap45, cap55, cap65; closed form, asserted against the capacity every principle cell recorded at D = 6) |
| Fig. 2 routings (`figure*`, TikZ) | `figs/routes_grid.tex` | `data/routes_tiles.csv` (ambient, vertiport, protected per tile), `data/routes_panels.csv` (panel titles, per-panel leg maximum, drawn ordering), `data/routes_N{8,16,24}_{equal,sufficientarian,prioritarian,utilitarian,proportional,baseline}.csv` (legs r1, c1, r2, c2, aircraft): 18 files |
| Fig. 3 metric vs N (`figure*`, groupplot 3×2) | `figs/metric_vs_N.tex` | congestion: `data/mvn_max_count.csv`, `data/mvn_shared_tile_timesteps.csv`; travel: `data/mvn_extra_vs_baseline.csv` (no baseline series), `data/mvn_departure_delay_total.csv`; noise: `data/mvn_peak_added.csv`, `data/mvn_total_added.csv` |
| Fig. 4 solve time (log y) | `figs/solve_time.tex` | `data/solve_time.csv` |

Colours and markers follow the Okabe–Ito palette and the markers in `figures.py`, imported
rather than copied. Leg width is 0.7 + 2.6·n/n_max pt, as in `figures._draw_map`. Figure
text is `\footnotesize`, with no bitmap text. Widths measured from the vector drawings and
text in the built PDF: Fig. 2 is 6.71 in and Fig. 3 is 6.79 in (limit 7.0); Fig. 1 is
3.23 in and Fig. 4 is 3.06 in (limit 3.3).

## Generator and harness changes

No change to the solver, the jsonl files, `metrics.py`, `metrics_run.py` or the runner.

* `figures.py`: `fig_metric_vs_N` panels regrouped by family (congestion | travel | noise).
  Peak added noise replaces average trip length. `fig_routes_grid` outlines the protected
  set. Matplotlib output is no longer used by the paper; its PNGs remain for the HTML
  review pages.
* `analyze.py` `table_capacity`: sizes changed from (16, 32) to (8, 24), both fully
  proven. The caption was corrected; the old one said only Equal and Sufficientarian send
  a cap. The table is set in `\footnotesize` with 2.5 pt column separation, because it
  overran the column by 46 pt.
* `check_tex.py` changes:
  * knows the pgfplots, pgfplotstable and TikZ vocabulary and the TeX primitives the
    figures use
  * accepts macros a figure defines for itself
  * **new** `MISSING DATA` check: every CSV a figure reads must exist
* `verify_sec4.py`: rewritten for the new text, 31 checks, N ≤ 24 only.
* `export_plot_data.py`: new.
* Deleted from `tex/figs/`: the 19 matplotlib PDFs. Running `figures.py` would write them
  again, but nothing `\input`s them.

## Could not verify: decide before submission

1. **Engine.** The page count is from Tectonic (XeTeX with `\usepackage[T1]{fontenc}`, now in
   `main.tex`, body in Times), not pdfLaTeX. The same layout is expected on Overleaf, with
   two pages of margin; confirm there.
2. **Venue rules.** The 8 pages including references, double-anonymous review and the
   15 September 2026 11:59 PST deadline come from `README.md` (checked against the CFP on
   2026-09-05). They were not re-checked this session.
3. **Overleaf compile time.** A single pass takes 10.4 s here and a full build needs
   several. If the Overleaf plan's compile timeout is shorter than that, compile
   `figs/*.tex` standalone and `\includegraphics` the PDFs, keeping the sources and CSVs.
   This was not needed locally, so it was not done.
4. **Setup selection.** The §III-C sentence ("a screen … selected D = 6 dB and the
   corridor set") rests on `results/setup_choice.md` (`screen3.jsonl`), not the metrics
   file. What is checked is its stated consequence (the cap is full under every
   principle at N = 16) and the reference numbers (0.44; stations 16, 20, 25).
5. **Machine.** "One 14-core workstation" comes from the machine record in `NIGHT_REPORT.md`.
   "Eight solves in parallel" is checked (`runner_par = 8`).
6. **Utilitarian.** Its count objective (airborne time) is attained by the baseline's
   routing at every size. §IV-B states this as a property: Utilitarian keeps the
   cap-feasible shortest-path routings. The decibel-form Utilitarian ladder at `D6_protA`
   was never run. Whether the paper should carry that form is a decision this session
   could not settle with a measurement.
7. **Protected set.** It is chosen from the data: the busiest low-income corridor tiles
   (DECISIONS D24), and §III-C says so. A reviewer may raise selection effects.
8. **Stations 9 and 12.** These are two of Proportional's six tiles. They are unclaimed
   tiles in the source instance, set to 55 dBA with neutral income and population scores
   by the request builder. The paper calls them 55 dBA tiles, which is true of the
   instance as solved.
9. **Bibliography.** The cited SMT/MAPF entries (`demoura2008z3`, `bjorner2015nuz`,
   `surynek2019smtmapf`, `stern2019mapf`) and the philosophy entries were entered from
   memory, per the `refs.bib` header. Page ranges are unconfirmed.
10. **Anonymity.** The PDF metadata has no author, and its text contains no names,
    affiliations or tool vocabulary; "residential" occurs only in a cited title.
    `main.tex` keeps the real author block **commented out**, so strip it before sharing
    the source.
11. **Brief vs data.**
    * The brief expected the cap-based lane proven across the ladder and the objective
      lane proven only to a frontier. On the reported ladder every condition is proven at
      every size, and §IV-E says that.
    * The brief's "aircraft on a shared route" metric is not reported. The metrics file
      records it for one ordering only (no band), so no attributable statement is possible.
12. **Spare length.** The paper uses 6 of 8 pages, and §IV is 2.1 pages against 3.6
    budgeted. The two spare pages are available if anything should come back.
