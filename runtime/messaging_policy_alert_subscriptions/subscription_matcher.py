from __future__ import annotations

from runtime.messaging_policy_alert_subscriptions.subscription_level import level_rank


def subscription_matches(*, subscription, alert_item, affected_user_id: str) -> bool:
    if not bool(subscription.enabled):
        return False
    if level_rank(alert_item.level) < level_rank(subscription.min_level):
        return False
    if subscription.code_filters and str(alert_item.code or "") not in set(subscription.code_filters):
        return False
    return not (subscription.user_scope and str(affected_user_id or "") not in set(subscription.user_scope))
