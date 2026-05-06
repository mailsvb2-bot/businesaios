from __future__ import annotations

from dataclasses import dataclass, field

from execution.headless_boot import build_headless_runtime

from entrypoints.api.business_memory_models import (
    BusinessMemoryGetRequest,
    BusinessMemoryRecentRunsRequest,
    BusinessMemoryPatternsResponse,
    BusinessMemoryRecentRunsResponse,
    BusinessMemoryResponse,
    BusinessMemorySummaryRequest,
    BusinessMemorySummaryResponse,
)
from entrypoints.api.headless_runtime_provider import HeadlessRuntimeProvider, build_default_headless_runtime_provider, build_headless_runtime_provider


CANON_API_BUSINESS_MEMORY_ROUTE_HANDLERS_FINAL_OWNER = True
CANON_API_BUSINESS_MEMORY_ROUTE_HANDLERS = True
CANON_API_BUSINESS_MEMORY_ROUTE_HANDLERS_SINGLE_RUNTIME_PROVIDER = True


def _bootstrap_headless_runtime() -> object:
    return globals()["build_headless_runtime"]()


def _default_runtime_provider() -> HeadlessRuntimeProvider:
    return build_headless_runtime_provider(runtime=_bootstrap_headless_runtime())



def build_business_memory_route_handlers(*, runtime_provider: HeadlessRuntimeProvider | None = None) -> "BusinessMemoryRouteHandlers":
    return BusinessMemoryRouteHandlers(runtime_provider=runtime_provider or build_default_headless_runtime_provider())


@dataclass(frozen=True)
class BusinessMemoryRouteHandlers:
    """Read-only boundary for business memory."""

    runtime_provider: HeadlessRuntimeProvider = field(default_factory=_default_runtime_provider)

    def get_memory(self, request: BusinessMemoryGetRequest) -> BusinessMemoryResponse:
        payload = self.runtime_provider.business_memory_query().get_memory(
            tenant_id=request.tenant_id,
            business_id=request.business_id,
        )
        return BusinessMemoryResponse(payload=payload)

    def get_summary(self, request: BusinessMemorySummaryRequest) -> BusinessMemorySummaryResponse:
        payload = self.runtime_provider.business_memory_query().get_summary(
            tenant_id=request.tenant_id,
            business_id=request.business_id,
        )
        return BusinessMemorySummaryResponse(
            tenant_id=str(payload.get("tenant_id") or request.tenant_id),
            business_id=str(payload.get("business_id") or request.business_id),
            total_runs=int(payload.get("total_runs") or 0),
            completed_runs=int(payload.get("completed_runs") or 0),
            failed_runs=int(payload.get("failed_runs") or 0),
            average_goal_score=float(payload.get("average_goal_score") or 0.0),
            active_goals=list(payload.get("active_goals") or []),
            learned_preferences=dict(payload.get("learned_preferences") or {}),
            recurring_failures=list(payload.get("recurring_failures") or []),
            recurring_wins=list(payload.get("recurring_wins") or []),
            anti_patterns=list(payload.get("anti_patterns") or []),
            trends=dict(payload.get("trends") or {}),
        )

    def get_recent_runs(self, request: BusinessMemoryRecentRunsRequest) -> BusinessMemoryRecentRunsResponse:
        runs = self.runtime_provider.business_memory_query().get_recent_runs(
            tenant_id=request.tenant_id,
            business_id=request.business_id,
            limit=request.limit,
        )
        return BusinessMemoryRecentRunsResponse(runs=list(runs))

    def get_failures(self, request: BusinessMemorySummaryRequest) -> BusinessMemoryPatternsResponse:
        patterns = self.runtime_provider.business_memory_query().get_recurring_failures(
            tenant_id=request.tenant_id,
            business_id=request.business_id,
        )
        return BusinessMemoryPatternsResponse(patterns=list(patterns))

    def get_wins(self, request: BusinessMemorySummaryRequest) -> BusinessMemoryPatternsResponse:
        patterns = self.runtime_provider.business_memory_query().get_recurring_wins(
            tenant_id=request.tenant_id,
            business_id=request.business_id,
        )
        return BusinessMemoryPatternsResponse(patterns=list(patterns))
