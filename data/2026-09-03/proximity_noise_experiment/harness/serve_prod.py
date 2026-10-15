"""Run the PRODUCTION solver on 5055, reloader off.

Deliberately a separate port from 5051: another session may own 5051, and a
600s solve sent at someone else's server is not a polite way to run a test.
"""
import importlib.util as iu
spec=iu.spec_from_file_location(
    "P", r"d:/Documents/EECS_199_Shoukry/solver_server_dB.py")
P=iu.module_from_spec(spec); spec.loader.exec_module(P)
P.app.run(port=5055, debug=False, threaded=True, use_reloader=False)
