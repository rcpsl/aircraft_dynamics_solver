dB_target_sweeps/ -- quick orientation
=======================================

Start here: DASHBOARD_DATA_INTEGRATION.md
  The full wiring guide (station numbering, community/people toggle,
  control-state -> file lookup table).

To actually use the data:
  dashboard_data.json   -- everything precomputed into one blob (already
                           inlined into fairness-dashboard-v2.html). Load
                           this if you just need the numbers.
  build_dashboard_data.py -- rebuilds that blob from the raw CSVs below,
                           in case anything changes.

Reference working dashboard:
  fairness-dashboard-v2.html -- a live prototype already wired to this
                           exact dataset; use it as a wiring example.

Raw data, by fairness principle (each has its own README.md/REPORT.md
with exact solver config + findings):
  equal_allocation/   -- split by 4 baseline combos x community/people counting
  sufficientarian/    -- same split
  utilitarian/        -- same split
  prioritarian/       -- step3_baseline_sweep/<combo>/{community,people}/<lens>.csv
                         read REPORT.md sec 5b/5d before trusting numbers here --
                         fleet size differs between the two modes (N=14 vs N=7)

Base model:
  Sample Communities.xlsx -- the 16 Austin communities + 8 "choose your own"
                         options the dashboard's community picker is built from
