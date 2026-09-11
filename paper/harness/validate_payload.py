"""Check payload.py against the REAL buildSolveRequest from the shipped dashboard.

payload.py is a hand port, and everything in this paper is measured through it, so a
silent divergence would invalidate every result. This compares the two field by field
across configurations spanning all five principles, both `who` settings, and two
Proportional rankings.

Run `node extract_js.js` first (or let this script do it) to regenerate
js_payloads.json from the dashboard HTML.

usage: python validate_payload.py        exit 0 iff there are zero mismatches
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import payload as P

JS = os.path.join(HERE, "js_payloads.json")

# key in js_payloads.json  ->  kwargs for payload.build_request
CASES = {
    "equal|communities|10||true":
        dict(principle="equal", who="communities", limit=10),
    "equal|people|5||true":
        dict(principle="equal", who="people", limit=5),
    "sufficientarian|communities|10||true":
        dict(principle="sufficientarian", who="communities", limit=10),
    "sufficientarian|people|5||true":
        dict(principle="sufficientarian", who="people", limit=5),
    "prioritarian|communities|10||true":
        dict(principle="prioritarian", who="communities", limit=10,
             protected=(15, 19, 24)),
    "prioritarian|people|10||true":
        dict(principle="prioritarian", who="people", limit=10,
             protected=(15, 19, 24)),
    "utilitarian|communities|10||true":
        dict(principle="utilitarian", who="communities", limit=10),
    "utilitarian|people|10||true":
        dict(principle="utilitarian", who="people", limit=10),
    "proportional|communities|10|income-ambient-distance-population|true":
        dict(principle="proportional"),
    "proportional|communities|10|distance-population-income-ambient|false":
        dict(principle="proportional",
             prop_order=("distance", "population", "income", "ambient"),
             prop_population=False),
}


def main():
    if not os.path.exists(JS):
        print("regenerating js_payloads.json from the dashboard HTML ...")
        subprocess.run(["node", os.path.join(HERE, "extract_js.js")], cwd=HERE, check=True)
    js = json.load(open(JS, encoding="utf-8"))

    bad = 0
    for key, kw in CASES.items():
        if key not in js:
            print(f"MISSING  {key}")
            bad += 1
            continue
        a, b = dict(js[key]), P.build_request(**kw)
        # timeoutMs is set by the harness per run, not by the dashboard's builder.
        a.pop("timeoutMs", None)
        b.pop("timeoutMs", None)
        diff = [k for k in set(a) | set(b) if a.get(k) != b.get(k)]
        if diff:
            bad += 1
            print(f"DIFF     {key}: {diff}")
            for k in diff:
                print(f"    js: {str(a.get(k))[:200]}")
                print(f"    py: {str(b.get(k))[:200]}")
        else:
            print(f"OK       {key}")

    # Demand-factor rounding: JavaScript's Math.round is half-away-from-zero,
    # Python's round() is banker's. They differ at exactly 1.25 and 1.75.
    expect = {0.25: 6, 0.5: 8, 0.75: 14, 1.0: 16, 1.25: 22, 1.5: 24, 1.75: 30, 2.0: 32}
    for f, n in expect.items():
        got = len(P.build_streams(f)[0])
        if got != n:
            bad += 1
            print(f"DIFF     fleet size at demand {f}: got {got}, dashboard gives {n}")
    print(f"\n{len(CASES)} payloads + {len(expect)} fleet sizes checked, {bad} mismatch(es)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
