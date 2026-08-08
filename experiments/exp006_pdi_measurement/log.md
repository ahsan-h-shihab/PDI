# exp006 — PDI Measurement (TRAPPolicy, Controlled Mode)

## Objective
Measure PDI on TRAPPolicy across 50 targets selected from exp003 multi-level
conditions. Report HSF, mean PDI, max PDI honestly regardless of direction.

## Pre-registered falsification criteria
- H1 NOT SUPPORTED if HSF < 0.10 AND mean_PDI < 0.10
- H2 NOT SUPPORTED if mean_PDI non-monotone in k

## Result
- targets computed : 50/50
- HSF              : 0.000
- mean PDI         : 0.000
- max PDI          : 0
- PDI distribution : {0: 50}

## H1: NOT SUPPORTED (falsified by pre-registered criterion)

## Diagnosis (from diagnostic run, not post-hoc)

PDI = 0 across all 50 targets. All families emit the same terminal level (2)
at every target condition despite having different trajectories.

ROOT CAUSE: The exp003 "multi-level" mining signal is a trajectory-crossing
artifact, not evidence of within-condition path-dependence.

In gen_trace's natural trajectories the agent passes through conditions
(T~0.66-0.68, S~0.74-0.76, ARS~0.50-0.54) on the way DOWN from level 3
(during fault/recovery phase), still holding level 3 from pre-fault escalation.
Mining captures these as "level 3 at this condition." But those same conditions
are also visited by episodes that never reached level 3, recording "level 2."

The multi-level appearance is therefore:
  level_3 -> agent passing through on downward trajectory (holding prior level)
  level_2 -> agent at same condition on upward/neutral trajectory

The convergent-trace generator approaches x* from a bounded history that does
NOT start from a high-level escalated state (because the ep005 generator builds
H=100 step histories from mid-range T starting points). As a result, all
families arrive at x* with the policy still at level 2, having never escalated
to level 3 within the history.

CONFIRMATION: "does the policy change level?" diagnostic shows F1 (degrade)
visits levels [2,3,4] during the trajectory but ENDS at level 2; F2 (recover)
visits [1,2] and ENDS at level 2. Both terminal levels = 2, PDI = 0.

The condition for PDI > 0 under tr_tdaa requires that different families
reach the same x* while holding DIFFERENT accumulated levels — which requires
at least one family to arrive already AT level 3 (or higher) from prior
escalation. The generator's admissibility-constrained ramps do not produce
this scenario at the tested target conditions.

## What this means for the paper

The core assumption underlying H1 as implemented is not supported:
convergent-trace families derived from bounded-ramp histories do not produce
path-dependent terminal levels under TRAPPolicy at the tested conditions.

The exp003 mining result (45-51% multi-level prevalence) does NOT translate
into PDI signal. The prevalence observed in mining reflects temporal persistence
of level state (level memory across timesteps in a single episode), not
within-condition history-sensitivity in the sense defined by PDI (Eq. 4).

This is a scientifically honest negative result.

## Negative result retained per policy
This experiment is NOT deleted. The negative result is the finding.

## Next action (to be determined by researcher)
Options:
A. Redefine the generator to include histories that start from an escalated
   state (pre-escalated start), making "arrive at x* holding level 3" one of
   the history families. This would test a different but legitimate
   interpretation of path-dependence.
B. Accept the null result and re-examine whether PDI as defined is a
   scientifically meaningful property of tr_tdaa given its dynamics.
C. Change the studied rule to one where the generator's ramp approach can
   induce different levels at the terminal step (e.g. a pure hysteresis rule).

No option is taken here. The researcher decides.
