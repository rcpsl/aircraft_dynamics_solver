"""Extract per-station Income (High/Medium/Low) from `Sample Communities.xlsx`.

Income is the one input the proportional *benefit* rule needs that the noise
domains never used. It is NOT in uam-config_finalized.json (which only has
baselines/populations/adjacency), so it must come from the workbook.

This reads the workbook authoritatively rather than hand-transcribing:
  1. Communities sheet         -> {External Name -> Income}
  2. CYO options sheet         -> {External Name -> Income} for the 8 slot options
  3. Dashboard Location sheet  -> row-major 4x4 grid -> {station -> community/CYO slot}
  4. Applies the documented station 6<->8 swap (DASHBOARD_DATA_INTEGRATION.md §1):
     the grid literally puts Dove Springs at 6 and CYO-B at 8, but the solver
     dataset sweeps station 6's baseline (55<->45), which only makes sense as the
     CYO-B International(55)/Exurban(45) choice. The data is authoritative, so the
     benefit map follows it: CYO-B at station 6, Dove Springs at station 8.

CYO slots (stations 2, 6, 11, 13) have two options; income can differ between
them (slots 11 and 13 do). `station_income(combo, cyo_choices)` resolves them;
`STATION_INCOME_DEFAULT` uses each slot's first option.
"""
import re
from pathlib import Path
import openpyxl

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import COMMUNITIES_XLSX as XLSX

# Documented placement fix: swap grid positions 6 and 8 (1-indexed).
SWAP = {6: 8, 8: 6}


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def _income_by_name():
    wb = openpyxl.load_workbook(XLSX, data_only=True)
    inc = {}
    for sheet in ("Communities", "Create Your Own Community Optio"):
        rows = list(wb[sheet].iter_rows(values_only=True))
        hdr = [(_norm(c)) for c in rows[0]]
        name_i, inc_i = hdr.index("external name"), hdr.index("income")
        for r in rows[1:]:
            if r[name_i] is None:
                continue
            inc[_norm(r[name_i])] = str(r[inc_i]).strip().capitalize()  # High/Medium/Low
    return inc


def _grid_stations():
    """Return {station(1-16) -> {'kind','options':[names]}} from the grid, pre-swap."""
    wb = openpyxl.load_workbook(XLSX, data_only=True)
    ws = wb["Dashboard Location"]
    # Data grid is the 4 rows x 4 cols block whose corner label is 1..4 both ways.
    grid_rows = [r for r in ws.iter_rows(values_only=True)
                 if r[0] in (1.0, 2.0, 3.0, 4.0)]
    stations = {}
    st = 1
    for r in grid_rows:
        for cell in r[1:5]:
            text = str(cell or "")
            if text.lower().startswith("create your own"):
                # "Create Your Own N:\nOption A\nOR Option B"
                body = text.split(":", 1)[1]
                opts = [o.strip() for o in re.split(r"\bOR\b", body) if o.strip()]
                stations[st] = {"kind": "cyo", "options": opts}
            else:
                # "Name - Loud 65 db" -> "Name"
                name = text.split(" - ")[0].strip()
                stations[st] = {"kind": "fixed", "options": [name]}
            st += 1
    return stations


def _match_income(name, inc_map):
    n = _norm(name)
    if n in inc_map:
        return inc_map[n]
    # options in the grid may be abbreviated; fall back to substring match
    for k, v in inc_map.items():
        if n in k or k in n:
            return v
    raise KeyError(f"no income found for community {name!r}")


def build_station_income(cyo_choices=None):
    """station(1-16) -> Income. cyo_choices maps station->0/1 (which CYO option);
    default 0 = first listed option. Returns dict keyed 1..16."""
    cyo_choices = cyo_choices or {}
    inc_map = _income_by_name()
    grid = _grid_stations()
    # apply the 6<->8 swap
    swapped = dict(grid)
    for a, b in SWAP.items():
        swapped[a] = grid[b]
    out = {}
    for st in range(1, 17):
        cell = swapped[st]
        pick = cyo_choices.get(st, 0) if cell["kind"] == "cyo" else 0
        name = cell["options"][pick]
        out[st] = _match_income(name, inc_map)
    return out


STATION_INCOME_DEFAULT = None  # populated on import below
try:
    STATION_INCOME_DEFAULT = build_station_income()
except Exception:  # keep import cheap/safe; callers can call the fn explicitly
    pass


if __name__ == "__main__":
    grid = _grid_stations()
    swapped = dict(grid)
    for a, b in SWAP.items():
        swapped[a] = grid[b]
    inc = build_station_income()
    print(f"{'St':>2}  {'Income':<7}  Community / CYO options")
    print("-" * 60)
    for st in range(1, 17):
        cell = swapped[st]
        tag = "(CYO)" if cell["kind"] == "cyo" else "     "
        print(f"{st:>2}  {inc[st]:<7}  {tag} {' / '.join(cell['options'])}")
