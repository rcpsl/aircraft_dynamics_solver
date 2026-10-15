import json, time, urllib.request
def post(port, req, timeout=2400):
    t=time.monotonic()
    r=urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/solve",
        json.dumps(req).encode(), {"Content-Type":"application/json"}), timeout=timeout)
    return json.load(r), time.monotonic()-t

def peak(res):
    return max((max(r) for r in res.get("noiseMatrix") or []), default=0.0)

def fellback(res):
    """Phase-2 failure looks like a normal sat from the outside -- no T_used is the
    tell on production; the fork also sets phase2Failed outright."""
    return res.get("phase2Failed") is True or (res.get("status")=="sat" and "T_used" not in res)
