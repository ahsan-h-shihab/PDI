# exp006 — Target Selection Protocol (FROZEN BEFORE ANY PDI IS COMPUTED)

Frozen at: pre-computation
Generator: exp005 (commit ce8adce, integrity verified)
Envelope:  exp004_envelope/envelope.json

## Selection source
Targets are selected from exp003_robustness mining results (real gen_trace
trajectories), specifically the raw_results.csv at bin_width=0.02, seed=12345
(the original existence probe parameters). This bin width was chosen BEFORE
exp006 because it is the middle of the robustness range and matches exp002.

## Selection rule (fixed, not data-adaptive)
A binned condition (T_bin, S_bin, R_bin) is included as a target x* if and
only if ALL of the following hold, evaluated on the exp003 raw_results.csv
BEFORE running any PDI computation:

  RULE 1: it appeared as multi-level (pct_multi>0) in exp003 at binw=0.02
  RULE 2: the bin centre lies within the envelope A3 ranges
           T in [0.0, 1.0], S in [0.178, 1.0], R in [0.150, 0.850]
  RULE 3: the bin centre is reachable by F1 and F2 (both families must NOT
           raise ValueError from gen_convergent) — checked by dry-run before
           PDI is computed; failed targets are logged as REJECTED_INFEASIBLE
  RULE 4: grid is capped at N_TARGETS=50 selected by descending occurrence
           count (most-visited conditions first) to keep runtime bounded

## What is NOT a selection criterion
- PDI value (not yet computed at selection time)
- Which family induces a higher level (unknown at selection time)
- Any property of the emitted authorization level

## Rejection logging
Every candidate bin that fails RULE 2, 3, or 4 is logged in
rejected_targets.csv with the rule that caused rejection.

## Seeds
PDI computation seed: 42 (all families, all targets)
Secondary seed:      137 (robustness check, same targets)

## Families used
F1_degrade, F2_recover, F3_counter_primed, F4_counter_reset
F4 failures (OOS) logged per S6; PDI computed over available families only.

## H1 falsification criterion (pre-registered)
H1 is NOT supported if:
  HSF < 0.10  (fewer than 10% of selected targets are history-sensitive)
  AND mean PDI < 0.10 levels
If either condition holds independently, it is reported as a qualified result.

## H2 falsification criterion (pre-registered)
H2 is NOT supported if mean PDI is non-monotone in k across k in {2,3,4}
(the k sweep uses the same targets and seed; non-monotonicity is reported
exactly as observed, not smoothed).

## This protocol is frozen. No target may be added, removed, or re-selected
## after PDI values are seen.
