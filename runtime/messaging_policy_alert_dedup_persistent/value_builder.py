from __future__ import annotations


def build_dedup_value(*, sent_at_epoch_s: int, pending_approval_id: str = "") -> dict:
    value = {"sent_at_epoch_s": int(sent_at_epoch_s)}
    approval_id = str(pending_approval_id or "").strip()
    if approval_id:
        value["pending_approval_id"] = approval_id
    return value
