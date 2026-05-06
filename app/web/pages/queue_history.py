from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from app.web.components import QueueAlertHistoryCard
from app.web.components import QueueRollupTimelineCard
from app.web.components import QueueRemediationAuditCard
from app.web.components import QueueRemediationAnalyticsCard
from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload


CANON_WEB_QUEUE_HISTORY_PAGE = True


@dataclass(frozen=True, slots=True)
class QueueHistoryPage:
    queue_rollup_timeline_card: QueueRollupTimelineCard = field(default_factory=QueueRollupTimelineCard)
    queue_alert_history_card: QueueAlertHistoryCard = field(default_factory=QueueAlertHistoryCard)
    queue_remediation_audit_card: QueueRemediationAuditCard = field(default_factory=QueueRemediationAuditCard)
    queue_remediation_analytics_card: QueueRemediationAnalyticsCard = field(default_factory=QueueRemediationAnalyticsCard)
    kind: str = 'queue_history_page'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'title': 'Queue History',
                'queue_timeline': normalized.get('queue_timeline'),
                'queue_alert_history': normalized.get('queue_alert_history'),
                'queue_remediation_audit': normalized.get('queue_remediation_audit'),
                'queue_remediation_analytics': normalized.get('queue_remediation_analytics'),
                'tenant_bound': True,
            },
        )

    def build_runtime_view(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        windows: Iterable[Any],
        alerts: Iterable[Any],
        remediation_plans: Iterable[Any] = (),
        remediation_executions: Iterable[Any] = (),
        remediation_route_history: Iterable[Any] = (),
        remediation_analytics: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        return self.build(
            {
                'tenant_id': required_tenant_id,
                'queue_timeline': self.queue_rollup_timeline_card.build_from_window_summaries(
                    tenant_id=required_tenant_id,
                    queue_name=queue_name,
                    windows=windows,
                ),
                'queue_alert_history': self.queue_alert_history_card.build_from_alerts(
                    tenant_id=required_tenant_id,
                    queue_name=queue_name,
                    alerts=alerts,
                    limit=100,
                ),
                'queue_remediation_audit': self.queue_remediation_audit_card.build_from_audit(
                    tenant_id=required_tenant_id,
                    queue_name=queue_name,
                    plans=remediation_plans,
                    executions=remediation_executions,
                    route_history=remediation_route_history,
                    limit=100,
                ),
                'queue_remediation_analytics': self.queue_remediation_analytics_card.build(
                    {
                        'tenant_id': required_tenant_id,
                        'queue_name': queue_name,
                        'analytics': dict(remediation_analytics or {}),
                    }
                ),
            }
        )


__all__ = ['CANON_WEB_QUEUE_HISTORY_PAGE', 'QueueHistoryPage']
