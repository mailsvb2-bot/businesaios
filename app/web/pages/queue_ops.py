from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from app.web.components import (
    ApprovalQueueCard,
    QueueHealthCard,
    QueueRemediationAnalyticsCard,
    QueueRemediationAuditCard,
    QueueRemediationHooksCard,
    RuntimeAlertsCard,
)
from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_QUEUE_OPS_PAGE = True


@dataclass(frozen=True, slots=True)
class QueueOpsPage:
    queue_health_card: QueueHealthCard = field(default_factory=QueueHealthCard)
    runtime_alerts_card: RuntimeAlertsCard = field(default_factory=RuntimeAlertsCard)
    queue_remediation_hooks_card: QueueRemediationHooksCard = field(default_factory=QueueRemediationHooksCard)
    queue_remediation_analytics_card: QueueRemediationAnalyticsCard = field(default_factory=QueueRemediationAnalyticsCard)
    queue_remediation_audit_card: QueueRemediationAuditCard = field(default_factory=QueueRemediationAuditCard)
    approval_queue_card: ApprovalQueueCard = field(default_factory=ApprovalQueueCard)
    kind: str = 'queue_ops_page'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        operator_summary = {'tenant_id': tenant_id, **dict(normalized.get('operator_summary') or {})}
        approval_preview = {'tenant_id': tenant_id, **dict(normalized.get('approval_preview') or {})}
        trend_preview = {'tenant_id': tenant_id, **dict(normalized.get('trend_preview') or {})}
        data_freshness = {'tenant_id': tenant_id, **dict(normalized.get('data_freshness') or {})}
        consistency = {'tenant_id': tenant_id, **dict(normalized.get('consistency') or {})}
        queue_name = str(normalized.get('queue_name') or '').strip()
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'queue_name': queue_name,
                'title': 'Queue Operations',
                'queue_health': normalized.get('queue_health'),
                'runtime_alerts': normalized.get('runtime_alerts'),
                'queue_remediation_hooks': normalized.get('queue_remediation_hooks'),
                'queue_remediation_analytics': normalized.get('queue_remediation_analytics'),
                'queue_remediation_audit': normalized.get('queue_remediation_audit'),
                'approval_queue': normalized.get('approval_queue'),
                'operator_summary': operator_summary,
                'timeline_preview': tuple(dict(item) for item in tuple(normalized.get('timeline_preview') or ())),
                'approval_preview': approval_preview,
                'trend_preview': trend_preview,
                'data_freshness': data_freshness,
                'evidence_timeline': tuple(dict(item) for item in tuple(normalized.get('evidence_timeline') or ())),
                'consistency': consistency,
                'tenant_bound': True,
            },
        )

    def build_runtime_view(self, *, tenant_id: str, reports: Iterable[Any], alerts: Iterable[Any], remediation_hooks: Iterable[Any] = (), remediation_analytics: Mapping[str, Any] | None = None, remediation_audit: Mapping[str, Any] | None = None, approvals: Iterable[Any] = (), operator_summary: Mapping[str, Any] | None = None, timeline_preview: Iterable[Mapping[str, Any]] = (), approval_preview: Mapping[str, Any] | None = None, trend_preview: Mapping[str, Any] | None = None, data_freshness: Mapping[str, Any] | None = None, evidence_timeline: Iterable[Mapping[str, Any]] = (), consistency: Mapping[str, Any] | None = None) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        reports_tuple = tuple(reports or ())
        queue_name = str(getattr(reports_tuple[0], 'queue_name', '') or '').strip() if reports_tuple else ''
        if not queue_name:
            queue_name = str((remediation_audit or {}).get('queue_name') or '').strip()
        if not queue_name:
            queue_name = str((remediation_analytics or {}).get('queue_name') or '').strip()
        return self.build(
            {
                'tenant_id': required_tenant_id,
                'queue_name': queue_name,
                'queue_health': self.queue_health_card.build_from_reports(tenant_id=required_tenant_id, reports=reports_tuple),
                'runtime_alerts': self.runtime_alerts_card.build_from_incidents(tenant_id=required_tenant_id, alerts=alerts, limit=50),
                'queue_remediation_hooks': self.queue_remediation_hooks_card.build_from_hooks(tenant_id=required_tenant_id, queue_name=queue_name, hooks=remediation_hooks),
                'queue_remediation_analytics': self.queue_remediation_analytics_card.build({'tenant_id': required_tenant_id, 'queue_name': queue_name, 'analytics': dict(remediation_analytics or {})}),
                'queue_remediation_audit': self.queue_remediation_audit_card.build({'tenant_id': required_tenant_id, 'queue_name': queue_name, 'rows': tuple(dict(item) for item in tuple((remediation_audit or {}).get('rows', ()) or ()))}),
                'approval_queue': self.approval_queue_card.build_from_records(tenant_id=required_tenant_id, records=approvals, limit=10) if tuple(approvals or ()) else None,
                'operator_summary': {'tenant_id': required_tenant_id, **dict(operator_summary or {})},
                'timeline_preview': tuple(dict(item) for item in tuple(timeline_preview or ())),
                'approval_preview': {'tenant_id': required_tenant_id, **dict(approval_preview or {})},
                'trend_preview': {'tenant_id': required_tenant_id, **dict(trend_preview or {})},
                'data_freshness': {'tenant_id': required_tenant_id, **dict(data_freshness or {})},
                'evidence_timeline': tuple(dict(item) for item in tuple(evidence_timeline or ())),
                'consistency': {'tenant_id': required_tenant_id, **dict(consistency or {})},
            }
        )


__all__ = ['CANON_WEB_QUEUE_OPS_PAGE', 'QueueOpsPage']
