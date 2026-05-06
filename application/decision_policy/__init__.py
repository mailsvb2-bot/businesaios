"""Decision policy namespace with lazy exports."""
from __future__ import annotations
from typing import Any
import importlib
_EXPORT_MAP = {
    "propose_action": "application.decision_policy.policy_stage",
    "allowed_price_band": "application.decision_policy.pricing",
    "band_rank": "application.decision_policy.pricing",
    "merge_price_constraints": "application.decision_policy.pricing",
    "DecisionSafetyConfig": "application.decision_policy.safety",
    "gate_decision_action": "application.decision_policy.safety",
}

def __getattr__(name: str) -> Any:
    if name in _EXPORT_MAP:
        module = importlib.import_module(_EXPORT_MAP[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
__all__ = sorted(_EXPORT_MAP)
