from __future__ import annotations

from dataclasses import dataclass

from runtime.messaging_policy_alert_subscriptions.subscription_channel import normalize_subscription_channel
from runtime.messaging_policy_alert_subscriptions.subscription_level import normalize_min_level
from runtime.tenancy import normalize_tenant_id


@dataclass(frozen=True)
class AlertSubscriptionRecord:
    tenant_id: str
    recipient_user_id: str
    channel: str
    min_level: str
    enabled: bool = True
    code_filters: tuple[str, ...] = ()
    user_scope: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", normalize_tenant_id(self.tenant_id, fallback="unknown_tenant"))
        object.__setattr__(self, "recipient_user_id", str(self.recipient_user_id or ""))
        object.__setattr__(self, "channel", normalize_subscription_channel(self.channel))
        object.__setattr__(self, "min_level", normalize_min_level(self.min_level))
        object.__setattr__(self, "enabled", bool(self.enabled))
        object.__setattr__(self, "code_filters", tuple(dict.fromkeys(str(x).strip() for x in self.code_filters if str(x).strip())))
        object.__setattr__(self, "user_scope", tuple(dict.fromkeys(str(x).strip() for x in self.user_scope if str(x).strip())))
