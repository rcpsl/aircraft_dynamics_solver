# For the reviewer — read this before the paper

## Status in one paragraph

Draft is complete: five sections, abstract, seven floats, 24 references. Every number
traces to a recorded solver run (213 solves, 107 solver-hours). **It has never been
compiled** — there is no TeX installation on the machine it was written on, so the first
Overleaf build is the real test. A structural checker (`check_tex.py` in the harness)
verifies inputs, refs, citations, figures, brace and environment balance, undefined
macros and unprovided environments, and currently reports clean.

## Two things to decide, both above my pay grade

**1. Venue.** The paper is ~10,200 words with seven floats, which is roughly **11–12
pages**. ICRA 2027 allows **8, hard** — over-length papers are returned without review,
there is no fee-based extension, and the deadline is **15 September 2026, 11:59 PST**.
Reaching 8 requires deleting a result that is true. The realistic options, in the
project README under "LENGTH":

  - move to a journal / transportation venue (T-RO, *Transportation Research Part C*,
    where the nearest related work appeared);
  - split the encoding (§III) from the empirical audit (§IV) into two papers, either of
    which fits 8 pages;
  - cut to 8 for ICRA by taking the whole trim menu *and* dropping one finding.

**2. What to do about the machine-load confound.** See below. It is disclosed, not fixed.

## What has already been retracted, and why that matters

Five findings were withdrawn during preparation, four of them after they had reached the
abstract. Every one came from the same error: **comparing a solver run that timed out
against one that was given more time**, which changes the answer without changing the
principle. The full record is in `../results/claims_audit.md`.

  1. "The cap binds hard at N=32" — the 158-vs-88 gap was an unproven incumbent; given
     four hours the same configuration proves out at 88, no binding.
  2. "Equal and Sufficientarian diverge at N=30" — both were unproven and 77% from
     optimal; re-run, both prove identical at 84.
  3. "The principles differ in how far they detour from the shortest path" — every
     non-zero detour came from a 600 s run. At matched budgets all five fly 100%
     shortest paths.
  4. "Utilitarian and Proportional return identical maps" — an exact-equality claim on
     two unproven rows, using a metric that sums over time and so cannot see the
     difference it claimed was absent.
  5. "On the second instance Equal and Sufficientarian produce identical occupancy" — a
     lookup bug let ablation *controls* overwrite the treatments. Real distance 0.13.

This is why the paper is shorter than it was. I mention it because the retraction record
is unusually complete and is, arguably, part of the contribution.

## The one confound that is disclosed but not removed

The long-budget re-runs happened to execute on a less loaded machine. Phase 1 is
budget-independent, so its wall time is a clean contention probe: across the 40
configurations run in more than one sweep, the **median phase-1 ratio is 3.10×**
(max 23×). So every 600 s-against-four-hour comparison in the paper moves two variables.

Why the retractions still stand: both changes favour the long run, and each retraction
*withdraws* a claimed effect rather than asserting a new one — a confound that
strengthens the long run cannot manufacture a null result. Removing it properly means
re-running the corpus serially, which is ~107 solver-hours. Disclosed in §IV-A and
flagged automatically by `cap_audit.py`.

## Known weak points, so you do not have to find them

  - **Related work is thin.** Two directly relevant papers (Gao et al. 2024,
    Hauptvogel et al. 2021) are now cited and positioned, but there are still **zero
    ICRA/IROS/RA-L/T-RO citations** in a paper being submitted to ICRA.
  - **One instance and a variant.** All empirical findings rest on a 5×5 Austin map plus
    a reduced-adjacency version of the same map.
  - **Utilitarian and Proportional never prove optimality above N=8**, even at four
    hours. That is reported as the tractability result rather than hidden, but it means
    several comparisons involving them are directional rather than exact.
  - **Style.** Long sentences and heavy em-dash use throughout; section titles are
    essayistic rather than conventional. Worth a pass.

## Where everything is

  - `main.tex` — compile this. Author block is **anonymised** for ICRA's
    double-anonymous review; the real one is commented out directly above it.
  - `sec1`–`sec5` — the five sections.
  - `tables/` and `figs/` — **generated**; do not hand-edit. They are rebuilt by
    `harness/analyze.py` and `harness/figures.py` from the raw solver output.
    `tables/caps.tex`, `tables/scaling.tex`, `tables/tiers.tex`, `tables/detour.tex`,
    `tables/distinct.tex` and `figs/tradeoff.pdf` are generated but deliberately unused —
    re-`\input` any of them if you want the detail back.
  - `../results/claims_audit.md` — every claim checked, corrected or retracted.
  - `../results/cap_audit.md` — which claims still rest on a run that hit the clock.
  - `../README.md` — the trim menu with word counts, and the reproduction instructions.
