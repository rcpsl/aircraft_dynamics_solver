"""Structural check on the LaTeX sources, since there is no TeX install on this box.

Catches the failure modes that would waste an Overleaf compile: an \\input of a file
that does not exist, a \\ref to a label nobody defines, a \\cite key missing from the
bibliography, an \\includegraphics of a figure that was never generated, and stray
carriage returns from a bad edit.

usage: python check_tex.py      exit 0 iff clean
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.normpath(os.path.join(HERE, "..", "tex"))

problems = []


def read(p):
    return io.open(p, encoding="utf-8", newline="").read()


def note(kind, msg):
    problems.append(f"{kind}: {msg}")


# ---- collect every tex file reachable from main.tex -------------------------
def gather(path, seen):
    if path in seen or not os.path.exists(path):
        return ""
    seen.add(path)
    s = read(path)
    out = s
    for m in re.finditer(r"\\input\{([^}]+)\}", s):
        target = m.group(1)
        cand = os.path.join(TEX, target if target.endswith(".tex") else target + ".tex")
        if not os.path.exists(cand):
            note("MISSING INPUT", f"{os.path.basename(path)} inputs {target!r} "
                                 f"-> {os.path.relpath(cand, TEX)} does not exist")
        else:
            out += gather(cand, seen)
    return out


main = os.path.join(TEX, "main.tex")
if not os.path.exists(main):
    print("no main.tex"); sys.exit(1)
seen = set()
doc = gather(main, seen)
print(f"scanned {len(seen)} tex files")

# ---- control characters -----------------------------------------------------
# A shell heredoc that collapses backslash escapes turns "\begin" into a literal
# backspace followed by "egin". Braces still balance, refs still resolve, and the
# build fails with an obscure error -- so this check exists specifically because
# that happened. \r is included since a lone CR is the same class of damage.
for p in sorted(seen):
    s = read(p)
    bad = [(i, c) for i, c in enumerate(s) if ord(c) < 32 and c not in "\n\t"]
    for i, c in bad[:5]:
        note("CONTROL CHAR", f"{os.path.relpath(p, TEX)} has {hex(ord(c))} at {i}: "
                             f"{s[max(0,i-30):i+20]!r}")
    if len(bad) > 5:
        note("CONTROL CHAR", f"{os.path.relpath(p, TEX)}: {len(bad)-5} more")

# ---- \end without a matching \begin -----------------------------------------
for p in sorted(seen):
    s = re.sub(r"(?<!\\)%.*", "", read(p))
    for env in set(re.findall(r"\\end\{(\w+\*?)\}", s)):
        nb = len(re.findall(r"\\begin\{" + re.escape(env) + r"\}", s))
        ne = len(re.findall(r"\\end\{" + re.escape(env) + r"\}", s))
        if nb != ne:
            note("ENV IMBALANCE",
                 f"{os.path.relpath(p, TEX)}: {env} has {nb} begin vs {ne} end")

# ---- labels vs refs ---------------------------------------------------------
labels = set(re.findall(r"\\label\{([^}]+)\}", doc))
refs = set(re.findall(r"\\(?:eq)?ref\{([^}]+)\}", doc))
for r in sorted(refs - labels):
    note("UNDEFINED REF", r)
unused = sorted(labels - refs)
if unused:
    print(f"note: {len(unused)} label(s) never referenced: {', '.join(unused)}")

# ---- citations vs bib -------------------------------------------------------
bib = os.path.join(TEX, "refs.bib")
keys = set(re.findall(r"@\w+\{([^,]+),", read(bib))) if os.path.exists(bib) else set()
cited = set()
for m in re.finditer(r"\\cite\{([^}]+)\}", doc):
    cited |= {c.strip() for c in m.group(1).split(",")}
for c in sorted(cited - keys):
    note("UNDEFINED CITE", c)
uncited = sorted(keys - cited)
if uncited:
    print(f"note: {len(uncited)} bib entr(ies) never cited: {', '.join(uncited)}")

# ---- graphics ---------------------------------------------------------------
for m in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", doc):
    g = m.group(1)
    cand = os.path.join(TEX, g)
    if not os.path.exists(cand):
        note("MISSING FIGURE", f"{g} -> {cand}")

# ---- brace balance per file -------------------------------------------------
for p in sorted(seen):
    s = re.sub(r"(?<!\\)%.*", "", read(p))          # strip comments
    s = s.replace(r"\{", "").replace(r"\}", "")
    if s.count("{") != s.count("}"):
        note("BRACE IMBALANCE",
             f"{os.path.relpath(p, TEX)}: {s.count('{')} open vs {s.count('}')} close")

# ---- undefined macros and environments --------------------------------------
#
# This check exists because the file shipped for a week with \dbinc used 28 times and
# defined nowhere, and \begin{proof} without amsthm loaded. Braces balanced, refs
# resolved, and the old checker reported "no structural problems found". A structural
# check that cannot see a missing macro is not checking the thing that breaks builds.
KNOWN_PACKAGES = {
    "amsmath": {"align", "equation", "gather", "split", "cases", "aligned",
                "eqref", "text", "textstyle", "displaystyle", "lfloor", "rfloor",
                "bigl", "bigr", "Bigl", "Bigr", "substack", "notag"},
    "amsthm": {"proof", "newtheorem", "theoremstyle", "qedhere"},
    "amssymb": {"square", "blacksquare", "varnothing", "nmid", "supsetneq",
                "subsetneq"},
    "graphicx": {"includegraphics", "resizebox", "scalebox"},
    "booktabs": {"toprule", "midrule", "bottomrule", "cmidrule", "addlinespace"},
    "multirow": {"multirow"},
    "cite": {"cite"},
    "hyperref": {"url", "href", "hidelinks"},
    "xcolor": {"color", "textcolor", "colorbox"},
}
# Commands provided by LaTeX itself or by IEEEtran; not exhaustive, but anything
# outside it is surfaced for a human to confirm rather than silently accepted.
BUILTIN = {
    "documentclass", "usepackage", "begin", "end", "section", "subsection",
    "subsubsection", "paragraph", "label", "ref", "caption", "centering", "item",
    "textbf", "textit", "emph", "texttt", "footnote", "input", "bibliography",
    "bibliographystyle", "maketitle", "title", "author", "date", "newcommand",
    "renewcommand", "providecommand", "def", "left", "right", "frac", "sum", "max",
    "min", "log", "in", "le", "ge", "neq", "leq", "geq", "times", "cdot", "ldots",
    "dots", "quad", "qquad", "hspace", "vspace", "newline", "par", "and", "to",
    "mathcal", "mathrm", "mathbb", "mathbf", "text", "bot", "top", "vee", "wedge",
    "neg", "forall", "exists", "Rightarrow", "iff", "approx", "sim", "propto",
    "alpha", "beta", "gamma", "delta", "epsilon", "kappa", "mu", "pi", "rho",
    "sigma", "tau", "omega", "Sigma", "Omega", "overline", "underline", "hat",
    "tilde", "bar", "vec", "operatorname", "mid", "colon", "setminus", "cup", "cap",
    "subseteq", "supseteq", "subset", "supset", "equiv", "lfloor", "rfloor",
    "IEEEauthorblockN", "IEEEauthorblockA", "IEEEoverridecommandlockouts",
    "IEEEkeywords", "abstract", "figure", "table", "tabular", "enumerate",
    "itemize", "description", "proposition", "definition", "theorem", "lemma",
    "corollary", "thebibliography", "sisetup", "DeclareSIUnit", "newtheorem",
    "theoremstyle", "BibTeX", "kern", "lower", "hbox", "rm", "sc", "scriptsize",
    "small", "footnotesize", "large", "Large", "multicolumn", "hline", "toprule",
    "midrule", "bottomrule", "cmidrule", "figure*", "table*",
    "bigvee", "bigwedge", "bigcup", "bigcap", "prod", "int", "ell", "infty",
    "langle", "rangle", "lvert", "rvert", "lVert", "rVert", "nu", "lambda",
    "theta", "phi", "psi", "chi", "eta", "zeta", "xi", "varepsilon", "varphi",
    # Footnote markers used by the generated tables and figure titles to flag a cell
    # whose optimality is unproven. Plain-TeX math symbols, always available; they
    # first appear here only because the fleet study's harvested incumbents are the
    # first unproven rows any generated table has had to mark.
    "dagger", "ddagger", "ast", "star", "circ", "bullet",
}

main_src = read(main)
defined = set(re.findall(r"\\(?:new|renew|provide)command\{?\\(\w+)", main_src))
loaded = set(re.findall(r"\\usepackage(?:\[[^\]]*\])?\{([^}]+)\}", main_src))
loaded = {p.strip() for grp in loaded for p in grp.split(",")}
newtheorems = set(re.findall(r"\\newtheorem\{(\w+)\}", main_src))

allowed = set(BUILTIN) | defined | newtheorems
for pkg, cmds in KNOWN_PACKAGES.items():
    if pkg in loaded:
        allowed |= cmds

# Macros used anywhere in the document. Comments are stripped first: a commented-out
# alternative (\qty, \IEEEproof) is not a use, and flagging it trains the reader to
# ignore this check.
doc_live = re.sub(r"(?<!\\)%.*", "", doc)
used = set(re.findall(r"\\([a-zA-Z]+)", doc_live))
unknown = sorted(u for u in used - allowed)
if unknown:
    note("POSSIBLY UNDEFINED MACRO",
         "not defined in main.tex and not from a loaded package: "
         + ", ".join("\\" + u for u in unknown[:25])
         + (f" (+{len(unknown)-25} more)" if len(unknown) > 25 else ""))

# Environments used, against those a loaded package or newtheorem provides.
envs = set(re.findall(r"\\begin\{([\w*]+)\}", doc))
env_allowed = set(BUILTIN) | newtheorems | {"document"}
for pkg, cmds in KNOWN_PACKAGES.items():
    if pkg in loaded:
        env_allowed |= cmds
missing_env = sorted(e for e in envs if e not in env_allowed)
if missing_env:
    note("POSSIBLY UNDEFINED ENVIRONMENT",
         ", ".join(missing_env) + " -- check the providing package is loaded")

# ---- report -----------------------------------------------------------------
print()
if problems:
    for p in problems:
        print(" ", p)
    print(f"\n{len(problems)} problem(s)")
    sys.exit(1)
print("no structural problems found")
