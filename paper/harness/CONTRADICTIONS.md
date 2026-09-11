# Paragraphs in Sections I--III and V that now contradict the redirection

Required by the brief, which also says not to rewrite those sections tonight. This is
the list to work from. Three categories, and they need different treatment:

* **FRAMING** --- the claim is still true, but it is stated in the workshop /
  participant vocabulary the redirection drops. Rewrite the sentence, keep the result.
* **SUPERSEDED** --- the new unlimited-budget data measures the same thing better, and
  the number in the text should be replaced.
* **CONTRADICTED** --- the new data disagrees. Must change before submission.

Nothing below has been edited. Line numbers are as of 2026-09-09.

---

## `sec1_intro.tex`

| where | category | what |
|---|---|---|
| L40--42 | FRAMING | ``it is the solver behind a participatory workshop tool in which residents of Austin, TX select a principle and see the resulting flight paths''. The instance is still Austin and still the tool's own request builder; the paper is no longer about what a resident sees. |
| L55--58 (contribution 2a) | FRAMING | ``the difference a user sees is an arbitrary tie-break''. Proposition~1 survives and §IV-B keeps it. The *user* is out of scope; restate as a statement about routings. |
| L58--59 (contribution 2b) | SUPERSEDED | ``already-loud communities some $70\times$ cheaper to overfly''. §IV-D now measures the ratio directly at the cap the study runs on: under $D=\SI{10}{\dB}$ the capacities are 9 / 90 / 900 aircraft at 45 / 55 / \SI{65}{\dBA}, i.e. $100\times$ between the extremes. Both numbers are right for their own $D$; the text should say which. |
| L59--61 (contribution 2c) | CONTRADICTED | ``an ablation shows three of the five principles bind on nothing at the deployed setting''. Two things are now wrong with this. ``Deployed setting'' means the \SI{600}{\second} budget, which the study does not use. And the fleet-size data says the binding is a function of $N$, not a fixed property: Equal and Sufficientarian return occupancy **identical to the no-fairness baseline** at $N=6$ and $N=8$ (distance exactly 0, all cells proven optimal) and differ from it at every size from $N=14$ up (Equal 0.19--0.25). ``Binds on nothing'' is true only below the size of the map. |
| L63--67 (contribution 3) | CONTRADICTED | ``unable to prove optimality within a \SI{600}{\second} budget''. With no budget at all, Utilitarian proves at $N=6$ (\SI{77}{\second}) and $N=8$ (\SI{329}{\second}) and not above; Proportional's wall is lower still. The budget was never the binding constraint, so the sentence understates the result. |

## `sec2_principles.tex`

Definitional throughout and largely survives. Its two forward references
(`sec:mismatch`, `sec:concavity`) still resolve --- both labels are kept in the new §IV.

| where | category | what |
|---|---|---|
| L26, L114 | FRAMING | Both point at §IV-B for the Equal/Sufficientarian collapse. The proposition and its proof are carried over verbatim, so these read correctly; only the surrounding narrative changed. No edit strictly required. |

## `sec3_encoding.tex`

| where | category | what |
|---|---|---|
| L178 | FRAMING | ``worth keeping at workshop scale, where a solve is dominated by\ldots''. Replace ``workshop scale'' with the fleet sizes it means. |
| L293, L337, L350 | FRAMING | The Proportional benefit construction is described through ``participants' own ranking'' and ``whatever ambient preference participants expressed''. The construction is unchanged and still needed; the ranking is now simply an input, not something a participant supplies. The `propranking` sweep that varied it is out of scope, so §IV no longer reports what changing it does --- if §III keeps claiming the ranking matters, it now has no supporting experiment. |
| L383 | CHECK | ``no result in Section~\ref{sec:results}\ldots'' --- the sentence refers to results that no longer exist in §IV. Verify what it asserts and re-point it. |
| L123--135 | OK | `eq:cap` and `fig:capacity` are both still referenced by the new §IV-D, which now also states the closed form as `eq:capclosed`. |

## `sec5_conclusion.tex`

| where | category | what |
|---|---|---|
| L7--21 (``The encoding is part of the ethics'') | CONFIRMED, one clause CONTRADICTED | The core survives and is now stronger. At unlimited budget, Equal, Sufficientarian, Prioritarian and the baseline all attain **the same arrival penalty at every fleet size** --- 18, 22, 40, 44, 62, 66, 84, 88 --- all proven optimal, while returning different routings whose peak added noise differs by up to \SI{3.98}{\dB} at $N=24$ ($10.00$ against $6.02$). But ``interchangeable at every fleet size we settled'' is now too strong: their occupancy is identical only at $N=6$ and $N=8$, and diverges from $N=14$ up (0.11--0.23). They are equally optimal, not interchangeable. Also drop ``so participants were interpreting''. |
| L23--31 (``Ask whether a principle binds'') | CONFIRMED and extendable | ``all five principles fly every aircraft on a shortest path'' held only for $N \le 16$ at matched budgets. It now holds for **every proven cell at every size on the ladder, to $N=32$, at no budget** --- and the slack screen shows Equal, Sufficientarian and Prioritarian still fly the floor when given three extra timesteps, so it is not an artefact of a tight horizon. The hedge in the parenthesis can go. ``Three of our five principles changed nothing the solver optimises at the deployed setting'' needs the $N$-dependence added, as in §I above. |
| L33+ (``An unproven answer is not a weak answer'') | CONFIRMED | Reinforced. This study removes the budget entirely and the retraction record is the reason it does. |
| L90 | OK | `Proposition~\ref{prop:collapse}` still resolves; the proposition is carried over unchanged. |
| L92, L97 | FRAMING | ``fixed in advance by the workshop's definition sheet'' and ``the degeneracy we\ldots'' --- the definition sheet is still the source for §II and can stay as a citation; the degeneracy sentence points at material §IV no longer carries. |

---

## The one structural risk

Every label §I--III and V reference into §IV still exists in the rewritten section, so the
document still builds: `sec:results`, `sec:setup`, `sec:mismatch`, `prop:collapse`,
`sec:concavity`, `sec:tractability`, `eq:capclosed`, `sec:degeneracy`. Two of those
(`sec:mismatch`, `sec:degeneracy`) are now attached to subsections about something
adjacent to what the referring sentence promises, so a reader following the reference
will land in roughly the right place but not on the old claim. `check_tex.py` cannot see
that; only a read can.

`eq:capclosed` was defined in the deleted §IV and had to be reconstructed, because
`paper/` is not under version control --- there was no earlier copy to recover it from.
The restated form,
$\capm_m = \lfloor (10^{D/10} - 1)\,10^{(b_m - \alpha)/10} \rfloor$,
is the closed form of `eq:cap` and matches both `figures.py: fig_capacity` and the
numbers in `fig:capacity`'s own caption (at $D=\SI{3}{\dB}$: 0 aircraft at
\SI{45}{\dBA}, 99 at \SI{65}{\dBA}). It should still be read against §III's notation
before submission. **`paper/` should be committed to git.**

---

# Addendum, 2026-09-11 — what the indifference floor changes

Measured after this file was first written, and it moves several entries. The finding:
holding one cap-based condition fixed and changing only the horizon — which provably
leaves its arrival optimum untouched — still moves its peak added noise by up to
**5.64 dB** and its peak tile occupancy by up to **5 aircraft** at N=16. Most
between-condition differences at a fixed setup are smaller than that, and so are not
evidence about the condition. Section IV now says so and declines the claims that rested
on them.

| where | was | now |
|---|---|---|
| §I contribution 2c, "an ablation shows three of the five principles bind on nothing at the deployed setting" | CONTRADICTED (N-dependence) | **CONTRADICTED, and the replacement is stronger.** It is not that three principles bind on nothing at one setting; it is that for the three cap-based conditions, *no performance difference from the no-fairness baseline exceeds the solver's own indifference* at any fleet size measured. Prioritarian's own objective evaluates to 0.0 at every fleet size and every horizon. Rewrite around the floor, not around the ablation. |
| §I contribution 2, "the translation from words to constraints is not neutral" | FRAMING | Survives and is better supported. The sharpest evidence is no longer the Equal/Sufficientarian collapse but the floor: a menu of five principles, three of which return answers a reader cannot distinguish from no principle at all. |
| §I contribution 2b, "$70\times$ cheaper to overfly" | SUPERSEDED | Unchanged by the floor — it is analytic. §IV-D gives 9 / 90 / 900 aircraft at $D=10$. |
| §V "Ask whether a principle binds, not whether it is implemented" | CONFIRMED | **Now has a quantitative test to offer, which it previously lacked.** The paragraph recommends running the payload with the principle's term removed and comparing. The floor says that is not sufficient: you must also vary an incidental parameter and check the principle's effect exceeds *that*. Worth rewriting as the paper's methodological contribution. |
| §V "Equal returning answers interchangeable with Sufficientarian's" | one clause CONTRADICTED | Unchanged from the original entry — they are identical only at N=6 and N=8 — but the floor explains why the divergence above N=14 is not a counter-example: it is smaller than the indifference. |
| §III-D, the arrival tie-break | not previously listed | **Newly load-bearing.** §III presents arrival as a tie-break that breaks ties harmlessly. The floor shows the tie-break is doing more visible work than three of the five principles. §III should say so. |

## The one new open question

The floor is measured on the four cap-based conditions, because they are the ones whose
arrival optimum provably does not move with the horizon. Utilitarian and Proportional
carry objectives that a wider horizon genuinely can improve, so the same instrument does
not apply to them unaltered, and their effects are compared against the cap-based floor
instead. The permutation sweep (`plans.py: perm_sweep`) removes that asymmetry — it
leaves the feasible set identical for every condition — and is queued. Until it lands,
the floor for the two objective principles is inferred rather than measured.
