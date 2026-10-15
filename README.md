# UAM noise-fairness solver

A Z3-based route planner for urban air mobility over Austin, built for a workshop
that asks participants: *if we fly air taxis over this city, who carries the noise?*
Participants choose a **fairness principle**; the solver routes the fleet under it;
the dashboard shows where the noise lands.

```
.
├── solver_server_dB.py       the solver — a Flask service on port 5051
├── UPDATE_RECORD.md          every change to the solver, with dates and commits
├── 5x5_realtime_solver/      the participant dashboard (+ its own README)
└── data/                     past result sets, filed by date (a README in each)
```

Start here: this file for the solver, `5x5_realtime_solver/README.md` for the
activity, `UPDATE_RECORD.md` for how the solver got here and what is still open.

---

# `solver_server_dB.py`

```
pip install z3-solver flask flask-cors
python solver_server_dB.py        # 127.0.0.1:5051
```

A single file, no package layout. `POST /solve` with a JSON scenario, get routes and
a noise matrix back. `GET /progress` reports the live phase (safe during a solve;
it never touches Z3 or the solve lock). `POST /cancel` abandons a running solve.

## The idea

Everything is expressed in **decibels**, not aircraft counts. A community has an
ambient baseline; aircraft flying over it add noise on top. The increase is

```python
dB_increase(baseline, n, aircraft_dB) = 10*log10(10**(baseline/10) + n*10**(aircraft_dB/10)) - baseline
```

which has two properties that drive everything else:

- **It is concave in `n`.** Two aircraft on one tile are quieter than one aircraft on
  each of two tiles. Objectives that minimize total noise therefore *concentrate*
  traffic rather than spreading it.
- **It depends on the baseline.** With 45 dB aircraft, one aircraft adds 3.010 dB to
  a 45 dB community but only 0.043 dB to a 65 dB one — a ~70x gradient. Quiet places
  are expensive to overfly, and that is built into the arithmetic before any
  fairness rule is applied.

Internally all dB values are multiplied by `SCALE = 100` and rounded to integers for
Z3. That rounding is not always innocent — see `UPDATE_RECORD.md`, open item 3.

## Two phases

1. **`find_min_T`** — feasibility and the minimum horizon. Enforces the hard caps
   `D` and `U`. Escalates `T` until the scenario is satisfiable or the budget runs
   out. A D-admissible reachability BFS rejects impossible requests early.
2. **`optimize_objectives`** — rebuilds the constraints in a fresh `Optimize` and
   minimizes the objectives.

A phase-2 timeout does **not** silently fall back to phase 1's unweighted route. The
best model found so far is recovered and reported as `optimality: "partial"`.

## The hard caps

| field | meaning |
|---|---|
| `D` | per-station cap on the dB **increase**. Converted to `D_count[m]`, the maximum aircraft a tile may hold — which also bounds the count variables and shortens the dB `If`-chains, so a tight `D` makes the model much smaller. |
| `U` | `max(dB) - min(dB) <= U`, enforced **per timestep**. One constant in one constraint per timestep, so its value never changes the model size. |

`U` is encoded via two auxiliary integers rather than a table over every station
pair — the change that cut the model from ~110,000 assertions to ~2,089.

**Always send `D` alongside `U`.** Measured at `U=5` on the 19-aircraft payload:
`D=30` took 341.7s and 508k conflicts, `D=10` 150.2s, `D=5` **59.0s and 16.8k
conflicts**. `D` does the pruning.

## Objectives, and the order they apply in

`OBJECTIVE_MODE = "lex"` since 2026-08-27. Z3's `Optimize` applies objectives in
**call order** under `priority='lex'`, and there are two tiers:

1. the principle — a weighted sum of whichever of `optimizeUtilitarian`,
   `optimizePrioritarian`, `optimizeProximity` are live
2. **arrival time** — `T_penalty`, the sum over aircraft of the timestep each
   arrived, built from the sticky `ha` flag

Tier 2 can only choose among answers already optimal for tier 1, so it provably
cannot cost a unit of fairness. Three consequences:

- `weightTime` no longer sets a magnitude, only whether the tie-break exists at all
- with one principle term live, **its weight cannot move the argmin** — scaling it
  alone is inert
- **Equal and Sufficientarian set no objective at all.** Their rule is the hard cap,
  so `T_penalty` is the only `minimize` call, and every routing inside the cap is
  equally valid. See `enumerate` below.

## Request fields

`N`, `M`, `D`, `U`, `adjacency` (M x M, self-loops required for soft T),
`startPositions`, `endPositions`, `aircraftMultipliers`, `baseline` (M floats),
`aircraftDB`, `hardT`, `T_max`, `weightTime`, the three `optimize*` flags with their
weights, `utilNoiseMode`, `protectedStations`, `stationTransitWeights`,
`proximityWeights`, `proximityMode` (`"noise"` default, or `"count"`),
`proximityNoiseRef`, `timeoutMs`, `clientRequestId`.

Enumeration (opt-in, added 2026-10-12):

| field | default | meaning |
|---|---|---|
| `enumerate` | `0` | up to 50 routings satisfying every hard constraint, the first being the one `/solve` would have returned alone |
| `enumerateDistinct` | `"counts"` | `"counts"` = two alternatives differ in what some community **hears** at some timestep. `"paths"` blocks position variables instead and permits relabellings of interchangeable aircraft. |
| `enumerateAtOptimum` | `true` | pins each raw principle metric and the arrival penalty, so the alternatives tie on every term at once |

At `enumerate: 0` the reply is unchanged, so client caches are unaffected; an older
server ignores the key and degrades to one answer. Replies carry `alternatives`,
`alternativesStatus` (`"limit"` / `"exhausted"` / `"timeout"`),
`alternativesDistinct` and `alternativesAtOptimum`. **`"exhausted"` is the strongest
outcome** — no other routing fits, so nothing about the answer was arbitrary.

Prefer `"counts"`. The 19-aircraft default demand has 1,658,880 relabellings per
routing and the solver has no symmetry-breaking constraint, so they are reachable;
measured, Z3 returned none at K up to 50, but `"paths"` did waste 2 of 50 slots at
K=50 on audibly identical routings, where `"counts"` wasted none.

## Reply fields

`status`, `paths`, `countMatrix`, `noiseMatrix` (M x T, the dB **increase** per
station per timestep), `T`, `T_used`, `T_min`, `arrivalPenalty`, `totalUtilNoise`,
`totalTransit`, `proximityCost`, `proximityMode`, `objectiveMode`, `optimality`,
`principleImposed`, `warning`, `notice`, and on failure `reason` plus a `detail`
naming the station that caused it.

Note `totalTransit` and `totalUtilNoise` appear only when the utilitarian objective
is on, and `arrivalPenalty` only when `weightTime > 0`.

## Things that will surprise you

- **`unsat` is not always a proof.** A timeout during `T` escalation is reported as
  `unsat` with a `detail` that says it timed out. Read the detail.
- **The served routing depends on the solver's request history.** The same payload
  posted three times to one process gave +6.02, +8.45 and +6.99 dB, each correctly
  `"optimal"`. A fresh process reproduces the sequence exactly, so Z3 is
  deterministic — state accumulates in the process-global context. Restart the
  process if you need run-to-run comparability.
- **Pre-departure waiting is free** in the noise objective (`moved` is false at the
  origin, so the aircraft is not active) but **mid-route hovering is not** — a
  holding aircraft stays active and keeps paying dB where it sits.
- **3 dB is infeasible on the 5x5 map.** A 45 dB tile admits zero aircraft at `D=3`
  (the first already adds 3.010), and station 5 is a 45 dB vertiport destination.

## Testing

Use Flask's `test_client()` rather than a port, so tests cannot collide with a
running server:

```python
import solver_server_dB as S
reply = S.app.test_client().post("/solve", json=payload).get_json()
```

The solver pool has historically leaked orphaned processes across sessions. Check
before assuming a port is free, and **never kill a Python process you did not
start** — sessions run concurrently.
