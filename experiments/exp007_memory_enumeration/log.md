# exp007 — Reachable Policy-Memory Enumeration

## Objective
Experimentally determine which (a,cu) states are reachable at step H-2 under
the admissibility envelope, and which produce distinct terminal outputs at the
exp006 targets. No assumptions about feasibility; BFS forward simulation only.

## Method
Exhaustive BFS on (a, cu, g_bin) state space over 98 steps (H=100, reaching
step H-2). Signal discretized into 500 bins over [g_min=-0.117, g_max=0.770].
Per-step signal move bounded by dg_max=0.184 (from empirical envelope).
State space converges after ~21 steps (3775 triples stable).

## Reachable (a,cu) pairs at H-2
13 of 18 theoretical pairs are reachable:
  (0,0),(0,1),(0,2),(1,0),(1,1),(1,2),(2,0),(2,1),(2,2),(3,0),(3,1),(3,2),(4,0)

## Unreachable pairs (5) — structural, not accidental
  (4,1),(4,2): requires g >= up_edge(4)+te = 0.85 to increment cu at level 4.
               g_max = 0.770 < 0.85. Impossible under this envelope.
  (5,0),(5,1),(5,2): level 5 requires g >= 0.85 for k=3 consecutive steps.
               Impossible under this envelope. Level 5 is never reached.

## Per-target terminal level analysis (8 representative targets)
All targets have g* in [0.496, 0.536], direct_band in {2,3}.

For these targets:
  - (a=0,cu=2): escalation fires -> terminal=1 (g*=0.536 >= up_edge(0)+te=0.25)
  - (a=1,cu=2): escalation fires -> terminal=2 (g*=0.536 >= up_edge(1)+te=0.40)
  - (a=2,*):    hold fires (g*=0.536 < up_edge(2)+te=0.55) -> terminal=2
  - (a=3,*):    hold fires (g*=0.536 < up_edge(3)+te=0.70) -> terminal=3
  - (a=4,cu=0): restriction fires if g_prev was high -> terminal in {3,4}

PDI potential at every target: max terminal - min terminal = 4 levels
(ranging from 0 to 4 depending on prior level).

## Key finding
PDI potential is 4 levels at every tested target.
The pilot generator (exp006) produced a[H-2]=2 for ALL families, yielding
terminal=2 for all, PDI=0. This is confirmed as a coverage failure:
(a=3,cu=0) is reachable under the envelope but was never produced.

## New generator interface (derived from this enumeration)
The new generator must accept `prior_level` as an explicit argument.
Families: one per reachable prior level in {0,1,2,3,4} (5 families).
cu targeting: secondary parameter, important only when Branch E fires.
  For these targets (g* in [0.50,0.54]):
    Branch E fires only for a_prev in {0,1} (g* >= up_edge(a)+te).
    For a_prev>=2: Branch E never fires; cu is irrelevant.
  => For a_prev in {0,1}: two sub-families (cu=0..1 vs cu=2) needed.
  => For a_prev in {2,3,4}: one family per level suffices.
  Total minimum families per target: 7 (2+2+1+1+1).

## Supports/contradicts paper?
SUPPORTS H1 potential: PDI=4 is provably reachable via admissible histories.
The question is now purely about implementation: can the generator construct
admissible histories that produce a_prev in {0,1,3,4} (not just 2)?

## Next action
Implement new generator with explicit prior_level argument.
Three-phase construction (escalate-to-prior, hold, descend-to-x*) is
proven feasible by the BFS enumeration: all prior levels 0-4 appear in
the reachable set.
