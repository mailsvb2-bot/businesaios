from __future__ import annotations

from dataclasses import dataclass

from interfaces.web.settings.alert_subscriptions.form_parser import parse_alert_subscriptions_form
from runtime.messaging_policy_alert_subscriptions.settings_key import SETTING_KEY


@dataclass(frozen=True)
class SaveResult:
    setting_key: str
    saved_value: list[dict]


class AlertSubscriptionsService:
    def save(self, payload) -> SaveResult:
        value = parse_alert_subscriptions_form(payload)
        return SaveResult(
            setting_key=SETTING_KEY,
            saved_value=value,
        )
