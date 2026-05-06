from __future__ import annotations

from runtime.messaging_policy_alert_dedup_persistent.boot_tenant_aware import build_tenant_aware_persistent_deduping_alert_notifier


def build_persistent_deduping_alert_notifier(*, settings_gateway, tenant_id: str = '', cooldown_s: int = 3600):
    return build_tenant_aware_persistent_deduping_alert_notifier(
        settings_gateway=settings_gateway,
        cooldown_s=int(cooldown_s),
    )
