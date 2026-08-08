# exp008 — generator_v2 verification

## Result: HARD GATE PASSED
S1=0, ADM=0, S4=0, PL=0 on 200 histories.
OOS=72 (cu_target=2 for pl=0 structurally impossible; logged per S6).

## Bugs found and fixed (3 iterations)
1. _safe_step must_hold=True in prime loop suppressed escalation counter.
   Fix: prime loop uses direct bounded T move, no _safe_step.
2. Prime steps capped at k-2=2 to avoid firing escalation prematurely.
3. Phase 3 uses _safe_step(must_hold=True) to prevent threshold crossings.

## Level map (x*=(0.68,0.76,0.16), seed=42, controlled)
prior_level=0 -> terminal=0
prior_level=1 -> terminal=1 or 2 (cu-dependent)
prior_level=2 -> terminal=2
prior_level=3 -> terminal=3
PDI_range = 3 (levels 0 through 3) CONFIRMED PRESENT

## Next action: FREEZE generator_v2.py, proceed immediately to exp009 PDI.
