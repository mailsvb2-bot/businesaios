from __future__ import annotations

"""Compatibility surface for the canonical decision application service owner."""

from application.decision.decision_service import (
    DecisionApplicationService,
    DecisionService,
    NON_SOVEREIGN_ENGINE_ROLE,
)

CANON_CORE_DECISION_APPLICATION_SERVICE_COMPAT = True
CANONICAL_OWNER_APPLICATION_SERVICE = "application.decision.decision_service"

__all__ = [
    "CANON_CORE_DECISION_APPLICATION_SERVICE_COMPAT",
    "CANONICAL_OWNER_APPLICATION_SERVICE",
    "DecisionApplicationService",
    "DecisionService",
    "NON_SOVEREIGN_ENGINE_ROLE",
]
