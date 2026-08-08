"""
Experimental policy variants used by the existing Table V / Table VII baselines.

These are deliberately NOT part of the core policy set. Each is the TRAP
transition rule applied to a single alternative input signal -- raw trust, or
inverted risk -- which is exactly the relationship in the original code
(``tr_tdaa(T, ...)`` and ``tr_tdaa(1 - R, ...)``). They therefore subclass
``TRAPPolicy`` and override only ``signal(...)``; the decision rule, parameters,
and warm-start behavior are inherited unchanged.

Importing this module self-registers the legacy method strings ``'trust'`` and
``'risk'`` into ``POLICY_REGISTRY`` so that ``sim.run('trust')`` / ``run('risk')``
(used to reproduce Tables V and VII) continue to resolve.
"""
from __future__ import annotations

from policies import TRAPPolicy, register


@register("trust")
class TrustOnlyPolicy(TRAPPolicy):
    """TRAP rule driven by the raw trust trace.

    Ignores stability, risk, and the ARS weights -- the decision signal is trust
    itself. Equivalent to the original ``tr_tdaa(T, te, tr, k)`` dispatch.
    """

    def signal(self, T, S, R):
        return T


@register("risk")
class RiskOnlyPolicy(TRAPPolicy):
    """TRAP rule driven by inverted risk ``1 - R``.

    Ignores trust, stability, and the ARS weights. Equivalent to the original
    ``tr_tdaa(1 - R, te, tr, k)`` dispatch.
    """

    def signal(self, T, S, R):
        return 1 - R
