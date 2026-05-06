from __future__ import annotations

from runtime.messaging_policy_alert_dedup.record import AlertNotificationDedupRecord


def parse_dedup_value(*, dedup_key: str, value) -> AlertNotificationDedupRecord | None:
    if not isinstance(value, dict):
        return None

    raw = value.get("sent_at_epoch_s")
    try:
        sent_at = int(raw)
    except Exception:
        return None

    if sent_at <= 0:
        return None

    return AlertNotificationDedupRecord(
        dedup_key=str(dedup_key),
        sent_at_epoch_s=sent_at,
    )
