from __future__ import annotations

from runtime.messaging_policy_alert_dedup_persistent.settings_prefix import DEDUP_SETTINGS_PREFIX


def build_settings_key(*, dedup_key: str) -> str:
    return f"{DEDUP_SETTINGS_PREFIX}{str(dedup_key)}"
