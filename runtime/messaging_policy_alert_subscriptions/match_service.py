from __future__ import annotations

from runtime.messaging_policy_alert_subscriptions.matched_subscription import MatchedSubscription
from runtime.messaging_policy_alert_subscriptions.subscription_matcher import subscription_matches


class AlertSubscriptionMatchService:
    def match(self, *, subscriptions, alerts, affected_user_id: str):
        out = []
        for subscription in tuple(subscriptions or ()):
            for alert_item in tuple(alerts or ()):
                if subscription_matches(subscription=subscription, alert_item=alert_item, affected_user_id=str(affected_user_id or "")):
                    out.append(MatchedSubscription(recipient_user_id=subscription.recipient_user_id, channel=subscription.channel, alert_code=str(alert_item.code), alert_level=str(alert_item.level), affected_user_id=str(affected_user_id or "")))
        return tuple(out)
