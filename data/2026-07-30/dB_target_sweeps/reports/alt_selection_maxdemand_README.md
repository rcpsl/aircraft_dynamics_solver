# Alternative target selection: max-demand rule

A **re-selection over the existing `equal_allocation` sweep** — no new solver
runs. Produced by `reselect_maxdemand.py`, output in `picks_maxdemand.csv`.

**Nothing published is modified.** The original
`<combo>/<mode>/picks_summary.csv` files and their target CSVs are untouched;
this folder sits alongside them as an alternative reading of the same raw data.

## Why

The published picks use a **"closest achievable value strictly below the
target"** rule (`../README.md` §6). That rule effectively **maximizes noise
subject to staying under the target** — close to the opposite of what a noise
target normally means. Among two solutions that both satisfy an 8 dB target,
it deliberately prefers the 7.9 dB one over the 6.2 dB one, purely because
7.9 is numerically nearer to 8.

Where the target exceeds what the network can physically reach, this
degenerates. The `avg` metric's ceiling in this network is ~6-9 dB, far below
the 18 dB target, so "closest from below" collapses into "find the loudest
thing available" — and that rewards *small-fleet* configs, because `avg` is a
max-over-stations of a per-station time average, and a light fleet can
concentrate traffic onto one station across more timesteps.

Consequences visible in the published `avg` data:

- In **6 of 8** cells the 18 dB pick is a duplicate of the 8 dB pick.
- In `s2-55_s6-45/community_equal` the 18 dB pick is **strictly dominated** by
  the 8 dB pick — louder (8.948 vs 7.933 dB) *and* serving 75% less demand
  (25% vs 100%). No one would ever prefer it.
- In `s2-55_s6-45/people_equal` the 18 dB pick is louder than the 8 dB pick
  for identical demand.

## The alternative rule

Reading "target" as *a noise budget we are willing to tolerate*:

```
among all sat candidates with metric value strictly below the target,
pick the one serving the MOST demand; tie-break toward the QUIETEST.
```

## Validation (do read this before trusting the numbers)

The script first re-derives the **original** rule from the raw sweep and
compares against the actually-published `picks_summary.csv` values:

- **40 of 40** cells where the strictly-below rule applies reproduce the
  published pick exactly.
- The other **8** cells are all `peak`/3 dB, and are the documented `‡`
  exception in `../README.md` §8 — sub-3 dB peak is structurally unreachable,
  so those published values (3.0103, 4.7712) deliberately sit *above* the
  target rather than below it. The strict rule correctly finds no candidate,
  which is why they're blank in both columns here. Not a discrepancy.

So the search log fully explains the published data, and the re-selection
below is applied to the same candidate set the original search saw.

## Results

**The max-demand rule is never worse.** Across all 40 comparable cells: **0
cells lose on either axis** (never louder, never less demand), and **7 cells
improve on both** — quieter *and* more demand served:

| cell | target | published | max-demand |
|---|---|---|---|
| s2-65_s6-45/people_equal | 8 avg | 6.248 @ 25% | **4.746 @ 100%** |
| s2-65_s6-45/people_equal | 18 avg | 6.248 @ 25% | **4.746 @ 100%** |
| s2-55_s6-45/community_equal | 18 avg | 8.948 @ 25% | **6.625 @ 100%** |
| s2-55_s6-45/people_equal | 8 avg | 7.372 @ 25% | **5.160 @ 100%** |
| s2-55_s6-45/people_equal | 18 avg | 8.610 @ 25% | **5.160 @ 100%** |
| s2-55_s6-55/people_equal | 3 avg | 2.386 @ 7.1% | **2.007 @ 12.5%** |
| s2-65_s6-55/people_equal | 8 peak | 6.990 @ 12.5% | **4.771 @ 25%** |

The pathological `s2-55_s6-45/community_equal` 18 dB cell is resolved: from
8.948 dB at 25% demand to **6.625 dB at 100% demand** — quieter *and* four
times the service.

The rule changes the pick in 34 of 48 rows overall; in the remaining cells the
published pick already happened to be the max-demand one.

## An honest finding this surfaces

Under the max-demand rule, **8 dB and 18 dB give identical answers in all 8
`avg` cells** — but now for a meaningful reason rather than an artifact:
*full demand already fits under 8 dB, so a looser 18 dB budget buys nothing.*
That is a real, reportable result. (The published rule also collapsed them in
6 of 8 cells, but because both targets were chasing the same unreachable
ceiling — a much less interesting reason.)

For `peak`, 8 and 18 stay distinct in **0 of 8** collapsed cells — i.e. they
differentiate in every cell, because the peak ceiling (~15-16 dB) sits above
both targets, so the budget genuinely binds at both levels. The problem
described here is specific to the `avg` metric.

## Caveats

- These are **re-selections over already-computed solves**, so each row points
  at a (variant, U) combination that was actually solved and returned sat. But
  the corresponding per-zone CSVs in `<combo>/<mode>/` were written for the
  *published* pick — where `changed=CHANGED`, no matching zone-level CSV
  exists on disk. Regenerating those would need new solver runs.
- The sweep itself is not exhaustive (4 fleet variants × integer U 0-16, with
  31-55 of 68 points per cell not returning usable data — `../README.md` §10).
  A denser sweep could beat both rules.
- The tie-break is "quietest among max-demand." Tie-breaking toward, say,
  lowest peak or shortest travel time instead would give slightly different
  picks in some cells.
