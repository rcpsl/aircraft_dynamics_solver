"""Second attempt at the CYO variants that phase 2 could not optimize in budget.

run_prioritarian_cyo.py leaves a file unwritten when phase 2 times out on all
three retry seeds, rather than cutting the fleet or falling back to a phase-1
route. This re-runs only those, with the phase-2 budget raised via a RUNTIME
attribute set on the imported module -- solver_server_dB.py is not edited.

Whether a larger budget helps is an open question and the answer is worth
recording either way: for people mode at N=14/T=5 it did not (1521 s failed
where 240 s failed), so a second no-result here would confirm that these solves
are hard rather than marginal.

Usage: python retry_cyo_unresolved.py [budget_seconds]
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _helpers45 as H

BUDGET_S = int(sys.argv[1]) if len(sys.argv) > 1 else 900
H.S.SOLVE_TIMEOUT_MS = BUDGET_S * 1000

from _paths45 import ROUTES  # noqa: E402
from _helpers45 import COMBOS  # noqa: E402
from run_prioritarian_cyo import (  # noqa: E402
    distinct_variants, variant_name, run_one, MODES,
)


def main():
    print(f"phase-2 budget raised to {BUDGET_S}s (runtime override)\n", flush=True)
    missing = []
    for combo in COMBOS:
        for mode in MODES:
            out_dir = ROUTES / combo / "prioritarian_cyo" / mode
            for (lens, prot), sels in sorted(distinct_variants(combo).items()):
                if not (out_dir / f"{variant_name(lens, prot)}.csv").exists():
                    missing.append((combo, mode, lens, prot, sels, out_dir))

    if not missing:
        print("nothing missing")
        return
    print(f"{len(missing)} unwritten variant(s):")
    for combo, mode, lens, prot, _, _ in missing:
        print(f"  {combo}/{mode}/{variant_name(lens, prot)}  {list(prot)}")
    print(flush=True)

    log = []
    for combo, mode, lens, prot, sels, out_dir in missing:
        print(f"--- {combo}/{mode} ---", flush=True)
        t0 = time.time()
        run_one(combo, mode, lens, prot, sels, out_dir, log)
        print(f"    ({time.time() - t0:.0f}s)", flush=True)

    still = [m for m in missing
             if not (m[5] / f"{variant_name(m[2], m[3])}.csv").exists()]
    print(f"\nstill unwritten after {BUDGET_S}s budget: {len(still)}")
    for combo, mode, lens, prot, _, _ in still:
        print(f"  {combo}/{mode}/{variant_name(lens, prot)}")


if __name__ == "__main__":
    main()
