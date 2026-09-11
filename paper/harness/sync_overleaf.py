"""Push regenerated tables and figures to an Overleaf project, without touching prose.

WHY THIS IS NOT A PLAIN `git push`
----------------------------------
Two people write to this project and they own disjoint files:

  prose      main.tex, sec*.tex, refs.bib, READ_ME_FIRST.md   <- humans edit in Overleaf
  artefacts  tables/*.tex, figs/*.pdf                          <- analyze.py / figures.py

A whole-directory push would clobber whichever side moved last. This script pushes ONLY
the artefacts, pulls everything else, and reports any prose file that changed upstream so
the local copy can be brought forward deliberately rather than by accident.

SETUP (once)
------------
Overleaf's Git remote needs a paid plan. In the project: Menu -> Git -> copy the URL,
which looks like https://git.overleaf.com/<project-id>. Authenticate with an Overleaf
Git token (Account Settings -> Git integration), used as the password.

    python sync_overleaf.py --init https://git.overleaf.com/<project-id>

USE (after any regeneration)
---------------------------
    python analyze.py && python figures.py && python sync_overleaf.py

    --dry-run   show what would change, push nothing
    --pull-prose  also copy upstream prose edits back into the local tree

If Git access is not available on the plan, run with --export instead: it writes only the
changed artefacts to a folder you can drag into Overleaf's file tree, which overwrites
those files and leaves prose untouched.
"""
import argparse
import filecmp
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.normpath(os.path.join(HERE, "..", "tex"))
WORK = os.path.normpath(os.path.join(HERE, "..", ".overleaf"))
CONF = os.path.join(HERE, ".overleaf_remote")

# Directories this script owns. Everything else in the project belongs to the humans.
ARTEFACTS = ("tables", "figs")
PROSE_SUFFIX = (".tex", ".bib", ".md")


def sh(*cmd, cwd=None, check=True):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and p.returncode:
        sys.exit(f"$ {' '.join(cmd)}\n{p.stdout}{p.stderr}")
    return p.stdout.strip()


def remote_url():
    if not os.path.exists(CONF):
        sys.exit("No remote configured. Run: sync_overleaf.py --init <git.overleaf.com URL>")
    return open(CONF, encoding="utf-8").read().strip()


def ensure_clone():
    url = remote_url()
    if not os.path.isdir(os.path.join(WORK, ".git")):
        print(f"cloning {url} -> {WORK}")
        sh("git", "clone", url, WORK)
    else:
        sh("git", "-C", WORK, "fetch", "origin")
        sh("git", "-C", WORK, "reset", "--hard", "origin/master")
    return WORK


def artefact_files():
    out = []
    for d in ARTEFACTS:
        src = os.path.join(TEX, d)
        if not os.path.isdir(src):
            continue
        for f in sorted(os.listdir(src)):
            if f.endswith((".tex", ".pdf")):
                out.append(os.path.join(d, f))
    return out


def report_prose_drift(work):
    """Prose files that differ between Overleaf and the local tree."""
    drift = []
    for f in sorted(os.listdir(work)):
        if not f.endswith(PROSE_SUFFIX):
            continue
        a, b = os.path.join(work, f), os.path.join(TEX, f)
        if os.path.exists(b) and not filecmp.cmp(a, b, shallow=False):
            drift.append(f)
    return drift


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", metavar="URL")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pull-prose", action="store_true")
    ap.add_argument("--export", metavar="DIR",
                    help="no Git: copy changed artefacts here for manual upload")
    a = ap.parse_args()

    if a.init:
        open(CONF, "w", encoding="utf-8").write(a.init.strip() + "\n")
        print(f"remote saved to {CONF}")
        return 0

    if a.export:
        os.makedirs(a.export, exist_ok=True)
        n = 0
        for rel in artefact_files():
            dst = os.path.join(a.export, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(TEX, rel), dst)
            n += 1
        print(f"{n} artefact(s) -> {a.export}")
        print("Drag tables/ and figs/ into Overleaf's file tree; it overwrites those "
              "files only and leaves prose untouched.")
        return 0

    work = ensure_clone()

    drift = report_prose_drift(work)
    if drift:
        print("\nPROSE CHANGED UPSTREAM (someone edited these in Overleaf):")
        for f in drift:
            print("   ", f)
        if a.pull_prose:
            for f in drift:
                shutil.copy2(os.path.join(work, f), os.path.join(TEX, f))
            print("  -> copied into the local tree. Re-run check_tex.py.")
        else:
            print("  -> NOT copied. Re-run with --pull-prose to bring them local,")
            print("     or edit locally and reconcile by hand. This script never")
            print("     pushes prose, so those edits are safe either way.")

    changed = []
    for rel in artefact_files():
        src, dst = os.path.join(TEX, rel), os.path.join(work, rel)
        if not os.path.exists(dst) or not filecmp.cmp(src, dst, shallow=False):
            changed.append(rel)
            if not a.dry_run:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)

    if not changed:
        print("\nartefacts already up to date")
        return 0
    print(f"\n{len(changed)} artefact(s) changed:")
    for rel in changed:
        print("   ", rel)
    if a.dry_run:
        print("(dry run: nothing pushed)")
        return 0

    sh("git", "-C", work, "add", *changed)
    msg = ("Regenerate tables and figures from solver output\n\n"
           "Artefacts only; prose untouched.\n\n"
           "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>")
    sh("git", "-C", work, "commit", "-m", msg)
    sh("git", "-C", work, "push", "origin", "master")
    print("pushed to Overleaf")
    return 0


if __name__ == "__main__":
    sys.exit(main())
