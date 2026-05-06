from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_QUEUE_REMEDIATION_ANALYTICS_CARD = True

@dataclass(frozen=True, slots=True)
class QueueRemediationAnalyticsCard:
    kind: str = 'queue_remediation_analytics_card'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        analytics = dict(normalized.get('analytics') or {})
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': require_tenant_id(normalized.get('tenant_id')),
                'queue_name': str(normalized.get('queue_name') or '').strip(),
                'analytics': analytics,
                'has_activity': bool(int(analytics.get('plan_count', 0) or 0) or int(analytics.get('execution_count', 0) or 0) or int(analytics.get('route_event_count', 0) or 0)),
                'tenant_bound': True,
            },
        )

__all__ = ['CANON_WEB_QUEUE_REMEDIATION_ANALYTICS_CARD', 'QueueRemediationAnalyticsCard']
