from __future__ import annotations

from application.decision.decision_service import (
    NON_SOVEREIGN_ENGINE_ROLE,
)
from application.decision.decision_service import (
    DecisionApplicationService as _CanonicalDecisionApplicationService,
)
from application.decision.decision_service import (
    DecisionService as _CanonicalDecisionService,
)


class DecisionApplicationService(_CanonicalDecisionApplicationService):
    """Compatibility application-service wrapper.

    Final owner: application.decision.decision_service
    """


class DecisionService(_CanonicalDecisionService):
    """Compatibility decision-service wrapper preserving the core.application import path."""


CANON_CORE_APPLICATION_DECISION_SERVICE_COMPAT = True

__all__ = [
    'DecisionApplicationService',
    'DecisionService',
    'NON_SOVEREIGN_ENGINE_ROLE',
    'CANON_CORE_APPLICATION_DECISION_SERVICE_COMPAT',
    '_CanonicalDecisionApplicationService',
    '_CanonicalDecisionService',
]
