"""Canonical roots for the 45 dB collection.

Mirrors dB_target_sweeps/scripts/_paths.py, but rooted at dB45_collection/ and
with NO path pointing into the 55 dB collection's data. The only thing shared
with the older collection is the repo-root solver itself, which is never
modified.

Everything is derived from this file's own position, so moving or cloning the
repo does not break the scripts.
"""
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent          # dB45_collection/scripts
COLLECTION = SCRIPTS.parent                        # dB45_collection
REPO = COLLECTION.parent                           # repo root (holds solver_server_dB.py)

DATA = COLLECTION / "data"
ROUTES = DATA / "full_routes"                      # final route-enriched CSVs
BASE_MODEL = DATA / "base_model"                   # xlsx + 45 dB config
PROBES = DATA / "probes"                           # phase-1 feasibility / degeneracy searches
PARAMS = DATA / "params"                           # chosen ladders, emitted by the probe stage
SUMMARIES = DATA / "summaries"

CONFIG_JSON = BASE_MODEL / "uam-config_45dB.json"
COMMUNITIES_XLSX = BASE_MODEL / "Sample Communities.xlsx"

DB_PER_CRAFT = 45  # the whole point of this collection; asserted against the config on load
