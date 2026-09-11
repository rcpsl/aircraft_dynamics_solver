
### default (dashboard, T_max = floor + 1) @ N=16   N=16   ->  **PASS**

Setup filter: `default`.

5 distinct routing(s), 5 metric(s) visibly spread.
Pairwise occupancy distance: min 0.114, mean 0.189. Distinct routings: 5/5 (equal, sufficientarian, prioritarian, utilitarian, proportional).

| metric | equal | suffic | priori | utilit | propor | spread | visible |
|---|---|---|---|---|---|---|---|
| max aircraft per tile | 5 | 8 | 7 | 9 | 5 | 4.00 | yes |
| shared tile-timesteps | 12 | 11 | 14 | 10 | 10 | 4.00 | yes |
| aircraft on a shared route | 10 | 7 | 13 | 13 | 14 | 7.00 | yes |
| total added dB | 39.62 | 39.86 | 30.92 | 19.98 | 23.81 | 19.87 | yes |
| peak added dB | 6.99 | 6.02 | 4.77 | 6.99 | 6.99 | 2.22 | yes |
| avg trip hops | 2.75 | 2.75 | 2.75 | 2.81 | 2.88 | 0.12 | no |

Status: equal=optimal, sufficientarian=optimal, prioritarian=optimal, utilitarian=partial (probe), proportional=partial (probe)

### sl3 (T_max = floor + 3) @ N=16   N=16   ->  **PASS**

Setup filter: `sl3`.

5 distinct routing(s), 6 metric(s) visibly spread.
Pairwise occupancy distance: min 0.136, mean 0.271. Distinct routings: 5/5 (equal, sufficientarian, prioritarian, utilitarian, proportional).

| metric | equal | suffic | priori | utilit | propor | spread | visible |
|---|---|---|---|---|---|---|---|
| max aircraft per tile | 7 | 8 | 4 | 16 | 14 | 12.00 | yes |
| shared tile-timesteps | 13 | 14 | 15 | 24 | 19 | 11.00 | yes |
| aircraft on a shared route | 11 | 8 | 12 | 0 | 3 | 12.00 | yes |
| total added dB | 35.88 | 37.70 | 36.95 | 69.05 | 61.94 | 33.17 | yes |
| peak added dB | 6.02 | 4.77 | 6.99 | 7.78 | 11.76 | 6.99 | yes |
| avg trip hops | 2.75 | 2.75 | 2.75 | 6.75 | 6.50 | 4.00 | yes |

Status: equal=optimal (probe), sufficientarian=optimal (probe), prioritarian=optimal (probe), utilitarian=partial (probe), proportional=partial (probe)

---

## Reading the two checks together

**Verdict: `SETUP_MAIN = default`.** The rule was fixed before the data was seen and the
default setup passes it — 5 of 5 principles produce mutually distinct routings, 5 of 6
headline metrics visibly spread. Phase 1b was not required. The `sl3` screen below was
run anyway, as a side note, and it does not change the verdict.

### What the slack screen settles, and what it does not

The brief's hypothesis was that the dashboard's tight horizon (`T_max` = Chebyshev floor
+ 1, + 0 when the Utilitarian term is live) is why every prior run flew shortest paths.
Three extra timesteps of room separates two very different answers.

**Proven, and it refutes the hypothesis for three principles.** Equal, Sufficientarian
and Prioritarian are all *proven optimal* at `sl3` with `T_used = 8`, and all three still
fly exactly the shortest-path floor: 44 fleet hops against a floor of 44, avg 2.75, the
same as at the default. Given three timesteps of room to detour into, they decline to use
any of it. Their travel-time neutrality is a property of the principle, not an artefact
of a tight horizon.

**Directional only, and NOT comparable to the default rows.** Utilitarian and
Proportional do use the horizon when given it — 108 and 104 fleet hops against the same
floor of 44, avg 6.75 and 6.50. So the two decibel-valued objectives are willing to buy
noise reduction with travel time, and the tight default horizon is what stops them.

Their *noise* numbers at `sl3` must not be read against the default ones. All four
Utilitarian and Proportional rows in this file are 900 s incumbents, and raising `T_max`
from 5 to 8 makes the phase-2 search much harder, so the `sl3` incumbent is further from
its optimum than the default one is. Total added noise reading 69.05 dB at `sl3` against
19.98 dB at the default is a statement about how far each search got, not about what the
principle does with a longer horizon. Comparing a search that ran out of clock against
one that did not is the single error behind every retraction in `claims_audit.md`, and
it is not repeated here: the `sl3` claim is that these two objectives **detour when they
can**, nothing more.

This is also the second reason to keep the default. At `sl3` the two objective principles
are markedly less tractable, so an unlimited-budget ladder on `sl3` would reach a lower
frontier than the one on the default — fewer proven cells, for a setup the pre-registered
rule did not select.


---

## CORRECTION, 2026-09-11 — the `sl3` reading above is withdrawn

The block above says Utilitarian and Proportional "do use the horizon when given it —
108 and 104 fleet hops against the same floor of 44 — so the two decibel-valued
objectives are willing to buy noise reduction with travel time."

**That inference does not hold.** The full slack probe (slack 1, 2, 3, 4 at N=8 and
N=16) shows hops and noise rising *together*:

| Utilitarian, N=16 | slack 1 | slack 2 | slack 3 | slack 4 |
|---|---|---|---|---|
| extra hops above the floor | 25 | 49 | 55 | 82 |
| total added noise (dB) | 34.5 | 60.5 | 69.4 | 134.8 |

An objective that minimises noise does not prefer a routing that is worse on the quantity
it minimises. And the feasible sets are nested — sticky arrival keeps every routing
available at floor+1 available at floor+4 — so the true optimum **cannot** get worse as
the horizon grows. A returned value four times worse is a search that has not got far.

What the extra hops measure is how poor a 900 s incumbent becomes once `T_max` grows, not
what the objective would choose. Every row here is `partial` at every horizon, so the
question is open, and Sec. IV-C now says so rather than reading a preference off it.

This is the same error the project has retracted five times: attributing to a principle
something that is a property of how far the search got.
