from __future__ import annotations

"""Single source of truth for DecisionCore sovereignty and compatibility surfaces.

This module exists to keep every DecisionCore-named import path anchored to one
canonical implementation contract. It prevents semantic drift between the
sovereign issuer, thin public re-exports, and compatibility aliases.
"""

CANONICAL_DECISION_CORE_IMPORT_PATH = "core.ai.decision_core.DecisionCore"
CANONICAL_DECISION_CORE_MODULE = "core.ai.decision_core"
CANONICAL_DECISION_CORE_CLASS_NAME = "DecisionCore"
CANONICAL_DECISION_CORE_PUBLIC_MODULE = "core.decision_core"
COMPAT_DECISION_ENGINE_MODULE = "application.decision.decision_service.DecisionService"
PLATFORM_OPTIMIZATION_COMPAT_MODULE = "core.ai.decision_core"


def is_canonical_decision_core_path(path: str) -> bool:
    return str(path).strip() == CANONICAL_DECISION_CORE_IMPORT_PATH


__all__ = [
    "CANONICAL_DECISION_CORE_CLASS_NAME",
    "CANONICAL_DECISION_CORE_IMPORT_PATH",
    "CANONICAL_DECISION_CORE_MODULE",
    "CANONICAL_DECISION_CORE_PUBLIC_MODULE",
    "COMPAT_DECISION_ENGINE_MODULE",
    "PLATFORM_OPTIMIZATION_COMPAT_MODULE",
    "is_canonical_decision_core_path",
]
