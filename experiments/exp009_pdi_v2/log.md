# exp009 — PDI Measurement with generator_v2

## Result
- HSF        : 1.000  (100% of targets history-sensitive)
- mean PDI   : 3.000
- max PDI    : 3
- distribution: {3: 50}  (all 50 targets, PDI=3)
- H1         : SUPPORTED

## Interpretation
PDI=3 at every target: the spread between the minimum reachable terminal
level (0, when prior level=0) and the maximum (3, when prior level=3) is
3 authorization levels at every tested condition.

Level maps show the pattern is clean and interpretable:
  prior_level=0 -> terminal=0   (held at low authority)
  prior_level=1 -> terminal=1 or 2 (cu-dependent)
  prior_level=2 -> terminal=2
  prior_level=3 -> terminal=3   (held at high authority)

Two agents at identical current condition (T,S,R) can differ by 3 full
authorization levels depending solely on the history by which they arrived.

## Scientific status
This is the intended PDI measurement. The prior_level dimension captures
the authorization-level carry from prior operating history, which is the
core policy-memory variable in tr_tdaa.

## Unexpected observation
PDI is uniform at 3 across all 50 targets. This is because all targets
have g* ≈ 0.50-0.54 (mid-range) and prior levels 0-3 are all reachable,
while prior level 4 is OOS (requires higher g history). The uniformity
is a structural consequence of the target selection (all in the same ARS
band region) rather than an artifact.

## Next action
Write paper sections. The experimental story is complete.
