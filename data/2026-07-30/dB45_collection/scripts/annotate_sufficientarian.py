"""Retrofit preamble keys into sufficientarian CSVs written before those keys
were added to run_sufficientarian.py.

Two keys were added after some files had already been solved:

  capBehaviourWarning -- the cap-riding caveat, discovered only once D=8 and
                         D=18 could be compared.
  phase2TimeoutMs     -- which phase-2 budget the cell actually solved under.
                         This one matters for provenance: four `weighted` cells
                         only solved after the budget was raised to 900000 ms,
                         and a cell that needed a raised budget is not the same
                         evidence as one that solved under the default. Files
                         written by the raised-budget run already carry the key
                         with the correct value, so they are skipped here and
                         only the default-budget files get 240000.

Re-solving purely to add preamble lines would risk Z3 returning a different
(equally optimal) routing and would make the collection internally inconsistent
for no gain, so lines are inserted textually -- solved data is untouched.

Values are IMPORTED from run_sufficientarian rather than copied, so retrofitted
and freshly generated files carry byte-identical text with no second copy to
drift. Insertion anchors match the order the generator emits, so a retrofitted
file is indistinguishable from a fresh one.

Idempotent: a file that already has a key is left alone for that key.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths45 import ROUTES
from run_sufficientarian import CAP_BEHAVIOUR_WARNING, DEFAULT_PHASE2_TIMEOUT_MS

# (key, value, anchor key) -- inserted immediately after the anchor line, which
# is where run_sufficientarian's meta dict puts it.
RETROFITS = [
    ("capBehaviourWarning", CAP_BEHAVIOUR_WARNING, "objectiveNote"),
    ("phase2TimeoutMs", DEFAULT_PHASE2_TIMEOUT_MS, "fullFleetFeasible"),
]


def annotate(path):
    lines = path.read_text(encoding="utf-8").split("\n")
    actions = []
    for key, value, anchor in RETROFITS:
        if any(line.startswith(f"# {key},") for line in lines):
            actions.append(f"{key}=present")
            continue
        for i, line in enumerate(lines):
            if line.startswith(f"# {anchor},"):
                lines.insert(i + 1, f"# {key},{value}")
                actions.append(f"{key}=ADDED")
                break
        else:
            actions.append(f"{key}=NO-ANCHOR")
    if any("ADDED" in a for a in actions):
        path.write_text("\n".join(lines), encoding="utf-8")
    return ", ".join(actions)


def main():
    files = sorted(ROUTES.glob("*/sufficientarian/*/D*.csv"))
    if not files:
        print("no sufficientarian CSVs found")
        return
    for p in files:
        print(f"{annotate(p):<52} {p.relative_to(ROUTES)}")
    print(f"\n{len(files)} file(s) processed")


if __name__ == "__main__":
    main()
