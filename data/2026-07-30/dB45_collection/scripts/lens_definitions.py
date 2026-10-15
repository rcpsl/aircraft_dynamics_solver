"""Station -> community attribute map, derived from the workbook in code.

Replaces both the hand-transcribed prioritarian lens lists and
dB_target_sweeps/scripts/extract_station_income.py. That older module hardcodes
`SWAP = {6: 8, 8: 6}`, which is WRONG -- the station map audit established
strict row-major numbering over the `Dashboard Location` grid with no swap.
Station 6 is Dove Springs (Low income); station 8 is CYO slot B. The swap is
not reproduced here.

Nothing is transcribed: the grid is parsed, names are resolved against the
`Communities` and `Create Your Own` sheets, and the lenses fall out of column
selectors. Run this file directly to print the derived map and self-checks.

Usage: python lens_definitions.py
"""
import re
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths45 import COMMUNITIES_XLSX

# Workbook column order, shared by both community sheets (the CYO sheet omits
# the numeric noise_db column that the fixed sheet carries).
_COLS = ["num", "name", "narrative", "austin", "population", "income", "race",
         "life_stage", "housing", "transport", "employment", "land_use", "noise"]

CYO_MARKER = "create your own"


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _load_sheets():
    wb = openpyxl.load_workbook(COMMUNITIES_XLSX, data_only=True)
    fixed, cyo = {}, {}
    for sheet, sink in ((wb["Communities"], fixed),
                        (wb["Create Your Own Community Optio"], cyo)):
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if row[0] is None:
                continue
            rec = {k: _norm(v) for k, v in zip(_COLS, row)}
            sink[rec["name"].lower()] = rec
    grid = wb["Dashboard Location"]
    return fixed, cyo, grid


def _parse_grid(grid):
    """Row-major over the 4x4 `Dashboard Location` block -> {station: cell text}.

    Row 1 and column A are the grid's own 1..4 index labels, so the data block
    starts at B2. NO 6<->8 swap is applied.
    """
    cells = {}
    st = 0
    for r in range(2, 6):
        for c in range(2, 6):
            st += 1
            cells[st] = _norm(grid.cell(row=r, column=c).value)
    assert st == 16, f"expected a 4x4 grid, walked {st} cells"
    return cells


def build_station_map():
    """{station: {"kind": "fixed"|"cyo", "options": [attr_dict, ...]}}.

    Fixed stations have exactly one option; CYO stations have two, in the
    order the grid cell lists them (index 0 = the default).
    """
    fixed, cyo, grid = _load_sheets()
    cells = _parse_grid(grid)
    out = {}
    for st, text in cells.items():
        if text.lower().startswith(CYO_MARKER):
            # "Create Your Own 2: A OR B" -- options split on " OR "
            body = text.split(":", 1)[1]
            names = [_norm(p) for p in re.split(r"\bOR\b", body)]
            opts = []
            for nm in names:
                rec = cyo.get(nm.lower())
                assert rec is not None, f"station {st}: no CYO row named {nm!r}"
                opts.append(rec)
            assert len(opts) == 2, f"station {st}: expected 2 CYO options"
            out[st] = {"kind": "cyo", "options": opts}
        else:
            # "Downtown - Loud 65 db" -- name is everything before " - "
            nm = _norm(text.split(" - ")[0])
            rec = fixed.get(nm.lower())
            assert rec is not None, f"station {st}: no community named {nm!r}"
            out[st] = {"kind": "fixed", "options": [rec]}
    return out


STATION_MAP = build_station_map()
CYO_SLOTS = sorted(st for st, v in STATION_MAP.items() if v["kind"] == "cyo")
FIXED_STATIONS = sorted(st for st, v in STATION_MAP.items() if v["kind"] == "fixed")


def attrs_for(station, cyo_choices=None):
    """Attribute row for a station under a CYO selection ({station: 0|1})."""
    entry = STATION_MAP[station]
    if entry["kind"] == "fixed":
        return entry["options"][0]
    return entry["options"][(cyo_choices or {}).get(station, 0)]


# ---------------------------------------------------------------- selectors

def _is_low_income(a):
    return a["income"].lower() == "low"


def _is_poc(a):
    """Race is neither Mixed nor Mostly white -- i.e. a majority community of
    colour. Covers 'Mostly hispanic', 'Mostly Black', 'Mostly Asian'."""
    r = a["race"].lower()
    return r not in ("mixed", "") and "white" not in r


def _is_transit_desert(a):
    return a["transport"].lower() == "desert"


def _has_few_jobs(a):
    return a["employment"].lower().startswith("few local jobs")


SELECTORS = {
    "low_income":      ("Income == Low", _is_low_income),
    "people_of_color": ("Race not Mixed and not Mostly white", _is_poc),
    "transit_desert":  ("Transport == Desert", _is_transit_desert),
    "few_jobs":        ('Employment == "Few local jobs"', _has_few_jobs),
}


def lens_stations(lens, cyo_choices=None, include_cyo=False):
    """Stations selected by `lens`.

    include_cyo=False (the default, and what the solve runs) restricts the lens
    to the twelve fixed communities, so the protected set does not move with a
    participant's CYO picks. include_cyo=True shows what the lens WOULD gain --
    see cyo_sensitivity().
    """
    _, pred = SELECTORS[lens]
    pool = sorted(STATION_MAP) if include_cyo else FIXED_STATIONS
    return [st for st in pool if pred(attrs_for(st, cyo_choices))]


def cyo_sensitivity():
    """{lens: {station: [option names that would add it]}} -- the disclosure
    surface for freezing the lenses to fixed communities."""
    out = {}
    for lens, (_, pred) in SELECTORS.items():
        hits = {}
        for st in CYO_SLOTS:
            names = [o["name"] for i, o in enumerate(STATION_MAP[st]["options"])
                     if pred(o)]
            if names:
                hits[st] = names
        out[lens] = hits
    return out


LENSES = {lens: lens_stations(lens) for lens in SELECTORS}


# --------------------------------------------- income map (proportional domain)

def build_station_income(cyo_choices=None):
    """{station: 'High'|'Medium'|'Low'} for all 16 stations. No SWAP."""
    return {st: attrs_for(st, cyo_choices)["income"].title()
            for st in sorted(STATION_MAP)}


def build_station_population(cyo_choices=None):
    return {st: attrs_for(st, cyo_choices)["population"].title()
            for st in sorted(STATION_MAP)}


def people_weights(cyo_choices=None):
    """Regenerates PEOPLE_WEIGHTS: High=10 / Medium=5 / Low=1, CYO slots
    pinned to a neutral 5 regardless of the option chosen."""
    tier = {"High": 10, "Medium": 5, "Low": 1}
    pop = build_station_population(cyo_choices)
    return [5 if st in CYO_SLOTS else tier[pop[st]] for st in sorted(STATION_MAP)]


if __name__ == "__main__":
    print(f"CYO slots: {CYO_SLOTS}\n")
    print(f"{'St':>3}  {'Occupant':<44} {'Pop':<7} {'Income':<7} {'Race':<15} "
          f"{'Transport':<9} {'Employment'}")
    for st in sorted(STATION_MAP):
        e = STATION_MAP[st]
        if e["kind"] == "cyo":
            occ = "CYO: " + " / ".join(o["name"] for o in e["options"])
        else:
            occ = e["options"][0]["name"]
        a = attrs_for(st)
        print(f"{st:>3}  {occ[:44]:<44} {a['population']:<7} {a['income']:<7} "
              f"{a['race']:<15} {a['transport']:<9} {a['employment']}")

    print("\nLenses (fixed communities only):")
    for lens, (desc, _) in SELECTORS.items():
        print(f"  {lens:<16} {str(LENSES[lens]):<26} {desc}")

    print("\nCYO sensitivity -- slots each lens would gain if CYO were included:")
    for lens, hits in cyo_sensitivity().items():
        if hits:
            for st, names in hits.items():
                print(f"  {lens:<16} +station {st} under {' / '.join(names)}")
        else:
            print(f"  {lens:<16} (none)")

    from _helpers45 import PEOPLE_WEIGHTS
    derived = people_weights()
    print(f"\nPEOPLE_WEIGHTS self-check: derived == hardcoded -> "
          f"{derived == PEOPLE_WEIGHTS}")
    if derived != PEOPLE_WEIGHTS:
        print(f"  derived   = {derived}")
        print(f"  hardcoded = {PEOPLE_WEIGHTS}")

    print("\nIncome map (no SWAP):")
    print(" ", build_station_income())
