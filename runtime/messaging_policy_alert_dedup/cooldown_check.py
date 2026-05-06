from __future__ import annotations


def is_in_cooldown(*, last_sent_epoch_s: int, now_epoch_s: int, cooldown_s: int) -> bool:
    return int(now_epoch_s) - int(last_sent_epoch_s) < int(cooldown_s)
