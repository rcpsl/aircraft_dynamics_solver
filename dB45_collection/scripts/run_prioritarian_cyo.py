"""Prioritarian with CYO picks feeding lens membership -- all variants.

The shipped domain freezes lenses to the twelve fixed communities
(lens_stations(..., include_cyo=False)), so a participant's Create-Your-Own
picks cannot move protectedStations. That is what makes 3 of 4 lenses
degenerate: their protected sets sit entirely off the only shortest path
1-6-11-16, so the objective is satisfied at zero before the solver starts.

Here include_cyo=True. CYO slots 6 and 11 are ON that path, so lenses that gain
them acquire something real to trade against.

WHAT A PARTICIPANT ACTUALLY CONTROLS. Four CYO slots, two options each:

  slot A  station 2  Historic Black Neighborhood (Moderate=55) | New High-Density Development (Loud=65)
  slot B  station 6  International District (Moderate=55)      | Exurban Commuter Town (Quiet=45)
  slot C  station 11 Working-Class Homeowner (Moderate=55)     | Suburban Tech Campus (Moderate=55)
  slot D  station 13 Retirement Community (Quiet=45)           | Quiet Rural Low-Income (Quiet=45)

Baseline dB comes from the workbook's own noise word (Loud=65 / Moderate=55 /
Quiet=45, verified against the twelve fixed stations), not from the combo name.
Slots A and B move a baseline; C and D never do. So A x B ARE the four existing
combos -- and, crucially, A and B are not independent knobs: each picks a
baseline AND a community at once. s6-45 necessarily installs the Exurban
Commuter Town, dropping station 6 into transit_desert and few_jobs; s6-55
installs the International District, dropping it into people_of_color. The
combo therefore decides which lenses can bind.

DEDUPLICATION. A solve is fully determined by (baseline, protectedStations,
mode). The 16 CYO selections x 4 lenses x 2 modes = 128 nominal variants
collapse to 36 x 2 = 72 distinct solves. Files are named by what the lens
GAINED from CYO, and cyo_selection_map.csv maps all 128 selections onto them,
so a dashboard can look up any pick without this script duplicating data.

A CAVEAT THAT LIMITS people MODE. people runs at T_max=4, the phase-1 floor,
where exactly one 1->16 path exists and the routing is FORCED. Enlarging a
protected set changes the reported protectedNoise there but cannot change the
routing -- nothing can. Only community mode (T_max=5, 16 four-hop paths) has
the freedom to respond to a lens at all. Expect people-mode files to stay
uniform across lenses; that is structural, not a lens finding.

PEOPLE_WEIGHTS is left as imported, with CYO slots pinned to a neutral 5. Note
the tension: once CYO picks feed lens membership it is arguably inconsistent to
keep them neutral in the population weighting (slot A's two options are Medium
vs High population). Changing that is a separate decision and would multiply
the variant count again, so it is flagged rather than done.

Usage:
    python run_prioritarian_cyo.py <combo> [--mode community|people|both]
    python run_prioritarian_cyo.py all
"""
import itertools
import sys
import time
from pathlib import Path

import z3

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths45 import ROUTES, SUMMARIES
from _helpers45 import (
    BASE_DEFAULT, COMBOS, demand_pct, solve_scenario, metric_maxima,
    write_full_csv, travel_stats, subsample_fleet,
)
from lens_definitions import LENSES, SELECTORS, CYO_SLOTS, STATION_MAP, lens_stations
from run_prioritarian import (
    D_FIXED, U_FIXED, W_TIME, W_PRIOR, T_FLOOR, RETRY_SEEDS, MODES,
)

NOISE_DB = {"loud": 65, "moderate": 55, "moderat": 55, "quiet": 45}
ON_PATH = {1, 6, 11, 16}   # stations no 1<->16 routing can avoid


def baseline_for_cyo(choices):
    b = list(BASE_DEFAULT)
    for st in CYO_SLOTS:
        b[st - 1] = NOISE_DB[STATION_MAP[st]["options"][choices[st]]["noise"].strip().lower()]
    return b


def combo_of(choices):
    b = baseline_for_cyo(choices)
    return f"s2-{b[1]}_s6-{b[5]}"


def all_cyo_selections():
    for bits in itertools.product([0, 1], repeat=len(CYO_SLOTS)):
        yield dict(zip(CYO_SLOTS, bits))


def variant_name(lens, protected):
    """File stem: what CYO added to this lens. Stable and self-describing."""
    gained = sorted(set(protected) - set(LENSES[lens]))
    return f"{lens}__gain_{'_'.join(map(str, gained)) if gained else 'none'}"


def distinct_variants(combo):
    """-> {(lens, protected_tuple): [cyo selections that produce it]} for `combo`."""
    out = {}
    for ch in all_cyo_selections():
        if combo_of(ch) != combo:
            continue
        for lens in LENSES:
            prot = tuple(lens_stations(lens, ch, include_cyo=True))
            out.setdefault((lens, prot), []).append(dict(ch))
    return out


def run_one(combo, mode, lens, protected, selections, out_dir, log):
    path = out_dir / f"{variant_name(lens, protected)}.csv"
    if path.exists():
        print(f"  skip {path.name} (exists)", flush=True)
        return

    spec = MODES[mode]
    n, mult, t_max, flags = spec["n"], spec["mult"], spec["t_max"], spec["flags"]
    start, end = subsample_fleet(n)
    baseline = baseline_for_cyo(selections[0])
    prot = list(protected)

    t0 = time.time()
    r = solve_scenario(n, D_FIXED, U_FIXED, t_max, baseline, mult, start, end,
                       protected_stations=prot, w_time=W_TIME, **flags)
    dt = time.time() - t0
    status = r.get("status")
    log.append(f"{mode},{lens},\"{prot}\",{status},{r.get('reason','')},"
               f"{r.get('protectedNoise','')},{dt:.1f}")

    # Phase-2 timeout is a budget limit, not infeasibility. Reseed; never cut fleet.
    if status == "phase2_failed":
        for seed in RETRY_SEEDS:
            z3.set_param("smt.random_seed", seed)
            z3.set_param("sat.random_seed", seed)
            t1 = time.time()
            r = solve_scenario(n, D_FIXED, U_FIXED, t_max, baseline, mult, start,
                               end, protected_stations=prot, w_time=W_TIME, **flags)
            log.append(f"{mode},{lens},\"{prot}\",{r.get('status')},"
                       f"seed{seed}:{r.get('reason','')},"
                       f"{r.get('protectedNoise','')},{time.time() - t1:.1f}")
            print(f"  {path.stem:<34} retry seed={seed} -> {r.get('status')}",
                  flush=True)
            if r.get("status") == "sat":
                break
        z3.set_param("smt.random_seed", 0)
        z3.set_param("sat.random_seed", 0)
        status = r.get("status")
        if status != "sat":
            print(f"  {path.stem:<34} PHASE-2 UNRESOLVED -- not written, "
                  f"demand NOT cut", flush=True)
            return

    if status != "sat":
        print(f"  {path.stem:<34} {status}/{r.get('reason','')} -- not written",
              flush=True)
        return

    pn = r.get("protectedNoise")
    mx_avg, mx_peak = metric_maxima(r, baseline)
    avg_tt, _, _ = travel_stats(r["paths"], mult, start, end, r["T"])
    gained = sorted(set(prot) - set(LENSES[lens]))
    meta = {
        "domain": "prioritarian_cyo", "combo": combo, "mode": mode, "lens": lens,
        "protectedStations": prot,
        "lensSelector": SELECTORS[lens][0].replace(",", ";"),
        "lensIncludesCyo": True,
        "lensFrozenStations": list(LENSES[lens]),
        "lensGainedFromCyo": gained,
        # Only stations on the unique shortest path can force a trade-off.
        "gainedOnPathStations": sorted(set(gained) & ON_PATH),
        "cyoSlots": CYO_SLOTS,
        "cyoSelectionsMappingHere": [
            "".join(str(s[st]) for st in CYO_SLOTS) for s in selections],
        "cyoSlotOrder": "".join(f"st{st}," for st in CYO_SLOTS).rstrip(","),
        "protectedNoise": pn,
        "protectedNoiseDegenerate": (pn == 0.0),
        "D": D_FIXED, "Dbinding": False,
        "U": U_FIXED, "Ubinding": False,
        "hardT": False, "T_max": t_max, "T_floor": T_FLOOR,
        "routingForcedByT": r["T"] <= T_FLOOR,
        "weightTime": W_TIME,
        "optimizePrioritarian": True, "weightPrioritarian": W_PRIOR,
        "optimizeUtilitarian": flags.get("optimize_util", False),
        "maxAvgAddedDb": round(mx_avg, 4),
        "maxPeakAddedDb": round(mx_peak, 4),
        "demandRole": "share of the 56-unit base fleet modelled; not unserved demand",
        "avgAddedDbComparability": f"averaged over T={r['T']}; compare modes on peak, not avg",
    }
    if flags.get("optimize_util"):
        meta["weightUtilitarian"] = flags["w_util"]
        meta["stationTransitWeights"] = flags["station_transit_weights"]

    write_full_csv(path, meta, r["paths"], mult, start, end,
                   r["countMatrix"], r["noiseMatrix"], baseline, r["T"])
    tag = "  [DEGENERATE]" if pn == 0.0 else ""
    print(f"  {path.stem:<34} protNoise={pn:<8} avg={mx_avg:6.3f} "
          f"peak={mx_peak:6.3f} T={r['T']} ({dt:.0f}s){tag}", flush=True)


def run(combo, mode):
    out_dir = ROUTES / combo / "prioritarian_cyo" / mode
    out_dir.mkdir(parents=True, exist_ok=True)
    variants = distinct_variants(combo)
    print(f"\n=== {combo} / {mode}: {len(variants)} distinct variants "
          f"(N={MODES[mode]['n']}, T_max={MODES[mode]['t_max']}, "
          f"demand={demand_pct(MODES[mode]['mult'])}%) ===", flush=True)
    log = []
    t0 = time.time()
    for (lens, prot), sels in sorted(variants.items()):
        run_one(combo, mode, lens, prot, sels, out_dir, log)
    log_dir = out_dir / "_search_log"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "attempts.csv").write_text(
        "mode,lens,protectedStations,status,reason,protectedNoise,elapsed_s\n"
        + "\n".join(log) + "\n", encoding="utf-8")
    print(f"=== {combo}/{mode} done in {time.time() - t0:.0f}s ===", flush=True)


def write_selection_map():
    """All 128 (cyo selection, lens, mode) -> the file that answers it."""
    rows = ["cyoSelection,st2,st6,st11,st13,combo,mode,lens,protectedStations,"
            "gainedFromCyo,file"]
    for ch in all_cyo_selections():
        combo = combo_of(ch)
        key = "".join(str(ch[st]) for st in CYO_SLOTS)
        for mode in MODES:
            for lens in LENSES:
                prot = lens_stations(lens, ch, include_cyo=True)
                gained = sorted(set(prot) - set(LENSES[lens]))
                rows.append(
                    f"{key},{ch[2]},{ch[6]},{ch[11]},{ch[13]},{combo},{mode},"
                    f"{lens},\"{prot}\",\"{gained}\","
                    f"{combo}/prioritarian_cyo/{mode}/{variant_name(lens, prot)}.csv")
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    out = SUMMARIES / "cyo_selection_map.csv"
    out.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"-> {out} ({len(rows) - 1} selections mapped)")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mode = "both"
    if "--mode" in sys.argv:
        mode = sys.argv[sys.argv.index("--mode") + 1]
    modes = list(MODES) if mode == "both" else [mode]
    combos = COMBOS if (not args or args[0] == "all") else [args[0]]
    for combo in combos:
        for m in modes:
            run(combo, m)
    write_selection_map()


if __name__ == "__main__":
    main()
