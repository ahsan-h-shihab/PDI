# exp003 — Robustness of the path-dependence existence result

**Objective.** Test whether the multi-level prevalence result (exp002) is an
artifact of discretization bin width or mining seed.

**Hypothesis.** If the phenomenon is real, prevalence of multi-level recurring
conditions stays qualitatively high and stable across reasonable bin widths and
independent seeds; the metric (mean level-spread) stays ~1.

**Design.** Bin widths {0.01,0.02,0.03,0.05,0.08} × seeds {1,7,12345,2024,99999};
4000 gen_trace episodes each; recurrence threshold ≥5. Mines only real simulator
trajectories under TRAPPolicy (asymmetric rule). Code commit 1893aee.

**Result.**
- % multi-level (mean over seeds): binw .01→50.9%, .02→46.4%, .03→53.2%,
  .05→61.2%, .08→68.9%. Monotone increase with bin width (expected: coarser bins
  merge more contexts), but **never collapses** — floor ≈46% at the finest
  reasonable bin.
- **Seed variability is tiny**: within each bin width the spread across 5 seeds
  is ≤~2 percentage points (e.g. binw .02: 45.6–47.0%).
- Mean level-spread ≈1.01–1.12 throughout; max spread 2. Stable.

**Interpretation.** The existence of path-dependence is robust: it does not
depend on a lucky seed and does not vanish at fine granularity. The upward trend
with bin width is a benign, well-understood coarsening effect, not the source of
the signal — the effect is already ~46–51% at the two finest bins. The mean
spread being pinned near 1 across all settings shows the phenomenon is a genuine
±1-level history effect, not binning noise.

**Supports or contradicts the paper?** SUPPORTS. The frozen H1 (path-dependence
present and prevalent for the memory-bearing rule) survives both robustness
checks. No evidence to stop.

**Next action.** Proceed to the convergent-trace generator (Phase 2 proper):
construct admissible histories that terminate at an identical x* and span the
degrade-into / recover-into / counter-full / counter-reset families, with
assertions that (a) all traces end at identical x* and (b) per-step moves obey
gen_trace's bounded support. Then Phase 3 (PDI + memoryless-null check).
