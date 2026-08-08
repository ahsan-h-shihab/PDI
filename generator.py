"""
Convergent-trace generator — Spec v2.  (revision after exp005 failure)

Bug fixes vs initial version
-----------------------------
F3: replaced independent-segment+vstack with a single continuous ramp
    that stays above-threshold in its first (H-tail) steps and converges
    in the remaining `tail` steps — no cross-segment join, so A1/A2 hold
    at every step by construction.

F4: replaced hard-coded T-offset (physically infeasible within envelope)
    with an R-spike strategy: raise R at the penultimate step toward R_hi
    while dropping T and S by their envelope bounds, achieving an ARS drop
    > tr=0.10.  Raises ValueError (S6) for targets where the maximum
    achievable ARS drop <= tr (physically impossible in Controlled mode
    for low-R* targets).

Everything else is unchanged.
"""
from __future__ import annotations
import json
import numpy as np
from pathlib import Path

# ---------------------------------------------------------------------------
# Envelope loader
# ---------------------------------------------------------------------------

def load_envelope(path: str | Path) -> dict:
    with open(path) as f:
        env = json.load(f)
    required = {"dT_max", "dS_max", "T_range", "S_range", "R_range", "scenario"}
    missing = required - env.keys()
    if missing:
        raise ValueError(f"envelope.json missing keys: {missing}")
    return env


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clamp(v, lo, hi):
    return float(max(lo, min(hi, v)))

def _ars(T, S, R, w=(0.5, 0.3, 0.2)):
    return w[0]*T + w[1]*S - w[2]*R

def _risk_for_natural(t, rng, fault_t, recovery_t, R_lo, R_hi):
    """Phase-keyed risk draw matching gen_trace scenario (Natural Mode)."""
    if t < fault_t:
        return float(rng.uniform(0.15, 0.30))
    elif t < recovery_t:
        return float(rng.uniform(0.60, 0.85))
    else:
        return float(rng.uniform(0.30, 0.50))

def _continuous_ramp(T_start, S_start, R_start,
                     T_star, S_star, R_star,
                     H, rng, dT_max, dS_max,
                     T_lo, T_hi, S_lo, S_hi, R_lo, R_hi):
    """
    Build a single (H,3) array that starts at (T_start,S_start,R_start)
    and terminates EXACTLY at (T_star,S_star,R_star).

    Per-step |dT| and |dS| are enforced <= envelope bounds at every step.
    R is drawn uniformly each step (no dR bound per spec).
    The terminal row is hard-set to x_star (S1).
    """
    T = np.zeros(H); S = np.zeros(H); R = np.zeros(H)
    T[0] = _clamp(T_start, T_lo, T_hi)
    S[0] = _clamp(S_start, S_lo, S_hi)
    R[0] = _clamp(R_start, R_lo, R_hi)

    for t in range(1, H - 1):
        # Steps remaining AFTER this one (excluding the forced terminal)
        steps_left = H - 1 - t
        # Minimum move needed to reach T_star in remaining steps
        # (if gap is too large, we must make progress)
        gap_T = T_star - T[t-1]
        gap_S = S_star - S[t-1]
        # Ideal linear progress
        ideal_T = T[t-1] + gap_T / (steps_left + 1)
        ideal_S = S[t-1] + gap_S / (steps_left + 1)
        # Add small noise
        raw_T = ideal_T + rng.normal(0, dT_max * 0.05)
        raw_S = ideal_S + rng.normal(0, dS_max * 0.05)
        # Clip move to envelope
        dT = _clamp(raw_T - T[t-1], -dT_max, dT_max)
        dS = _clamp(raw_S - S[t-1], -dS_max, dS_max)
        T[t] = _clamp(T[t-1] + dT, T_lo, T_hi)
        S[t] = _clamp(S[t-1] + dS, S_lo, S_hi)
        R[t] = float(rng.uniform(R_lo, R_hi))

    # S1: hard-set terminal row exactly
    T[H-1] = float(T_star)
    S[H-1] = float(S_star)
    R[H-1] = float(R_star)
    return np.column_stack([T, S, R])


# ---------------------------------------------------------------------------
# Path families
# ---------------------------------------------------------------------------
FAMILIES = ("F1_degrade", "F2_recover", "F3_counter_primed", "F4_counter_reset")
_TE = 0.05    # escalation margin matching tr_tdaa default
_TR = 0.10    # restriction threshold matching tr_tdaa default


# ---------------------------------------------------------------------------
# Main generator — Spec v2
# ---------------------------------------------------------------------------

def gen_convergent(x_star, family: str, seed: int, H: int = 100,
                   mode: str = "controlled",
                   envelope: dict | None = None,
                   envelope_path: str | None = None) -> np.ndarray:
    """
    Generate one admissible history of length H terminating EXACTLY at x_star.
    Raises ValueError if x_star is unreachable or family infeasible (S6).
    """
    if envelope is None:
        if envelope_path is None:
            raise ValueError("provide envelope or envelope_path")
        envelope = load_envelope(envelope_path)

    rng = np.random.default_rng(int(seed))   # S4: isolated, deterministic

    T_star = float(x_star[0])
    S_star = float(x_star[1])
    R_star = float(x_star[2])
    dT_max = float(envelope["dT_max"])
    dS_max = float(envelope["dS_max"])
    T_lo, T_hi = float(envelope["T_range"][0]), float(envelope["T_range"][1])
    S_lo, S_hi = float(envelope["S_range"][0]), float(envelope["S_range"][1])
    R_lo, R_hi = float(envelope["R_range"][0]), float(envelope["R_range"][1])
    fault_t    = int(envelope["scenario"]["fault_t"])
    recovery_t = int(envelope["scenario"]["recovery_t"])

    # S6: reject out-of-range targets
    if not (T_lo <= T_star <= T_hi):
        raise ValueError(f"T*={T_star} outside T_range {envelope['T_range']}")
    if not (S_lo <= S_star <= S_hi):
        raise ValueError(f"S*={S_star} outside S_range {envelope['S_range']}")
    if not (R_lo <= R_star <= R_hi):
        raise ValueError(f"R*={R_star} outside R_range {envelope['R_range']}")
    if H < 8:
        raise ValueError(f"H={H} too short; need >= 8 for family construction")

    g_star = _ars(T_star, S_star, R_star)

    # ── Family construction ───────────────────────────────────────────────

    if family == "F1_degrade":
        # ARS approaches g_star from above: T starts high, ramps down.
        T_start = _clamp(T_star + 0.25, T_lo, T_hi)
        S_start = _clamp(S_star, S_lo, S_hi)
        R_start = _clamp(R_star, R_lo, R_hi)
        h = _continuous_ramp(T_start, S_start, R_start,
                             T_star, S_star, R_star,
                             H, rng, dT_max, dS_max,
                             T_lo, T_hi, S_lo, S_hi, R_lo, R_hi)

    elif family == "F2_recover":
        # ARS approaches g_star from below: T starts low, ramps up.
        T_start = _clamp(T_star - 0.25, T_lo, T_hi)
        S_start = _clamp(S_star, S_lo, S_hi)
        R_start = _clamp(R_star, R_lo, R_hi)
        h = _continuous_ramp(T_start, S_start, R_start,
                             T_star, S_star, R_star,
                             H, rng, dT_max, dS_max,
                             T_lo, T_hi, S_lo, S_hi, R_lo, R_hi)

    elif family == "F3_counter_primed":
        # Build ONE continuous trajectory:
        # Steps 0..(H-tail-1): keep ARS above up_edge(band(g_star))+te,
        #   approaching from a starting T above that threshold.
        # Steps (H-tail)..(H-1): converge to x_star within envelope.
        # The counter `cu` increments on every above-threshold step, so
        # by the time we hit the terminal region it is primed.
        from policies import up_edge, to_state
        cur_band = to_state(g_star)
        ue = up_edge(cur_band)          # upper band edge
        g_above = ue + _TE + 0.02      # ARS needed to keep cu incrementing
        # T needed to hold g_above with S=S_star, R=R_lo (conservative):
        T_above = _clamp((g_above + 0.2*R_lo - 0.3*S_star) / 0.5, T_lo, T_hi)
        T_start = T_above
        S_start = _clamp(S_star, S_lo, S_hi)
        R_start = R_lo

        tail = max(4, int(H * 0.08))    # last ~8% of steps converge to x_star
        hold = H - tail                 # steps spent above threshold

        # Single continuous ramp via _continuous_ramp with a two-phase target:
        # We build it manually to guarantee:
        # (a) steps 0..hold-1 keep T >= T_above (counter primed)
        # (b) steps hold..H-2 converge to T_star (within envelope, step by step)
        # (c) step H-1 == x_star (S1)
        T = np.zeros(H); S = np.zeros(H); R = np.zeros(H)
        T[0] = _clamp(T_start, T_lo, T_hi)
        S[0] = _clamp(S_start, S_lo, S_hi)
        R[0] = float(rng.uniform(R_lo, R_hi))

        for t in range(1, hold):
            # Stay at T_above with small noise, bounded by envelope
            raw_T = T_above + rng.normal(0, dT_max * 0.1)
            raw_S = S_star  + rng.normal(0, dS_max * 0.1)
            dT = _clamp(raw_T - T[t-1], -dT_max, dT_max)
            dS = _clamp(raw_S - S[t-1], -dS_max, dS_max)
            T[t] = _clamp(T[t-1] + dT, T_lo, T_hi)
            S[t] = _clamp(S[t-1] + dS, S_lo, S_hi)
            R[t] = float(rng.uniform(R_lo, R_hi))

        # Convergence phase: ramp T from wherever we are to T_star
        for t in range(hold, H - 1):
            steps_left = H - 1 - t
            ideal_T = T[t-1] + (T_star - T[t-1]) / (steps_left + 1)
            ideal_S = S[t-1] + (S_star - S[t-1]) / (steps_left + 1)
            raw_T = ideal_T + rng.normal(0, dT_max * 0.05)
            raw_S = ideal_S + rng.normal(0, dS_max * 0.05)
            dT = _clamp(raw_T - T[t-1], -dT_max, dT_max)
            dS = _clamp(raw_S - S[t-1], -dS_max, dS_max)
            T[t] = _clamp(T[t-1] + dT, T_lo, T_hi)
            S[t] = _clamp(S[t-1] + dS, S_lo, S_hi)
            R[t] = float(rng.uniform(R_lo, R_hi))

        T[H-1] = float(T_star)   # S1
        S[H-1] = float(S_star)
        R[H-1] = float(R_star)
        h = np.column_stack([T, S, R])

    elif family == "F4_counter_reset":
        # Force ARS drop > tr=0.10 at the penultimate->terminal step to reset cu.
        # Strategy: at step H-2 set R to R_lo (minimum risk = highest ARS);
        # at step H-1 (terminal) R=R_star, T drops by dT_max, S drops by dS_max.
        # ARS drop = 0.5*dT_max + 0.3*dS_max + 0.2*(R_star - R_lo)
        max_ars_drop = (0.5 * dT_max + 0.3 * dS_max
                        + 0.2 * (R_star - R_lo))
        if max_ars_drop <= _TR:
            raise ValueError(
                f"F4 infeasible for R*={R_star:.3f}: max ARS drop "
                f"{max_ars_drop:.4f} <= tr={_TR} (Controlled Mode physical "
                f"constraint; target is out-of-support for F4)")

        # Penultimate T and S: must be reachable from T_star+dT_max, S_star+dS_max
        T_pen = _clamp(T_star + dT_max * 0.95, T_lo, T_hi)
        S_pen = _clamp(S_star + dS_max * 0.95, S_lo, S_hi)
        R_pen = R_lo   # minimum risk -> maximum ARS at penultimate step

        # Build the main body converging to (T_pen, S_pen, R_pen)
        T_start = _clamp(T_star - 0.15, T_lo, T_hi)
        h = _continuous_ramp(T_start, _clamp(S_star, S_lo, S_hi),
                             _clamp((R_lo+R_hi)/2, R_lo, R_hi),
                             T_pen, S_pen, R_pen,
                             H - 1, rng, dT_max, dS_max,
                             T_lo, T_hi, S_lo, S_hi, R_lo, R_hi)
        # Append terminal row: S1
        terminal = np.array([[T_star, S_star, R_star]])
        h = np.vstack([h, terminal])

    else:
        raise ValueError(f"unknown family {family!r}; must be one of {FAMILIES}")

    # ── Natural Mode overlay (S2, Revision 2) ────────────────────────────
    if mode == "natural":
        # Step 1: replace R column with phase-keyed draws (preserve terminal row).
        for t in range(H - 1):
            h[t, 2] = _risk_for_natural(t, rng, fault_t, recovery_t, R_lo, R_hi)
        # Step 2: inject scripted fault jump at fault_t.
        if fault_t < H - 1:
            fault_mag = float(rng.uniform(
                envelope["dT_fault_min"], envelope["dT_fault_max"]))
            h[fault_t, 0] = _clamp(h[fault_t, 0] - fault_mag, T_lo, T_hi)
        # Step 3: re-plan T and S from fault_t+1 onward so that subsequent
        # steps honour the envelope (A1/A2) starting from the post-fault value.
        # The re-plan is a bounded linear ramp from h[fault_t] to (T_star,S_star)
        # with noise, identical to _continuous_ramp's inner loop.
        replan_start = fault_t + 1
        if replan_start < H - 1:
            for t in range(replan_start, H - 1):
                steps_left = H - 1 - t
                ideal_T = h[t-1, 0] + (T_star - h[t-1, 0]) / (steps_left + 1)
                ideal_S = h[t-1, 1] + (S_star - h[t-1, 1]) / (steps_left + 1)
                raw_T = ideal_T + rng.normal(0, dT_max * 0.05)
                raw_S = ideal_S + rng.normal(0, dS_max * 0.05)
                dT = _clamp(raw_T - h[t-1, 0], -dT_max, dT_max)
                dS = _clamp(raw_S - h[t-1, 1], -dS_max, dS_max)
                h[t, 0] = _clamp(h[t-1, 0] + dT, T_lo, T_hi)
                h[t, 1] = _clamp(h[t-1, 1] + dS, S_lo, S_hi)
        # Step 4: S1 — terminal row must survive the overlay exactly.
        h[-1] = [T_star, S_star, R_star]

    elif mode != "controlled":
        raise ValueError(f"mode must be 'controlled' or 'natural', got {mode!r}")

    return h


# ---------------------------------------------------------------------------
# Assertion functions (S1, S2, S4, S3-check) — unchanged from spec
# ---------------------------------------------------------------------------

def assert_terminates_at(h: np.ndarray, x_star) -> None:
    T_star, S_star, R_star = float(x_star[0]), float(x_star[1]), float(x_star[2])
    assert h[-1, 0] == T_star, f"S1 T fail: {h[-1,0]} != {T_star}"
    assert h[-1, 1] == S_star, f"S1 S fail: {h[-1,1]} != {S_star}"
    assert h[-1, 2] == R_star, f"S1 R fail: {h[-1,2]} != {R_star}"


def assert_admissible(h: np.ndarray, envelope: dict, mode: str = "controlled") -> None:
    dT_max = float(envelope["dT_max"])
    dS_max = float(envelope["dS_max"])
    T_lo, T_hi = float(envelope["T_range"][0]), float(envelope["T_range"][1])
    S_lo, S_hi = float(envelope["S_range"][0]), float(envelope["S_range"][1])
    R_lo, R_hi = float(envelope["R_range"][0]), float(envelope["R_range"][1])
    fault_t    = int(envelope["scenario"]["fault_t"])
    H = len(h)
    for t in range(H):
        T_t, S_t, R_t = h[t, 0], h[t, 1], h[t, 2]
        assert T_lo <= T_t <= T_hi, f"A3 T range t={t}: {T_t}"
        assert S_lo <= S_t <= S_hi, f"A3 S range t={t}: {S_t}"
        assert R_lo <= R_t <= R_hi, f"A3 R range t={t}: {R_t}"
        if t >= 1:
            dT = abs(T_t - h[t-1, 0])
            dS = abs(S_t - h[t-1, 1])
            skip = (mode == "natural" and t == fault_t)
            if not skip:
                assert dT <= dT_max + 1e-9, f"A1 |dT|={dT:.5f} > {dT_max:.5f} at t={t}"
                assert dS <= dS_max + 1e-9, f"A2 |dS|={dS:.5f} > {dS_max:.5f} at t={t}"
    # A4
    dT_app = abs(h[-1, 0] - h[-2, 0])
    dS_app = abs(h[-1, 1] - h[-2, 1])
    assert dT_app <= dT_max + 1e-9, f"A4 terminal |dT|={dT_app:.5f} > {dT_max:.5f}"
    assert dS_app <= dS_max + 1e-9, f"A4 terminal |dS|={dS_app:.5f} > {dS_max:.5f}"


def assert_reproducible(x_star, family: str, seed: int, H: int,
                        mode: str, envelope: dict) -> None:
    h1 = gen_convergent(x_star, family, seed, H, mode, envelope)
    h2 = gen_convergent(x_star, family, seed, H, mode, envelope)
    assert np.array_equal(h1, h2), "S4 fail: regenerated history differs"


def assert_families_distinct(level_map: dict) -> None:
    levels = list(level_map.values())
    assert len(set(levels)) >= 2, (
        f"S3-check fail: all families yield the same level {levels}; "
        f"x_star is history-insensitive at this condition")
