"""Final targeted retry for files that consistently time out at ~240s across
multiple identical attempts (contention-independent -- same near-240s wall
every time, suggesting they're just barely over budget, not intractable).

Overrides solver_server_dB.SOLVE_TIMEOUT_MS for THIS PROCESS ONLY (a module-
level global resolved at call time -- no edit to the actual solver_server_dB.py
file on disk, no effect on any other process/consumer of that module).

Usage: python retry_extended_timeout.py <combo> [timeout_ms]
(run_combo.py already skips existing files, so this only attempts whatever's
still missing for that combo. timeout_ms defaults to 420000 (420s).)
"""
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import REPO
sys.path.insert(0, str(REPO))
import solver_server_dB as S
S.SOLVE_TIMEOUT_MS = int(sys.argv[2]) if len(sys.argv) > 2 else 420000  # this process only

sys.argv = ["run_combo.py", sys.argv[1]]
runpy.run_path(str(Path(__file__).resolve().parent / "run_combo.py"), run_name="__main__")
