"""Confirm check_tex.py actually catches the two failure modes that shipped.

Temporarily breaks main.tex two ways and asserts the checker complains each time,
then restores. Written as a file because this shell collapses backslash escapes.
"""
import io
import shutil
import subprocess
import sys

MAIN = "../tex/main.tex"
BAK = "../tex/_main_selftest.bak"
shutil.copy(MAIN, BAK)
orig = io.open(MAIN, encoding="utf-8", newline="").read()


def run():
    p = subprocess.run([sys.executable, "check_tex.py"], capture_output=True, text=True)
    return p.stdout


try:
    # 1. remove the \dbinc definition
    broken = orig.replace("\\newcommand{\\dbinc}{\\delta}\n", "")
    assert broken != orig, "could not remove \\dbinc -- test is not exercising anything"
    io.open(MAIN, "w", encoding="utf-8", newline="").write(broken)
    out = run()
    ok1 = "UNDEFINED MACRO" in out and "dbinc" in out
    print("removed \\dbinc      ->", "CAUGHT" if ok1 else "*** MISSED ***")

    # 2. remove amsthm, leaving \begin{proof} unprovided
    broken2 = orig.replace("\\usepackage{amsthm}\n", "")
    assert broken2 != orig, "could not remove amsthm"
    io.open(MAIN, "w", encoding="utf-8", newline="").write(broken2)
    out = run()
    ok2 = "UNDEFINED ENVIRONMENT" in out and "proof" in out
    print("removed amsthm       ->", "CAUGHT" if ok2 else "*** MISSED ***")
finally:
    shutil.copy(BAK, MAIN)
    import os
    os.unlink(BAK)

out = run()
print("restored             ->", "clean" if "no structural problems" in out else "DIRTY")
sys.exit(0 if (ok1 and ok2) else 1)
