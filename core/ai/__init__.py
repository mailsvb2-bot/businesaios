"""AI economy core namespace with lightweight package import."""

from __future__ import annotations

import importlib
from typing import Any

CANON_CORE_AI_NAMESPACE = True
CANON_DECISION_CORE_SINGLETON_IDENTITY = True
_COMPAT_ALIAS_MAP = {
    "decision_trace": "core.decision.ai_decision_trace",
    "decision_pricing": "application.decision_policy.pricing",
    "world_model_pinning": "kernel.world_model_pin",
    "world_state": "kernel.world_state",
}
_DECISION_CORE_SINGLETON: Any | None = None


def __getattr__(name: str) -> Any:
    if name in _COMPAT_ALIAS_MAP:
        module = importlib.import_module(_COMPAT_ALIAS_MAP[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def set_decision_core_singleton(core: Any) -> None:
    """Register the one process-wide decision issuer.

    Canonical boot constructs ``core.ai.decision_core.DecisionCore`` and calls
    this function before any executor or interface is exposed. A conflicting
    earlier registration therefore fails boot instead of silently replacing
    the decision owner.
    """

    global _DECISION_CORE_SINGLETON
    if core is None:
        raise TypeError("DECISIONCORE_MISSING")
    if _DECISION_CORE_SINGLETON is not None and _DECISION_CORE_SINGLETON is not core:
        from core.observability.arch_violation import log_arch_violation
        from core.runtime.safe_mode import enter_safe_mode

        log_arch_violation("MULTI_DECISIONCORE")
        enter_safe_mode("MULTI_DECISIONCORE")
        raise SystemExit("ARCH_VIOLATION: MULTI_DECISIONCORE")
    _DECISION_CORE_SINGLETON = core


def get_decision_core_singleton() -> Any:
    if _DECISION_CORE_SINGLETON is None:
        raise RuntimeError("DECISIONCORE_NOT_INITIALIZED")
    return _DECISION_CORE_SINGLETON


def require_decision_core_singleton(core: Any | None = None) -> Any:
    """Return the registered core and reject every alternate issuer identity."""

    registered = get_decision_core_singleton()
    if core is not None and core is not registered:
        raise RuntimeError("NONCANONICAL_DECISIONCORE")
    return registered


def reset_decision_core_singleton() -> None:
    """Testing/process-teardown hook; production boot never swaps the owner."""

    global _DECISION_CORE_SINGLETON
    _DECISION_CORE_SINGLETON = None


__all__ = [
    "CANON_CORE_AI_NAMESPACE",
    "CANON_DECISION_CORE_SINGLETON_IDENTITY",
    "decision_trace",
    "decision_pricing",
    "world_model_pinning",
    "world_state",
    "set_decision_core_singleton",
    "get_decision_core_singleton",
    "require_decision_core_singleton",
    "reset_decision_core_singleton",
]
