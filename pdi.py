"""
PDI add-on: drive an existing policy over a single history and read the
terminal authorization level. Pure add-on -- imports policies/sim read-only,
edits nothing. Phase 1 scope: adapter + nothing else.

An "existing policy" here is any BasePolicy from policies.py. Its public
contract is update(T, S, R, state=None) -> np.ndarray[int], which consumes a
FULL signal history and returns the level at every step. To measure PDI we
feed a constructed history whose terminal condition is the target x*, run the
policy over the whole history, and read the last level a[-1]. Because the
per-step carry (the `cu` counter) is internal and not injectable, we obtain it
the only correct way: by letting the policy build it up over the real history.
"""
from __future__ import annotations
import numpy as np
from policies import BasePolicy


def emit_terminal_level(policy: BasePolicy, history) -> int:
    """Run `policy` over a full (T,S,R) history; return the level at the last step.

    history: array-like of shape (H, 3), rows are (T, S, R) per step, in order,
    with the final row equal to the target condition x*.
    """
    hist = np.asarray(history, dtype=float)
    assert hist.ndim == 2 and hist.shape[1] == 3, f"history must be (H,3), got {hist.shape}"
    assert hist.shape[0] >= 1, "history must have >= 1 step"
    T, S, R = hist[:, 0], hist[:, 1], hist[:, 2]
    a = policy.update(T, S, R)          # canonical warm-start (state=None), as in all reported results
    a = np.asarray(a, dtype=int)
    assert a.shape[0] == hist.shape[0], f"level series {a.shape} != history len {hist.shape[0]}"
    return int(a[-1])


def emit_level_series(policy: BasePolicy, history) -> np.ndarray:
    """Full level trajectory for a history (used by tests / diagnostics)."""
    hist = np.asarray(history, dtype=float)
    T, S, R = hist[:, 0], hist[:, 1], hist[:, 2]
    return np.asarray(policy.update(T, S, R), dtype=int)
