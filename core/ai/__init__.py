"""AI economy core namespace with lightweight package import."""
from __future__ import annotations
from typing import Any
import importlib

CANON_CORE_AI_NAMESPACE = True
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
    global _DECISION_CORE_SINGLETON
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

def reset_decision_core_singleton() -> None:
    global _DECISION_CORE_SINGLETON
    _DECISION_CORE_SINGLETON = None

__all__ = ["CANON_CORE_AI_NAMESPACE", "decision_trace", "decision_pricing", "world_model_pinning", "world_state", "set_decision_core_singleton", "get_decision_core_singleton", "reset_decision_core_singleton"]
