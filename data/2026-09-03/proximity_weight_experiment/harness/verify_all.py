"""Check every Z3 'sat' result against the surrogate, reconstructing each row's payload.

The runner's older rows do not carry their payload overrides (fixed since), so the
configuration is recovered from the job key, which does: it carries N=..., split=True
and demandFactor=... . Getting this wrong is silent and looks like a surrogate failure
-- the first version of this script compared N=8 runs against the default N=16 payload
and reported 10 spurious mismatches.
"""
import json, os, sys
sys.path.insert(0, r"d:/Documents/EECS_199_Shoukry/proximity_noise_experiment/harness")
import mkreq as mk
import surrogate as su

DEM, AIR, DTN, COM = [4, 2, 2], 11, 18, 5
PAIRS = [(DTN, AIR), (COM, DTN), (COM, AIR)]
S_, E_, M_ = [], [], []
for (a, b), C in zip(PAIRS, DEM):
    for s, e in ((a, b), (b, a)):
        lo = max(1, round(C / 3))
        for m in (lo, max(1, C - lo)):
            S_.append(s); E_.append(e); M_.append(m)
SPLIT = (S_, E_, M_)


def streams_for(rec):
    key = rec["key"]
    if "split=True" in key:
        return SPLIT
    for part in key.split("|"):
        if part.startswith("demandFactor="):
            return mk.streams(float(part.split("=")[1]))
    return None


def w_prox_for(rec):
    for part in rec["key"].split("|"):
        if part.startswith("wp"):
            return float(part[2:])
    return 1.0


def main(files):
    ok = bad = 0
    for fn in files:
        if not os.path.exists(fn):
            continue
        for line in open(fn):
            r = json.loads(line)
            if r.get("status") != "sat":
                continue
            # hardT rows solve at phase 1's T, which the row records as "T"
            T = r.get("T", r["T_max"])
            p = su.Problem(r["scheme"], r["order"], r["pop"], T=T,
                           w_prox=w_prox_for(r), streams=streams_for(r))
            got = p.solve(restarts=40)
            if got["occ"] == r["occ"]:
                ok += 1
            else:
                bad += 1
                print(f"  MISMATCH {fn:14} {r['scheme']:11} "
                      f"{'|'.join(r['order'])[:34]:36} surrogate cost {got['cost']:.9f}")
    print(f"\nZ3 sat results checked: {ok+bad}   identical: {ok}   different: {bad}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["timing.jsonl", "final.jsonl", "cliff.jsonl",
                          "demand.jsonl", "keepdb.jsonl", "stage1.jsonl"])
