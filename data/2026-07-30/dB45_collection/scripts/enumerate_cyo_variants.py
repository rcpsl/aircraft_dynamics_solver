"""Do the CYO picks change the prioritarian domain? Enumerate, dedupe, report.

As shipped: NO. lens_stations() defaults to include_cyo=False, so protected sets
are drawn only from the twelve fixed communities and a participant's CYO picks
cannot move them. Slots A/B (stations 2/6) still change the BASELINE -- they are
the four combos -- but slots C/D (stations 11/13) change nothing at all.

With include_cyo=True the picks become load-bearing, and that matters here
specifically because CYO slots 6 and 11 sit ON the only shortest path
(1-6-11-16). Every lens that gains one of them stops being degenerate.

The coupling that makes this non-obvious: slots A and B choose a baseline AND a
community at once. They are not independent knobs. Picking s6-45 necessarily
installs the Exurban Commuter Town at station 6 (Quiet=45 dB, Transport=Desert,
Few local jobs), which drops station 6 into transit_desert and few_jobs. Picking
s6-55 installs the International District instead (Moderate=55, Mostly Asian),
which drops station 6 into people_of_color. So the combo you pick decides which
lenses can bind.

Baseline dB is derived from the workbook's own noise word (Loud=65 / Moderate=55
/ Quiet=45, established against the twelve fixed stations), not assumed from the
combo name.

A solve is fully determined by (baseline, protectedStations, mode), so many of
the 16 x 4 x 2 = 128 nominal variants collapse. This prints the distinct set.

Usage: python enumerate_cyo_variants.py
"""
import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _helpers45 import BASE_DEFAULT
from lens_definitions import (
    LENSES, SELECTORS, CYO_SLOTS, STATION_MAP, lens_stations,
)

NOISE_DB = {"loud": 65, "moderate": 55, "moderat": 55, "quiet": 45}
MODES = ["community", "people"]


def baseline_for_cyo(choices):
    """Baseline vector implied by a CYO selection, from the workbook noise word."""
    b = list(BASE_DEFAULT)
    for st in CYO_SLOTS:
        word = STATION_MAP[st]["options"][choices[st]]["noise"].strip().lower()
        b[st - 1] = NOISE_DB[word]
    return b


def combo_name(choices):
    """The existing four-combo label, derived from slots A/B rather than assumed."""
    b = baseline_for_cyo(choices)
    return f"s2-{b[1]}_s6-{b[5]}"


def all_choices():
    for bits in itertools.product([0, 1], repeat=len(CYO_SLOTS)):
        yield dict(zip(CYO_SLOTS, bits))


def main():
    print("CYO slots:", CYO_SLOTS)
    print(f"{2 ** len(CYO_SLOTS)} CYO selections x {len(LENSES)} lenses "
          f"x {len(MODES)} modes = "
          f"{2 ** len(CYO_SLOTS) * len(LENSES) * len(MODES)} nominal variants\n")

    # Does any slot move a baseline?
    movers = []
    for st in CYO_SLOTS:
        dbs = {NOISE_DB[o["noise"].strip().lower()]
               for o in STATION_MAP[st]["options"]}
        movers.append((st, sorted(dbs)))
    print("baseline effect per slot:")
    for st, dbs in movers:
        print(f"  station {st:>2}: {dbs}  "
              f"{'MOVES baseline' if len(dbs) > 1 else 'no dB change'}")
    print()

    rows = []
    for ch in all_choices():
        combo = combo_name(ch)
        base = baseline_for_cyo(ch)
        for lens in LENSES:
            frozen = lens_stations(lens, ch, include_cyo=False)
            withcyo = lens_stations(lens, ch, include_cyo=True)
            rows.append((ch, combo, tuple(base), lens, tuple(frozen), tuple(withcyo)))

    # As shipped: does the CYO pick change anything a solve can see?
    frozen_keys = {(r[2], r[3], r[4]) for r in rows}
    cyo_keys = {(r[2], r[3], r[5]) for r in rows}
    print(f"distinct (baseline, lens, protectedStations) solves")
    print(f"  include_cyo=False (as shipped): {len(frozen_keys)}  "
          f"-> x{len(MODES)} modes = {len(frozen_keys) * len(MODES)} files")
    print(f"  include_cyo=True             : {len(cyo_keys)}  "
          f"-> x{len(MODES)} modes = {len(cyo_keys) * len(MODES)} files")
    print()

    print("Per lens, protected sets under include_cyo=True "
          "(* = contains an on-path station 1/6/11/16, so it can bind):")
    on_path = {1, 6, 11, 16}
    for lens in LENSES:
        seen = {}
        for r in rows:
            if r[3] != lens:
                continue
            seen.setdefault((r[1], r[5]), r[0])
        print(f"\n  {lens}   frozen={list(LENSES[lens])}   [{SELECTORS[lens][0]}]")
        for (combo, prot), ch in sorted(seen.items()):
            mark = "*" if on_path & set(prot) else " "
            gained = sorted(set(prot) - set(LENSES[lens]))
            print(f"   {mark} {combo:<14} {str(list(prot)):<28} "
                  f"gains {gained if gained else '-'}")

    print("\n\nDistinct solves needed with include_cyo=True, per mode:")
    for base, lens, prot in sorted(cyo_keys, key=lambda k: (k[1], k[2])):
        combo = f"s2-{base[1]}_s6-{base[5]}"
        mark = "*" if on_path & set(prot) else " "
        print(f"  {mark} {combo:<14} {lens:<16} {list(prot)}")


if __name__ == "__main__":
    main()
