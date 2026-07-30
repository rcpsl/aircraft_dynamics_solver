"""Canonical roots for every script in this folder.

All scripts here were originally written to live *inside* the data folders they
read and write (`dB_target_sweeps/`, `dB_target_sweeps/full_routes/`,
`.../equal_allocation/alt_selection_maxdemand/`) and derived their paths from
`Path(__file__).parent`. They now all live in `scripts/`, so those relative
assumptions no longer hold — every path they need is defined once here instead.

Nothing is hardcoded to an absolute location: everything is derived from this
file's own position, so moving or cloning the repo does not break the scripts.
"""
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent          # dB_target_sweeps/scripts
SWEEPS = SCRIPTS.parent                            # dB_target_sweeps
REPO = SWEEPS.parent                               # repo root (holds solver_server_dB.py)

DATA = SWEEPS / "data"
ROUTES = DATA / "full_routes"                      # route-enriched CSVs (primary dataset)
AGG = DATA / "aggregate_only"                      # original zone-summary-only CSVs
BASE_MODEL = DATA / "base_model"                   # xlsx + uam-config_finalized.json
SUMMARIES = DATA / "summaries"                     # derived cross-scenario tables
DASHBOARDS = SWEEPS / "dashboards"
REPORTS = SWEEPS / "reports"

CONFIG_JSON = BASE_MODEL / "uam-config_finalized.json"
COMMUNITIES_XLSX = BASE_MODEL / "Sample Communities.xlsx"
