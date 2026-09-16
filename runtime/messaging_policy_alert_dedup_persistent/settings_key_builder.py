from __future__ import annotations

DEDUP_SETTINGS_PREFIX = "messaging_policy:alert_dedup:"


def build_settings_key(*, dedup_key: str) -> str:
    return f"{DEDUP_SETTINGS_PREFIX}{str(dedup_key)}"


def build_approval_index_key(*, approval_id: str) -> str:
    return f"{DEDUP_SETTINGS_PREFIX}__approval__:{str(approval_id)}"
