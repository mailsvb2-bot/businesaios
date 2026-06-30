"""Compatibility surface for the canonical decision application service owner."""

from __future__ import annotations

from application.decision.decision_service import (
    NON_SOVEREIGN_ENGINE_ROLE,
    DecisionApplicationService,
    DecisionService,
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

