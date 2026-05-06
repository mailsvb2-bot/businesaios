from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from application.analytics.analytics_alert_dedup_service import AnalyticsAlertDedupService
from application.analytics.analytics_alert_escalation_service import AnalyticsAlertEscalationService
from application.analytics.analytics_delivery_contract import AnalyticsDeliverySink


@dataclass
class AnalyticsDeliveryService:
    sinks: dict[str, AnalyticsDeliverySink]
    _dedup: AnalyticsAlertDedupService = field(default_factory=AnalyticsAlertDedupService)
    _escalation: AnalyticsAlertEscalationService = field(default_factory=AnalyticsAlertEscalationService)

    def deliver_alert_batch(self, *, tenant_id: str, channel: str, alerts: list[Mapping[str, Any]]) -> dict[str, Any]:
        deduped = self._dedup.deduplicate(alerts=alerts)
        escalated = self._escalation.escalate(alerts=deduped)
        sink = self.sinks[channel]
        return sink.deliver(tenant_id=str(tenant_id), payload={"kind": "analytics_alert_batch", "alerts": escalated})

    def deliver_export_manifest(self, *, tenant_id: str, channel: str, export_payload: Mapping[str, Any]) -> dict[str, Any]:
        sink = self.sinks[channel]
        return sink.deliver(tenant_id=str(tenant_id), payload={"kind": "analytics_export_delivery", **dict(export_payload)})
