from __future__ import annotations

from runtime.messaging_policy_alerts.detector import MessagingPolicyAlertDetector
from runtime.tenancy import normalize_tenant_scope


class MessagingPolicyAlertService:
    def __init__(self, *, dashboard_service, detector: MessagingPolicyAlertDetector | None = None):
        self._dashboard_service = dashboard_service
        self._detector = detector or MessagingPolicyAlertDetector()

    def build(self, *, tenant_id: str, user_id: str = "", date_from: str = "", date_to: str = "", limit: int = 500):
        tenant_scope = normalize_tenant_scope(tenant_id, allow_unknown=True)
        dashboard = self._dashboard_service.build(
            tenant_id=tenant_scope,
            user_id=str(user_id or ""),
            date_from=str(date_from or ""),
            date_to=str(date_to or ""),
            limit=int(limit),
        )
        return self._detector.detect(dashboard)
