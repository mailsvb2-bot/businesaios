from __future__ import annotations

from dataclasses import dataclass, field

from entrypoints.api.baseline_models import (
    PromoteBaselineRequest,
    PromoteBaselineResponse,
    SelectBaselineRequest,
    SelectBaselineResponse,
)
from entrypoints.api.governance_route_handlers import GovernanceRouteHandlers


CANON_API_BASELINE_ROUTE_HANDLERS_FINAL_OWNER = True
CANON_API_BASELINE_ROUTE_HANDLERS = True


@dataclass(frozen=True)
class BaselineRouteHandlers:
    """
    Canonical compatibility adapter for baseline routes in V11/V13.

    This preserves the dedicated baseline surface that existed in older builds,
    while keeping GovernanceRouteHandlers as the single owner of baseline logic.
    """

    delegate: GovernanceRouteHandlers = field(default_factory=GovernanceRouteHandlers)

    @classmethod
    def build_default(cls) -> "BaselineRouteHandlers":
        return cls(delegate=GovernanceRouteHandlers())

    def promote(self, request: PromoteBaselineRequest) -> PromoteBaselineResponse:
        return self.delegate.promote_baseline(request)

    def promote_baseline(self, request: PromoteBaselineRequest) -> PromoteBaselineResponse:
        return self.delegate.promote_baseline(request)

    def handle_promote_baseline(self, request: PromoteBaselineRequest) -> PromoteBaselineResponse:
        return self.delegate.promote_baseline(request)

    def handle_select_baseline(self, request: SelectBaselineRequest) -> SelectBaselineResponse:
        return self.delegate.select_baseline(request)

    def select_baseline(self, request: SelectBaselineRequest) -> SelectBaselineResponse:
        return self.delegate.select_baseline(request)


__all__ = [
    "BaselineRouteHandlers",
    "CANON_API_BASELINE_ROUTE_HANDLERS",
]
