"""Emit tables/pairwise.tex from results/pairwise.jsonl."""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
rows = [json.loads(l) for l in
        io.open(os.path.join(HERE, "results", "pairwise.jsonl"), encoding="utf-8")]
rows.sort(key=lambda r: r["N"])

tex = [r"\begin{table}[t]", r"\centering",
       r"\caption{The two disparity encodings, built on an otherwise identical phase-2 "
       r"model and timed. Both state the same constraint and agree on the objective at "
       r"every size. The pairwise form needs two orders of magnitude more assertions "
       r"and takes correspondingly longer to \emph{build}, but it \emph{solves} "
       r"$6$--$9\times$ faster --- so the max/min encoding's advantage is in "
       r"construction, and it decays from $3.2\times$ on total time at $N{=}6$ to "
       r"parity at $N{=}16$. Single runs on an idle machine; the solve times at "
       r"$N{=}6$ are under a second and should be read as indicative.}",
       r"\label{tab:pairwise}",
       r"\begin{tabular}{r rr rr rr}", r"\toprule",
       r"\multirow{2}{*}{$N$} & \multicolumn{2}{c}{max/min} & "
       r"\multicolumn{2}{c}{pairwise} & \multicolumn{2}{c}{ratio} \\",
       r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}",
       r" & constr. & solve (s) & constr. & solve (s) & solve & total \\",
       r"\midrule"]
for r in rows:
    a, b = r["maxmin"], r["pairwise"]
    tex.append(f"{r['N']} & {a['u_constraints']} & {a['solve_s']:.2f} & "
               f"{b['u_constraints']:,} & {b['solve_s']:.2f} & "
               f"${r['speedup_solve']:.2f}\\times$ & "
               f"${r['speedup_total']:.2f}\\times$ \\\\")
tex += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
out = os.path.join(HERE, "..", "tex", "tables", "pairwise.tex")
io.open(out, "w", encoding="utf-8", newline="\n").write("\n".join(tex) + "\n")
print("wrote", os.path.normpath(out))
