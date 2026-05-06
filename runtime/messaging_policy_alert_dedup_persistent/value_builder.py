from __future__ import annotations


def build_dedup_value(*, sent_at_epoch_s: int) -> dict:
    return {"sent_at_epoch_s": int(sent_at_epoch_s)}
