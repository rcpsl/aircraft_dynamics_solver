"""Head-to-head runtime: weighted sum vs lexicographic, repeated measures.

Every earlier timing was a single sample taken under whatever load happened to be on
the machine, and Z3's run-to-run spread on these payloads is wide enough (244s vs 619s
for the same proven answer) that one sample decides nothing. This repeats each
configuration and reports the whole set.

Usage:  python test9_perf.py <port> <config> [reps]
        config = proportional | utilpeople

Run the four arms as four processes against four servers, so the two configurations
do not queue behind each other and neither solver gets the quiet machine:

    5056 lex  proportional     5058 lex  utilpeople
    5057 prod proportional     5059 prod utilpeople

The objective is recomputed from the RETURNED paths, not read from the solver's own
reporting, so a partial result and a proven one are scored the same way and the two
solvers cannot disagree about what they are measuring.
"""
import sys, cfg, client

# 15 min for Proportional (production does it in ~50-190s, so this is not binding).
# 30 min -- the server's SOLVE_TIMEOUT_CAP_MS -- for Utilitarian+People, which is the
# one configuration where lex has failed to finish before.
CONFIGS = {
    "proportional": dict(kw=dict(principle="proportional"), timeoutMs=900000,
                         metric="proximityCost"),
    "utilpeople":   dict(kw=dict(principle="utilitarian", who="people"),
                         timeoutMs=1800000, metric="utilNoise"),
}


def score(res, req, metric):
    if metric == "proximityCost":
        return res.get("proximityCost")
    return cfg.util_noise(res, req)


if __name__ == "__main__":
    port = int(sys.argv[1])
    name = sys.argv[2]
    reps = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    c = CONFIGS[name]

    print("=== %s on port %d, %d reps ===" % (name, port, reps), flush=True)
    rows = []
    for k in range(reps):
        req = cfg.build(timeoutMs=c["timeoutMs"], **c["kw"])
        try:
            res, el = client.post(port, req)
        except Exception as e:
            print("  rep %d  CLIENT %s: %s" % (k + 1, type(e).__name__, e), flush=True)
            continue
        opt = res.get("optimality")
        if res.get("status") != "sat":
            print("  rep %d  %-8s %s" % (k + 1, res.get("status"), res.get("reason", "")),
                  flush=True)
            continue
        v = score(res, req, c["metric"])
        rows.append((el, opt, v))
        print("  rep %d  %6.0fs  optimality=%-8s %s=%s  mode=%s  arrPen=%s"
              % (k + 1, el, opt, c["metric"], v,
                 res.get("objectiveMode"), res.get("arrivalPenalty")), flush=True)

    if rows:
        ts = sorted(r[0] for r in rows)
        mid = ts[len(ts) // 2] if len(ts) % 2 else (ts[len(ts) // 2 - 1] + ts[len(ts) // 2]) / 2
        print("  --- %d/%d returned: min %.0fs  median %.0fs  max %.0fs; %d proven optimal"
              % (len(rows), reps, ts[0], mid, ts[-1],
                 sum(1 for r in rows if r[1] == "optimal")), flush=True)
