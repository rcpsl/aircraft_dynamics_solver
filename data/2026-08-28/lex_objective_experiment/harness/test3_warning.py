"""Does a phase-2 failure now say what was dropped?

Forced by squeezing timeoutMs until phase 1 still finishes but phase 2 cannot. The
point is the WORDING and the flags, not the timing: a participant reading the old
message could not tell which objective was lost, and for Equal/Sufficientarian the
old message claimed a fairness choice had been dropped when there was no objective
to drop -- their rule is the D/U cap, which phase 1 enforces either way.
"""
import cfg, client

def probe(label, principle, who, ms):
    req = cfg.build(principle, who, timeoutMs=ms)
    for port, tag in ((5057, "PROD"), (5056, "LEX ")):
        try: res, el = client.post(port, req)
        except Exception as e:
            print(f"  {tag} {label:26} CLIENT {type(e).__name__}"); continue
        if not client.fellback(res):
            st = res.get("status")
            print(f"  {tag} {label:26} no phase-2 failure (status={st}) [{el:.0f}s]")
            continue
        flags = ""
        if "phase2Failed" in res:
            flags = (f"  [phase2Failed={res['phase2Failed']} "
                     f"reason={res.get('phase2FailReason')} "
                     f"principleImposed={res['principleImposed']}]")
        print(f"  {tag} {label:26} FELL BACK, paths T={len(res['paths'][0])} [{el:.0f}s]{flags}")
        print(f"       warning: {res.get('warning','(none)')}")
    print()

if __name__ == "__main__":
    print("=== phase-2 forced to fail (tight timeoutMs) ===\n")
    probe("Proportional",    "proportional",    "communities", 6000)
    probe("Prioritarian",    "prioritarian",    "communities", 6000)
    probe("Utilitarian+People", "utilitarian",  "people",      6000)
    probe("Sufficientarian",  "sufficientarian","communities", 6000)
    probe("Equal",            "equal",          "communities", 6000)
