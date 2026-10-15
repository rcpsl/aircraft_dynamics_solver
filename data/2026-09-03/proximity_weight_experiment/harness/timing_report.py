"""Read timing.jsonl and say, per configuration, whether it clears 600 s.

Anything at the 900 s cap is reported as ">900" rather than a number: the cap
was chosen because the decision threshold is the dashboard's 600 s budget, so
past 900 s the exact figure changes nothing.
"""
import json, sys


def label(r):
    bits = [r["scheme"]]
    if "D" in r:
        bits.append(f"D={r['D']:g}")
    for k, v in sorted(r.get("req", {}).items()):
        if k == "split":
            bits.append("split streams")
        elif isinstance(v, (int, float, bool, str)):
            bits.append(f"{k}={v}")
    return "  ".join(bits)


def main(path):
    rows = [json.loads(l) for l in open(path)]
    plan = {j_key(j): j for j in json.load(open("plan_timing.json"))["jobs"]}
    print(f"{'configuration':44}{'status':16}{'wall':>9}{'600s?':>8}  routing")
    for r in sorted(rows, key=lambda r: r["elapsed"]):
        j = plan.get(r["key"], {})
        cfg = label(dict(j, scheme=r["scheme"]))
        wall = f"{r['elapsed']:.0f}s" if r["status"] == "sat" else ">900s"
        ok = "PASS" if (r["status"] == "sat" and r["elapsed"] <= 600) else "fail"
        route = ("/".join(str(r["tier"][b]) for b in ("45", "55", "65"))
                 if r.get("tier") else "-")
        print(f"{cfg[:43]:44}{r['status']:16}{wall:>9}{ok:>8}  {route}")


def j_key(j):
    wp = float(j.get("w_prox", 1.0))
    tail = "" if wp == 1.0 else f"|wp{wp:g}"
    if "D" in j:
        tail += f"|D{float(j['D']):g}"
    for k, v in sorted(j.get("req", {}).items()):
        tail += f"|{k}={v}" if isinstance(v, (int, float, bool, str)) else f"|{k}"
    return (f"{j['scheme']}|{'-'.join(j['order'])}|{'P' if j['pop'] else 'NOPOP'}"
            f"|T{j['T_max']}{tail}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "timing.jsonl")
