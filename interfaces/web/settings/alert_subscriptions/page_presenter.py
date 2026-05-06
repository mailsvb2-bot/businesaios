from __future__ import annotations

from dataclasses import dataclass

from runtime.messaging_policy_alert_subscriptions.settings_key import SETTING_KEY
from runtime.messaging_policy_alert_subscriptions.subscription_collection import parse_subscription_list


@dataclass(frozen=True)
class AlertSubscriptionItemViewModel:
    recipient_user_id: str
    channel: str
    min_level: str
    enabled: bool
    code_filters: tuple[str, ...]
    user_scope: tuple[str, ...]


@dataclass(frozen=True)
class OptionViewModel:
    key: str
    label: str


@dataclass(frozen=True)
class AlertSubscriptionsPageModel:
    setting_key: str
    items: tuple[AlertSubscriptionItemViewModel, ...]
    channels: tuple[OptionViewModel, ...]
    levels: tuple[OptionViewModel, ...]


_CHANNELS = (
    OptionViewModel("telegram", "Telegram"),
    OptionViewModel("whatsapp", "WhatsApp"),
    OptionViewModel("sms", "SMS"),
    OptionViewModel("email", "Email"),
)

_LEVELS = (
    OptionViewModel("info", "Info"),
    OptionViewModel("warn", "Warn"),
    OptionViewModel("critical", "Critical"),
)


def _present_item(item) -> AlertSubscriptionItemViewModel:
    return AlertSubscriptionItemViewModel(
        recipient_user_id=item.recipient_user_id,
        channel=item.channel,
        min_level=item.min_level,
        enabled=bool(item.enabled),
        code_filters=tuple(item.code_filters),
        user_scope=tuple(item.user_scope),
    )


def present_page(existing_value, *, tenant_id: str) -> AlertSubscriptionsPageModel:
    items = tuple(
        _present_item(item)
        for item in parse_subscription_list(existing_value, tenant_id=str(tenant_id))
    )
    return AlertSubscriptionsPageModel(
        setting_key=SETTING_KEY,
        items=items,
        channels=_CHANNELS,
        levels=_LEVELS,
    )
