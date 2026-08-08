# exp005 — Convergent-trace generator verification (Spec v2)

## Objective
Verify that the convergent-trace generator satisfies S1–S4 on a systematic
target grid across both Controlled and Natural modes.

## Hypothesis
All generated histories terminate at exactly x* (S1), satisfy the empirical
admissibility envelope A1–A4 (S2), and are bit-exactly reproducible from their
provenance tuple (S4). F4 is infeasible for low-R* targets in Controlled Mode
(physical constraint); those are logged as out-of-support (S6).

## Failures encountered and resolved

### Attempt 1 (initial implementation)
- F3 (counter_primed): 72 ADM failures (A1) at the vstack join point.
  Root cause: two independently-built segments joined without checking the
  cross-segment step against dT_max. Fix: replaced vstack construction with a
  single continuous ramp (hold phase + convergence phase, no join).
- F4 (counter_reset): 36 generator errors.
  Root cause: hard-coded T-offset of 0.15 > 1.5*dT_max. Fix: replaced with
  R-spike strategy; raises ValueError (S6) for R* < ~0.55 where max ARS drop
  cannot exceed tr=0.10 (physical constraint, not a bug).

### Attempt 2 (after F3/F4 fixes)
- 114 ADM failures (A1) in Natural Mode only, all at t=41 (fault_t+1).
  Root cause: Natural Mode overlay injected scripted fault at t=40, pulling
  T far below the ramp trajectory; subsequent step at t=41 snapped back,
  producing |dT|=0.25-0.38 >> dT_max=0.063. Assertion was correct.
  Fix: added re-planning pass after fault injection — re-runs T/S from
  fault_t+1 onward as a bounded ramp from h[fault_t] to (T*,S*), using the
  same _continuous_ramp inner loop. Re-planning always feasible (58 steps *
  dT_max=0.063 = 3.67 >> max fault gap 0.44).

## Final result (Attempt 3)
- histories attempted : 264
- S1  failures        : 0  (HARD GATE)
- ADM failures        : 0  (HARD GATE)
- S4  failures        : 0  (HARD GATE)
- out-of-support      : 36 (F4/low-R*, physical constraint, logged per S6)
- S3-distinct (ok)    : 18
- S3-insensitive      : 48 (logged, NOT a hard failure; history-insensitive targets)

## Interpretation
All hard-gate assertions pass. The 36 out-of-support cases are physically
expected (F4 requires ARS drop > 0.10 which needs R* > ~0.55 in Controlled
Mode). The 48 S3-insensitive cases mean the current target grid has many
history-insensitive conditions; this is a target-selection issue, not a
generator bug — the PDI experiment (exp006) will select targets where at least
one family pair is known to induce different levels (using the mining results
from exp002/003 as a prior).

## Failed experiments retained
Two failed runs (attempt 1: F3 vstack bug; attempt 2: Natural Mode re-planning
bug) are documented in this log. Raw results from the final run are in
raw_results.csv. No previous experiment directories overwritten.

## Supports/contradicts paper?
SUPPORTS — the generator is verified correct; convergent histories exist and
are reproducible. The high S3-insensitive count on the systematic grid is
expected and will be addressed by target selection in exp006.

## Next action
exp006: PDI measurement on TRAPPolicy using verified generator. Select targets
from the exp003 mining results where multi-level conditions are known. Report
HSF, mean PDI, and PDI surface.
