# exp004 — Empirical admissibility envelope (spec Revision 1)

**Objective.** Replace hand-picked admissibility thresholds with the simulator's
own observed support, per accepted spec Revision 1.

**Hypothesis.** gen_trace's ordinary per-step drift has a well-defined bounded
support, separable from the scripted fault jump; the envelope should be derived
from ordinary steps only.

**Design.** 20,000 gen_trace episodes (1.98M ordinary steps), seed 20240601.
Recorded |dT|,|dS| for ordinary steps (t != TF), scripted fault |dT| at t=TF
separately, and observed value ranges of T,S,R. Envelope = 99.99th pct of
ordinary steps. Code commit 1846ef9.

**Result.**
- Controlled envelope: dT_max=0.0632, dS_max=0.0421 (ordinary-step 99.99pct;
  hard max 0.0804 / 0.0537).
- Scripted fault jump: |dT| in [0.150, 0.441] at t=40 — DISJOINT from ordinary
  support (gap ~0.08→0.15), so the cut is unambiguous.
- Value ranges: T[0,1], S[0.177,1], R[0.150,0.850]. R non-autoregressive → no dR bound.

**Interpretation.** The envelope is now a simulator-derived artifact, not an
arbitrary multiplier. Empirical dT_max (0.063) exceeds the earlier 3.3σ guess
(0.05): guessing would have been too tight. Ordinary/fault separation confirms
the two-mode design (Rev 2): Controlled uses the ordinary envelope; Natural
retains the scripted shock.

**Supports/contradicts paper?** Neutral/infrastructure — enables Phase 2. No
scientific claim tested here.

**Next action.** Implement convergent-trace generator (exp005) reading
envelope.json; Controlled + Natural modes; assertions S1, A1–A4, S3-check, S4.
