"""Serve either objective scheme on any port: python serve_any.py <weighted|prod> <port>

  prod      -> solver_server_dB.py            production, LEXICOGRAPHIC since 2026-08-27
  weighted  -> solver_server_dB_weighted.py   the control: the older single-weighted-sum

"lex" is still accepted and maps to prod, because that is what production now runs;
old command lines in the logs here therefore still do what they say.

Reloader off, as everywhere here: a restart mid-solve surfaces as a bare
ConnectionResetError. A server started before an edit keeps serving the OLD code, so
restart after every solver change or the tests measure the wrong build.
"""
import sys, importlib.util as iu

PATHS = {
    "prod":     r"d:/Documents/EECS_199_Shoukry/solver_server_dB.py",
    "lex":      r"d:/Documents/EECS_199_Shoukry/solver_server_dB.py",
    "weighted": r"d:/Documents/EECS_199_Shoukry/lex_objective_experiment/solver_server_dB_weighted.py",
}

which, port = sys.argv[1], int(sys.argv[2])
path = PATHS[which]
spec = iu.spec_from_file_location("S_" + which + str(port), path)
m = iu.module_from_spec(spec); spec.loader.exec_module(m)
print("serving %s (OBJECTIVE_MODE=%s) on %d" % (which, m.OBJECTIVE_MODE, port), flush=True)
m.app.run(port=port, debug=False, threaded=True, use_reloader=False)
