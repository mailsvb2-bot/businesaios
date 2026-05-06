from __future__ import annotations

from dataclasses import dataclass, field

from entrypoints.api.drift_models import (
    DriftAuditRequest,
    DriftAuditResponse,
    RollbackBaselineRequest,
    RollbackBaselineResponse,
)
from entrypoints.api.governance_route_handlers import GovernanceRouteHandlers


CANON_API_DRIFT_ROUTE_HANDLERS_FINAL_OWNER = True
CANON_API_DRIFT_ROUTE_HANDLERS = True


@dataclass(frozen=True)
class DriftRouteHandlers:
    """
    Canonical compatibility adapter for drift / rollback routes in V11/V13.

    This file deliberately restores the older API surface without owning drift
    policy or rollback logic itself.
    """

    delegate: GovernanceRouteHandlers = field(default_factory=GovernanceRouteHandlers)

    @classmethod
    def build_default(cls) -> "DriftRouteHandlers":
        return cls(delegate=GovernanceRouteHandlers())

    def audit(self, request: DriftAuditRequest) -> DriftAuditResponse:
        return self.delegate.audit_drift(request)

    def audit_drift(self, request: DriftAuditRequest) -> DriftAuditResponse:
        return self.delegate.audit_drift(request)

    def handle_audit_drift(self, request: DriftAuditRequest) -> DriftAuditResponse:
        return self.delegate.audit_drift(request)

    def rollback(self, request: RollbackBaselineRequest) -> RollbackBaselineResponse:
        return self.delegate.rollback_baseline(request)

    def rollback_baseline(self, request: RollbackBaselineRequest) -> RollbackBaselineResponse:
        return self.delegate.rollback_baseline(request)

    def handle_rollback_baseline(self, request: RollbackBaselineRequest) -> RollbackBaselineResponse:
        return self.delegate.rollback_baseline(request)


__all__ = [
    "DriftRouteHandlers",
    "CANON_API_DRIFT_ROUTE_HANDLERS",
]
