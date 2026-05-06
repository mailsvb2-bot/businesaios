from __future__ import annotations

from dataclasses import dataclass

from core.tenancy.normalization import require_tenant_id
from typing import Protocol

from runtime.queue.queue_remediation_audit_sqlite import QueueRemediationExecutionAuditEntry, QueueRemediationPlanAuditEntry
from runtime.queue.queue_remediation_route_history_sqlite import QueueRemediationRouteHistoryEntry

CANON_RUNTIME_QUEUE_REMEDIATION_ANALYTICS = True

class QueueRemediationAuditReader(Protocol):
    def list_plan_entries(self, *, tenant_id: str, queue_name: str, limit: int = 50) -> tuple[QueueRemediationPlanAuditEntry, ...]: ...
    def list_execution_entries(self, *, tenant_id: str, queue_name: str, limit: int = 50) -> tuple[QueueRemediationExecutionAuditEntry, ...]: ...

class QueueRemediationRouteHistoryReader(Protocol):
    def list_entries(self, *, tenant_id: str, queue_name: str, limit: int = 50) -> tuple[QueueRemediationRouteHistoryEntry, ...]: ...

@dataclass(frozen=True)
class QueueRemediationAnalyticsReport:
    tenant_id: str
    queue_name: str
    plan_count: int
    execution_count: int
    executed_count: int
    review_required_count: int
    route_event_count: int
    most_used_hook_code: str | None
    most_used_action: str | None
    last_plan_at: str | None
    last_execution_at: str | None
    last_route_event_at: str | None
    category_counts: dict[str, int]
    reason_counts: dict[str, int]
    action_counts: dict[str, int]
    status_counts: dict[str, int]
    source_counts: dict[str, int]
    hook_offer_counts: dict[str, int]
    top_unexecuted_hook_code: str | None
    execution_rate: float

    def as_dict(self) -> dict[str, object]:
        return self.__dict__.copy()

@dataclass(frozen=True)
class QueueRemediationAnalyticsService:
    audit_store: QueueRemediationAuditReader
    route_history_store: QueueRemediationRouteHistoryReader | None = None

    def summarize(self, *, tenant_id: str, queue_name: str, limit: int = 200) -> QueueRemediationAnalyticsReport:
        normalized_tenant_id = require_tenant_id(tenant_id)
        normalized_queue_name = str(queue_name or '').strip()
        if not normalized_queue_name:
            raise ValueError('queue_name is required')
        normalized_limit = max(1, int(limit))
        plans = tuple(self.audit_store.list_plan_entries(tenant_id=normalized_tenant_id, queue_name=normalized_queue_name, limit=normalized_limit))
        executions = tuple(self.audit_store.list_execution_entries(tenant_id=normalized_tenant_id, queue_name=normalized_queue_name, limit=normalized_limit))
        routes = tuple(self.route_history_store.list_entries(tenant_id=normalized_tenant_id, queue_name=normalized_queue_name, limit=normalized_limit)) if self.route_history_store is not None else ()
        category_counts: dict[str, int] = {}
        reason_counts: dict[str, int] = {}
        action_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        source_counts: dict[str, int] = {}
        hook_counts: dict[str, int] = {}
        hook_offer_counts: dict[str, int] = {}
        for item in plans:
            for hook in tuple(item.hooks or ()):
                code = str(dict(hook).get('code') or '').strip()
                if code:
                    hook_offer_counts[code] = hook_offer_counts.get(code, 0) + 1
        for item in executions:
            category = str(item.category or '').strip() or 'unknown'
            reason = str(item.reason or '').strip() or 'unknown'
            hook_code = str(item.hook_code or '').strip()
            category_counts[category] = category_counts.get(category, 0) + 1
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            if hook_code:
                hook_counts[hook_code] = hook_counts.get(hook_code, 0) + 1
        for item in routes:
            action = str(item.action or '').strip() or 'unknown'
            status = str(item.status or '').strip() or 'unknown'
            source = str(item.source or '').strip() or 'unknown'
            action_counts[action] = action_counts.get(action, 0) + 1
            status_counts[status] = status_counts.get(status, 0) + 1
            source_counts[source] = source_counts.get(source, 0) + 1
        return QueueRemediationAnalyticsReport(
            tenant_id=normalized_tenant_id,
            queue_name=normalized_queue_name,
            plan_count=len(plans),
            execution_count=len(executions),
            executed_count=sum(1 for x in executions if x.executed),
            review_required_count=sum(1 for x in executions if not x.executed),
            route_event_count=len(routes),
            most_used_hook_code=_top_key(hook_counts),
            most_used_action=_top_key(action_counts),
            last_plan_at=plans[0].generated_at.isoformat() if plans else None,
            last_execution_at=executions[0].executed_at.isoformat() if executions else None,
            last_route_event_at=routes[0].recorded_at.isoformat() if routes else None,
            category_counts=category_counts,
            reason_counts=reason_counts,
            action_counts=action_counts,
            status_counts=status_counts,
            source_counts=source_counts,
            hook_offer_counts=hook_offer_counts,
            top_unexecuted_hook_code=_top_unexecuted_hook_code(hook_offer_counts=hook_offer_counts, hook_counts=hook_counts),
            execution_rate=0.0 if not plans else round(min(1.0, sum(1 for x in executions if x.executed) / max(1, sum(len(tuple(item.hooks or ())) for item in plans))), 4),
        )

def _top_key(values: dict[str, int]) -> str | None:
    if not values:
        return None
    return sorted(values.items(), key=lambda item: (-item[1], item[0]))[0][0]

__all__ = ['CANON_RUNTIME_QUEUE_REMEDIATION_ANALYTICS', 'QueueRemediationAnalyticsReport', 'QueueRemediationAnalyticsService']


def _top_unexecuted_hook_code(*, hook_offer_counts: dict[str, int], hook_counts: dict[str, int]) -> str | None:
    candidates = {key: int(hook_offer_counts.get(key, 0)) - int(hook_counts.get(key, 0)) for key in hook_offer_counts}
    candidates = {key: value for key, value in candidates.items() if value > 0}
    if not candidates:
        return None
    return sorted(candidates.items(), key=lambda item: (-item[1], item[0]))[0][0]
