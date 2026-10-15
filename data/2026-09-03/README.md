# 2026-09-03 — pricing Proportional, and the ranking it switches off

Two folders, one question split in half: *how should Proportional price burden*, and
*what does the answer cost the participants' ranking?*

## `proximity_noise_experiment/` — weight x added noise

```
proximity_noise_experiment/
├── README.md                  the experiment and its verdict
├── solver_server_dB_noise.py  a SNAPSHOT of the arm as measured — now behind production
└── harness/                   probes, launchers, captured output, route dumps
```

Proportional used to price burden as `weight x occupancy` — one aircraft-timestep on
a tile costs that tile's weight. This experiment priced it as `weight x the dB
increase the station suffers`, which is the burden a community actually experiences.

Measured over 30 rankings: never a louder peak, 4.8-5.6 dB quieter in 11 of 28, and
traffic over 45 dB tiles pinned to its floor of 4 aircraft-timesteps every time.

Two consequences recorded as *not* bugs:

- dB is **concave** in the count, so stacking aircraft on one tile is cheaper than
  spreading them (3 on a 45 dB tile cost 6.02 dB; three separate tiles cost 9.03).
  The objective therefore concentrates traffic, where the count term was indifferent
  to concentration.
- the increase depends on the station's **own baseline**, so one aircraft adds
  3.01 dB at a 45 dB tile and 0.043 dB at a 65 dB tile — a large implicit price
  gradient favouring already-loud tiles.

**This shipped on 2026-09-03** and is the default: a request sending no
`proximityMode` gets the dB term. `proximityMode: "count"` reproduces the old
behaviour and is roughly 28x cheaper for Z3. Both replies echo `proximityMode`, so a
stored result says which priced it.

The folder's direction is inverted, as with the lex experiment.
`solver_server_dB_noise.py` is a snapshot of the arm **as it was measured** and is
now **behind** production: it forked before the lexicographic objective and the
best-so-far salvage landed. Do not deploy it or diff it as if it were current.

Known caveat from the project notes: at the 600s budget this term can return
partials with a **louder peak** than the count term's proven optimum. Shipping it
was a decision, not a free win.

## `proximity_weight_experiment/` — restoring the ranking

```
proximity_weight_experiment/
├── NOTES.md     the diagnosis and three payload-only fixes
└── harness/     104 files of sweep data — the bulk of this folder
```

dB pricing switches off the participant ranking: re-derived from the other folder's
`sweep.jsonl`, of 30 rankings 28 are comparable and they produce **one** distinct
occupancy vector under noise pricing. Every ranking gives the same routing, so the
cards participants reorder stop mattering.

This folder asks whether the ranking can be recovered **without touching the
solver** — by changing only the `proximityWeights` vector the client sends, plus the
already-supported `proximityNoiseRef` field. Nothing here modifies a solver file.

The diagnosis is the ambient double-count: the dB curve fits an implicit ambient
rank weight of about **0.88**, while the maximum a participant could assign at the
time was 0.40. The copy of ambient the participant cannot control is the stronger
one.

**Still open as of 2026-10-15.** The current dashboard sends no `proximityNoiseRef`,
so the gradient is still there. Under the two-factor 60/40 model the dashboard now
uses, the comparison is 0.88 implicit against a 0.60 participant maximum — 1.46x.
Ambient is no longer a *ranked* factor (removed 2026-09-29), so it is no longer
double-counted; it is counted once, in the dB curve, where nobody can rank it.

## Solver version

Both ran against the solver at **`83804cc` (2026-08-23)** plus the lex change, i.e.
the state that this repo's **third** solver commit records (1751 lines, dated
2026-09-03). That commit is the shipped result of this experiment.

`solver_server_dB_noise.py` is NOT that state — it is the pre-lex, pre-salvage fork,
kept as the measurement snapshot.

## A note on `harness/`

The original repository gitignored `*_experiment/harness/`. It is included here
because `proximity_weight_experiment` is 105 files of which **104 are in
`harness/`** — excluding it would reduce that experiment to a single markdown file,
and the sweep data is the evidence.
