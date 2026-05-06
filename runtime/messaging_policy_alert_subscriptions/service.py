from __future__ import annotations

from runtime.tenancy import normalize_tenant_scope
from runtime.messaging_policy_alert_subscriptions.match_service import AlertSubscriptionMatchService
from runtime.messaging_policy_alert_subscriptions.notification_planner import AlertNotificationPlanner
from runtime.messaging_policy_alert_subscriptions.notifier import MessagingPolicyAlertNotifier
from runtime.messaging_policy_alert_subscriptions.subscription_loader import load_alert_subscriptions


class MessagingPolicyAlertSubscriptionService:
    def __init__(self, *, alert_service, planner: AlertNotificationPlanner | None = None, match_service: AlertSubscriptionMatchService | None = None, notifier: MessagingPolicyAlertNotifier | None = None):
        self._alert_service = alert_service
        self._planner = planner or AlertNotificationPlanner()
        self._match_service = match_service or AlertSubscriptionMatchService()
        self._notifier = notifier or MessagingPolicyAlertNotifier()

    def run(self, *, settings_gateway, effects, tenant_id: str, affected_user_id: str = "", date_from: str = "", date_to: str = "", limit: int = 500, decision_id: str, correlation_id: str):
        tenant_scope = normalize_tenant_scope(tenant_id, allow_unknown=True)
        alert_result = self._alert_service.build(tenant_id=tenant_scope, user_id=str(affected_user_id or ""), date_from=str(date_from or ""), date_to=str(date_to or ""), limit=int(limit))
        subscriptions = load_alert_subscriptions(settings_gateway=settings_gateway, tenant_id=tenant_scope)
        plan = self._planner.build_plan(tenant_id=tenant_scope, affected_user_id=str(affected_user_id or ""), alerts=alert_result.alerts, subscriptions=subscriptions, date_from=str(date_from or ""), date_to=str(date_to or ""), match_service=self._match_service)
        notify_result = self._notifier.notify(plan=plan, effects=effects, decision_id=str(decision_id), correlation_id=str(correlation_id))
        out = {"alerts_count": len(alert_result.alerts), "subscriptions_count": len(subscriptions), "notifications_total": int(getattr(notify_result, "notifications_total", 0)), "notifications_sent": int(getattr(notify_result, "notifications_sent", 0))}
        if hasattr(notify_result, "notifications_suppressed"):
            out["notifications_suppressed"] = int(getattr(notify_result, "notifications_suppressed", 0))
        return out
