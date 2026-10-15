"""Run the FORKED solver on 5052 with the reloader off.

Reloader off on purpose: with debug=True Flask restarts on any file save, which
tears down an in-flight solve and shows up at the client as a bare
ConnectionResetError. That cost a 10-minute run once already.
"""
import importlib.util as iu
spec=iu.spec_from_file_location(
    "S", r"d:/Documents/EECS_199_Shoukry/proximity_noise_experiment/solver_server_dB_noise.py")
S=iu.module_from_spec(spec); spec.loader.exec_module(S)
S.app.run(port=5053, debug=False, threaded=True, use_reloader=False)
