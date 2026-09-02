from __future__ import annotations

from runtime.messaging_policy_alert_dedup.record import AlertNotificationDedupRecord


def parse_dedup_value(*, dedup_key: str, value) -> AlertNotificationDedupRecord | None:
    if not isinstance(value, dict):
        return None
    try:
        sent_at = int(value.get("sent_at_epoch_s") or 0)
    except Exception:
        return None
    pending_approval_id = str(value.get("pending_approval_id") or "").strip()
    if sent_at <= 0 and not pending_approval_id:
        return None
    return AlertNotificationDedupRecord(dedup_key=str(dedup_key), sent_at_epoch_s=sent_at, pending_approval_id=pending_approval_id)
