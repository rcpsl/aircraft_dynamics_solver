# 2026-08-28 — lexicographic vs weighted objectives

## What this data is

`lex_objective_experiment/` — the evidence that justified making the solver's
objectives **lexicographic**, plus the superseded weighted scheme kept as a working
control.

```
lex_objective_experiment/
├── README.md                     the experiment, its measurements and its verdict
├── solver_server_dB_weighted.py  the CONTROL: the old weighted-sum scheme, port 5056
└── harness/                      probe scripts, launchers, captured stdout, route dumps
```

## The question it answered

The principle and the arrival-time penalty used to be summed into one weighted
objective. Because the normalising divisors are loose by very different amounts, the
time term outvoted the principle roughly **31:1** on the measured payload — 68.8% of
its normalised range against the utilitarian term's 2.2%. Z3 was mostly minimising
arrival time while appearing to optimise fairness.

Making them separate `opt.minimize` calls under Z3's default `priority='lex'` means
the time tier can only choose among answers already optimal for the principle. It
provably cannot cost a unit of fairness.

## What it measured

Per its README: fairness is **exactly equal** to the weighted scheme on
Proportional, Prioritarian, Equal and Sufficientarian. Runtime is ~1.4x slower on
Proportional, ~2x **faster** on Prioritarian, and even on the other two. On
Utilitarian + People the two genuinely diverge: lex reaches a 5.5-7.5% better noise
value but did not prove optimality within an 1800s cap, where the weighted scheme
proves it in 202-658s. That case now relies on the best-so-far salvage.

## The direction of this folder is inverted

This experiment **shipped on 2026-08-27**. Production is lexicographic, and
`OBJECTIVE_MODE` in the solver reads `"lex"`.

So `solver_server_dB_weighted.py` is no longer the experimental arm — it is the
**control**, kept on port 5056 so every measurement above stays reproducible and so
there is a no-code-change fallback if lex hurts in a live session. It differs from
production in exactly four places: the header, the `OBJECTIVE_MODE` constant, the
`minimize()` block, and the port. The API, the phase-2 messaging and the salvage are
identical.

It was also patched alongside the proximity-noise change on 2026-09-03, so it has
not drifted from production on that axis either.

## Solver version

The experiment ran against the solver at **`83804cc` (2026-08-23)** — this repo's
second solver commit — with the lex change applied on top. That change is in this
repo's **third** solver commit (2026-09-03), which groups lex with the phase-2
salvage and the proximity-noise pricing; see `UPDATE_RECORD.md` for why those three
could not be separated.

`solver_server_dB_weighted.py` in this folder is therefore the better reference for
what the *pre-lex* objective code looked like, since the control preserves it
deliberately.

## A note on `harness/`

The original repository gitignored `*_experiment/harness/` as local scaffolding. It
is included here because this is a data repository and the harness holds the probe
outputs and route dumps the conclusions rest on — without it, the claims above stand
on prose alone.
