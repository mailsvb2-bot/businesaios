from __future__ import annotations

from runtime.messaging_policy_alerts.alert_level import LEVEL_CRITICAL, LEVEL_INFO, LEVEL_WARN

_ALLOWED = {LEVEL_INFO, LEVEL_WARN, LEVEL_CRITICAL}


def normalize_min_level(value: str | None) -> str:
    text = str(value or LEVEL_WARN).strip().lower()
    if text not in _ALLOWED:
        return LEVEL_WARN
    return text


def level_rank(value: str) -> int:
    text = normalize_min_level(value)
    if text == LEVEL_INFO:
        return 1
    if text == LEVEL_WARN:
        return 2
    return 3
