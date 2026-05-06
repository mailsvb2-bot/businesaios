from __future__ import annotations

from runtime.messaging_policy_alert_dedup_persistent.subscription_service_factory_v2 import build_persistent_alert_subscription_service_v2


def build_persistent_alert_subscription_service(*, alert_service, settings_gateway, tenant_id: str = '', cooldown_s: int = 3600):
    return build_persistent_alert_subscription_service_v2(
        alert_service=alert_service,
        settings_gateway=settings_gateway,
        cooldown_s=int(cooldown_s),
    )
