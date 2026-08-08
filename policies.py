"""
Policy-independent authorization architecture for the TRAP simulation.

This module owns the *authorization-band substrate* (band thresholds and the
value->band mapping) and the policy classes that decide an authorization
trajectory from trust/stability/risk traces. It deliberately depends on nothing
in ``sim.py`` -- the dependency direction is ``sim.py -> policies.py`` only, so
there is no import cycle.

Design goals
------------
* The simulator (``sim.run``) is policy-agnostic: it calls ``policy.update(...)``
  and never branches on policy type. Swapping the policy object is the only
  thing required to evaluate a different authorization policy.
* A future experiment runner can evaluate many policies under identical
  conditions by passing policy *objects* into ``sim.run(policy=...)`` with a
  fixed seed -- no simulator change required (see ``make_policy`` /
  ``POLICY_REGISTRY``).
* Numerical behavior is identical to the original ``sim.py``. The per-step
  band-transition rules are lifted verbatim; the only edits are (a) deriving the
  horizon from ``len(signal)`` instead of a module-global ``T_END`` (identical
  for the fixed 100-step horizon) and (b) an *optional* warm-start ``init_state``
  that defaults to the original initialization.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

# ---------------------------------------------------------------------------
# Authorization-band substrate (moved verbatim from the original sim.py).
# These define the authorization model the policies operate on; they are not
# trust/stability/risk generation and not evaluation metrics.
# ---------------------------------------------------------------------------
BANDS = [0.20, 0.35, 0.50, 0.65, 0.80]


def to_state(x):
    s = 0
    for b in BANDS:
        if x >= b:
            s += 1
    return s


def up_edge(a):
    return BANDS[a] if a < 5 else 1e9


def low_edge(a):
    return BANDS[a - 1] if a >= 1 else -1e9


# ---------------------------------------------------------------------------
# Transition rules (verbatim logic; T_END -> len(sc); optional init_state).
#
# These remain module-level functions so that existing reproducibility scripts
# that reference them by name (e.g. verify_tables.py) keep working unchanged.
# The policy classes below call exactly these functions, so there is a single
# source of truth and no risk of the class logic drifting from the originals.
#
# `init_state` is the optional incoming authorization state. When None (the
# canonical configuration that produces every reported result) the trajectory is
# initialized from the signal exactly as before, so outputs are byte-identical.
# ---------------------------------------------------------------------------
def tr_static(sc, init_state=None):
    n = len(sc)
    base = to_state(sc[0]) if init_state is None else int(init_state)
    return np.full(n, base, dtype=int)


def tr_tdaa(sc, te, tr, k, init_state=None):
    n = len(sc)
    a = np.zeros(n, dtype=int)
    a[0] = to_state(sc[0]) if init_state is None else int(init_state)
    cu = 0
    for t in range(1, n):
        d = sc[t] - sc[t - 1]
        a[t] = a[t - 1]
        if d < -tr:                                   # rapid restriction -> jump to mapped band
            a[t] = min(a[t - 1], to_state(sc[t]))
            cu = 0
        elif sc[t] >= up_edge(a[t - 1]) + te:         # cautious escalation, k consecutive
            cu += 1
            if cu >= k:
                a[t] = a[t - 1] + 1
                cu = 0
        else:
            cu = 0
    return a


def tr_sym(sc, th, k, init_state=None):               # symmetric: k consecutive in both directions
    n = len(sc)
    a = np.zeros(n, dtype=int)
    a[0] = to_state(sc[0]) if init_state is None else int(init_state)
    cu = cd = 0
    for t in range(1, n):
        a[t] = a[t - 1]
        if sc[t] >= up_edge(a[t - 1]) + th:
            cu += 1
            cd = 0
            if cu >= k:
                a[t] = a[t - 1] + 1
                cu = 0
        elif sc[t] < low_edge(a[t - 1]) - th:
            cd += 1
            cu = 0
            if cd >= k:
                a[t] = a[t - 1] - 1
                cd = 0
        else:
            cu = cd = 0
    return a


# ---------------------------------------------------------------------------
# Policy registry: enables name-based construction so an experiment runner can
# enumerate/instantiate policies without the simulator hard-coding any of them.
# Modules register their policies via the @register decorator; importing the
# module is what populates the registry (variants.py registers 'trust'/'risk').
# ---------------------------------------------------------------------------
POLICY_REGISTRY: "dict[str, type[BasePolicy]]" = {}


def register(*names):
    def deco(cls):
        for nm in names:
            POLICY_REGISTRY[nm] = cls
        return cls
    return deco


def make_policy(method, w=(0.5, 0.3, 0.2), te=0.05, tr=0.10, k=3) -> "BasePolicy":
    """Construct a policy object from a legacy method string + run-level params.

    The parameter wiring matches the original ``sim.py`` dispatch exactly --
    notably, the symmetric policy is fed ``te`` (not ``tr``), and the trust/risk
    variants ignore the weights ``w``. Unknown names raise ``ValueError``.
    """
    cls = POLICY_REGISTRY.get(method)
    if cls is None:
        raise ValueError(
            f"unknown policy/method: {method!r}; registered: {sorted(POLICY_REGISTRY)}"
        )
    return cls.from_run_params(w=w, te=te, tr=tr, k=k)


# ---------------------------------------------------------------------------
# Policy interface
# ---------------------------------------------------------------------------
class BasePolicy(ABC):
    """An authorization policy maps trust/stability/risk traces to an
    authorization-band trajectory.

    Subclasses implement two things:

    * ``signal(T, S, R) -> np.ndarray`` -- the per-timestep decision signal the
      policy derives from the raw traces (e.g. the composite ARS, raw trust, or
      inverted risk). Keeping signal derivation inside the policy is what makes
      the simulator signal-agnostic.
    * ``update(T, S, R, state=None) -> np.ndarray[int]`` -- the authorization
      band at each timestep.

    ``state`` is the OPTIONAL incoming authorization state (warm-start). When
    ``None`` -- the canonical configuration used for all reported results -- the
    trajectory is initialized from the policy's own signal exactly as in the
    original implementation, so outputs are unchanged. A non-``None`` ``state``
    lets a future online/segmented experiment resume from a known band without
    any change to the simulator or to the default numerical behavior. The
    per-step carry (consecutive-observation counters) is an internal
    implementation detail and is intentionally not part of this interface.
    """

    @abstractmethod
    def update(self, T, S, R, state=None) -> np.ndarray:
        ...

    @classmethod
    def from_run_params(cls, w=(0.5, 0.3, 0.2), te=0.05, tr=0.10, k=3) -> "BasePolicy":
        # Default adapter: ignore unused run-level params. Concrete policies
        # override to forward exactly the parameters they consume.
        return cls()


@register("static")
class StaticPolicy(BasePolicy):
    """Fixed authorization band derived from the initial composite signal."""

    def __init__(self, w=(0.5, 0.3, 0.2)):
        self.w = w

    def signal(self, T, S, R):
        w = self.w
        return w[0] * T + w[1] * S - w[2] * R

    def update(self, T, S, R, state=None):
        return tr_static(self.signal(T, S, R), init_state=state)

    @classmethod
    def from_run_params(cls, w=(0.5, 0.3, 0.2), te=0.05, tr=0.10, k=3):
        return cls(w=w)


@register("sym")
class SymmetricPolicy(BasePolicy):
    """Symmetric k-consecutive escalation/restriction on the composite signal.

    The threshold is the escalation threshold ``te``: the original code wires
    ``te`` into the symmetric rule and leaves ``tr`` unused, which is preserved
    here exactly.
    """

    def __init__(self, w=(0.5, 0.3, 0.2), te=0.05, k=3):
        self.w = w
        self.te = te
        self.k = k

    def signal(self, T, S, R):
        w = self.w
        return w[0] * T + w[1] * S - w[2] * R

    def update(self, T, S, R, state=None):
        return tr_sym(self.signal(T, S, R), self.te, self.k, init_state=state)

    @classmethod
    def from_run_params(cls, w=(0.5, 0.3, 0.2), te=0.05, tr=0.10, k=3):
        return cls(w=w, te=te, k=k)


@register("tdaa", "trap")
class TRAPPolicy(BasePolicy):
    """Trust-Responsive Authorization Policy (canonical policy).

    Asymmetric rule on the composite signal ``ARS = w0*T + w1*S - w2*R``:

    * a rapid restriction (signal drop greater than ``tr``) jumps immediately to
      the mapped band;
    * escalation is cautious -- it requires ``k`` consecutive steps above the
      upper band edge plus ``te``.

    The manuscript historically names this policy TDAA. ``TDAAPolicy`` is kept as
    an alias and the registry key ``'tdaa'`` is retained so that existing outputs
    and the verification harness remain byte-identical until an explicit,
    output-changing rename.
    """

    def __init__(self, w=(0.5, 0.3, 0.2), te=0.05, tr=0.10, k=3):
        self.w = w
        self.te = te
        self.tr = tr
        self.k = k

    def signal(self, T, S, R):
        w = self.w
        return w[0] * T + w[1] * S - w[2] * R

    def update(self, T, S, R, state=None):
        return tr_tdaa(self.signal(T, S, R), self.te, self.tr, self.k, init_state=state)

    @classmethod
    def from_run_params(cls, w=(0.5, 0.3, 0.2), te=0.05, tr=0.10, k=3):
        return cls(w=w, te=te, tr=tr, k=k)


# Backward-compatibility alias (until an explicit, output-changing rename).
TDAAPolicy = TRAPPolicy
