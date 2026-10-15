# 5x5 real-time solver — participant dashboard

`uam-dashboard-community-readability-0918.html` is the workshop frontend. It is a
single self-contained HTML file: no build step, no dependencies, no server of its
own. Open it in a browser.

It talks to `solver_server_dB.py` (in the parent folder) over HTTP. Start the solver
first:

```
python solver_server_dB.py          # listens on 127.0.0.1:5051
```

Then open the HTML file. If the solver is not running, the dashboard says no route
was generated rather than silently showing its offline estimate as a result.

This is the current dashboard. An older lineage, `uam-dashboard-NEXT-5x5_v2.html`,
is not included here; it predates the readability pass and the factor removals
described below, and the two are not interchangeable.

## What the activity is

A 5x5 grid of 25 Austin communities. Three vertiports (Airport, Downtown, Commuter
Town) generate air-taxi demand. Participants pick a **fairness principle** and a
**dB limit**, press Run, and see where the noise lands. The point is that the
principle changes who carries the burden, and the dashboard has to make that
visible without overclaiming.

Each community has an ambient baseline of exactly 45, 55 or 65 dB (8 / 8 / 5 tiles,
plus 4 Create-Your-Own slots participants fill from the same three values). Aircraft
are 45 dB. One aircraft over a tile for one timestep therefore adds 3.010 dB to a
45 dB community, 0.414 dB to a 55 dB one and 0.043 dB to a 65 dB one — a ~70x
gradient that drives much of the behaviour below.

One solver timestep is 3 minutes; the reporting period is one hour.

## The five principles, and what each sends the solver

| principle | request fields | what it means |
|---|---|---|
| **Equal** | `D = U = limit` | caps the GAP between the loudest and quietest community, per timestep |
| **Sufficientarian** | `D = limit`, `U` wide | caps each community's own increase |
| **Utilitarian** | `optimizeUtilitarian`, `utilNoiseMode` | least total added noise |
| **Prioritarian** | `optimizePrioritarian`, `protectedStations` | protect the chosen communities first |
| **Proportional** | `optimizeProximity`, `proximityWeights` | benefit carries burden |

Two things about this table are worth knowing before you run a session.

**Equal and Sufficientarian return the same routing on this map.** Equal sends the
limit as `D` as well as `U`, and with fewer aircraft than the 25 stations pigeonhole
leaves some station empty at every timestep, so the minimum increase is always 0 and
"gap <= n" already implies "every increase <= n". This is a known property of this
map, left as-is by decision.

**Neither sets any objective.** Their rule is the hard cap, so every routing inside
the cap satisfies the principle equally well, and the one on screen was chosen by
the arrival-time tie-break and then by Z3's search order. That is what the
alternatives panel exists to expose — see below.

## Admin ("Facilitator set-up")

Demand per corridor, aircraft dB, vertiport dB, the Create-Your-Own prefills, the
solver address, extra time steps, the solve budget, the cache flush, and the
alternatives controls. Changing anything that alters the request marks the shown
route stale; changing the ranking controls clears the map, because the ranking is
applied when a route is generated.

`Extra time steps` should stay at 1. Measured on this map: 0 extra gave a +6.99 dB
peak, 1 extra gave +4.77 dB, and 2 changed nothing while costing far more.

## The alternatives panel

With `SOLVER.alternatives = 5` (the default) the dashboard asks the solver for five
routings that tie on the group's rule and on arrival time, ranks them here on the
frontend, and puts the quietest on the map. The panel lists all five; clicking one
repaints the map from a routing already in hand, without touching the solver.

The ranking is frontend-only — the solver is not modified to do it. These routings
already tie on the rule and on arrival time, so reordering them cannot trade either
away. It serves the quietest of a **sample**, not a proven minimum, and the panel's
wording says "of N sampled" throughout for that reason.

`rankBy` is `'total'` (added dB summed over every station and timestep, the same
quantity the Utilitarian objective minimises) or `'peak'` (the loudest single
station-timestep). They can disagree, so both figures appear on every row.

The open list is an overlay floated over the map. It must stay that way: `.stats` is
`flex:0 0 auto` above a `.gridwrap` with `min-height:1050px`, so a panel in the
normal flow cannot borrow space from the map — it grows the column and pushes the
grid off screen instead.

## Numbers on screen, and what they actually mean

**"Cumulative Noise: before and with UAM"** is a population-weighted **arithmetic
mean of per-community dB levels** across the 18 tiles that count (vertiports and
unclaimed Create-Your-Own slots are excluded). Despite the name it is cumulative
over *time* and averaged over *space* — nothing is summed across communities. It
therefore divides local harm by 18: a +10 dB hit on one community moves the headline
+0.6 dB. Concentrated harm is visible in the map colours and the "Highest cumulative
noise" strip, not here.

Per tile, the increase underneath that mean is energy-correct: `cumulativeChanges`
adds aircraft energy to baseline energy and normalises to the hour. It is the
cross-tile step that averages decibels directly.

**"dB-steps"** in the alternatives panel is added dB summed over all 25 stations and
all timesteps. It is a cost functional, not a loudness — decibels are not additive,
and the same two aircraft score 4.771 stacked on one 45 dB tile versus 6.021 split
across two. The panel prints the per-cell average next to any spread it quotes
because the raw total overstates itself.

**Trip length** counts position changes from the returned paths, so self-loop holds
are correctly ignored. It is not read from `totalTransit`, which the solver only
reports when the utilitarian objective is on.

## Proportional: how the 60/40 works

Participants rank two factors — Income and Vertiport distance. The first counts 60%,
the second 40%. Those are **exponent** weights:

```
tile weight = 5 ^ (0.60 * score_first + 0.40 * score_second)
```

Each factor scores every tile 0..3, where 0 means fly over it freely and 3 means
protect it hard. Income: Low 3, Medium 1.5, High 0. Distance: the Manhattan ring to
the nearest vertiport, so a vertiport tile scores 0 and is cheapest to overfly —
under benefit-carries-burden the tiles enjoying the access are the ones that pay.
Weights sum to 1 and scores top out at 3, so the exponent stays in [0,3] and the
weight in [1,125].

The solver never sees 60 or 40. It receives `proximityWeights`, a flat 25-number
vector. Ambient noise and Population were removed as ranked factors on 2026-09-29
and 2026-10-05 respectively.

**Known limitation, stated plainly:** Proportional prices burden as weight x the dB
*increase*, and the increase depends on each station's own baseline. That builds in
an ambient gradient worth about 0.88 in equivalent rank-weight terms, against the
0.60 a participant can give their top-ranked factor — 1.46x stronger than the lever
they control. It is why reordering the two cards often looks inert. The solver
exposes `proximityNoiseRef` to flatten this; the dashboard does not currently use
it.

## Caching

Responses are cached in `localStorage` keyed on the request JSON, so a repeat of a
set-up already solved returns instantly instead of costing another 20-80s of Z3.

**Bump `CACHE_KEY` whenever the solver changes what it returns.** The key is the
request, and a solver-side change does not change the request, so without a bump
every participant keeps being served pre-change answers with nothing on screen to
say so — and a reload does not help, because reload rehydrates the cache straight
back out of `localStorage`. It is at `v4`. "Empty the cache" in Admin is the
mid-session escape hatch.

## Status

The alternatives panel and the overlay fix are verified by a stub-DOM harness
(27 assertions: ranking, painting, open/close, the single-routing case) and against
the live solver, but **this file has not been opened in a browser since those
changes**. The CSS is reasoned from the layout rules, not seen. If the panel sits
oddly against the stats border, the `top:calc(100% + 6px)` offset on `.altbody` is
the number to nudge.
