# exp009 — Integrity Audit

Performed post-experiment before paper writing.

## Check 1: Numbers from CSV, not cached variables
PASS. HSF=1.000, mean_PDI=3.000, max_PDI=3, distribution={3:50}
recomputed from processed_results.csv independently of summary.json.
Both agree exactly.

## Check 2: Full reproducibility from frozen artifacts
PASS. 400 terminal levels regenerated from generator_v2.py (frozen),
envelope.json (frozen), selected_targets.json, TRAPPolicy defaults.
Zero mismatches against raw_results.csv.

## Check 3: No frozen artifact modified after exp008
PASS. All 11 hashed artifacts (exp005: 7 files, exp008/generator_v2: 3 files,
envelope cross-check: 1) verify against stored SHA-256 hashes.

## Check 4: Paper claims vs what was measured

SAFE to claim:
- PDI = 3 authorization levels at 50 mid-range targets (g* ≈ 0.50–0.54)
  under TRAPPolicy (tr_tdaa, default parameters), Controlled Mode
- Two admissible histories reaching identical (T,S,R) can be granted
  levels 0 and 3 — a spread of 3 bands — depending on prior history
- The mechanism is level carry: a[H-2] determines a[H-1] via Branch H
  (hold) when g* is below up_edge(a[H-2])+te, which holds at all 50 targets

MUST NOT claim without qualification:
- "PDI=3 across all conditions" — only one ARS sub-band tested
- "PDI applies to other rules" — only tr_tdaa measured
- "PDI reflects natural operating probabilities" — Controlled Mode only
- "PDI = 3 is the maximum possible" — level 4-5 structurally OOS,
  not measured, so true maximum if they were reachable is unknown

## Check 5: Limitations for the paper (all 10 must appear)

L1  Single rule (tr_tdaa / TRAPPolicy default only).
L2  Single ARS sub-band (g* ≈ 0.50–0.54; 50 targets in band 2-3 region).
L3  Default parameters only (w, te, tr, k fixed).
L4  Controlled Mode only; Natural Mode not run.
L5  Levels 4-5 structurally unreachable (g_max=0.770 < up_edge(4)+te=0.850).
L6  Synthetic signal source; no real deployment validation.
L7  PDI_range is worst-case over deliberately constructed admissible
    histories, not expectation over natural history distribution.
L8  PDI_dis not interpretable as a natural history probability in this study.
L9  50 targets, occurrence-frequency selected; no full-grid coverage.
L10 exp006 null result (ramp generator) stands as a separate pilot finding;
    exp009 result depends on generator_v2 which adds prior_level control.
