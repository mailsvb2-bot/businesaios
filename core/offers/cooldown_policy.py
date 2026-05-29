from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CooldownDecision:
    allowed: bool
    reason: str
    last_shown_ms: int | None = None


def allow_offer_by_cooldown(
    *,
    now_ms: int,
    last_shown_ms: int | None,
    cooldown_days: int,
) -> CooldownDecision:
    if int(cooldown_days) <= 0:
        return CooldownDecision(allowed=True, reason="no_cooldown", last_shown_ms=last_shown_ms)
    if last_shown_ms is None:
        return CooldownDecision(allowed=True, reason="never_shown", last_shown_ms=None)
    cooldown_ms = int(cooldown_days) * 24 * 60 * 60 * 1000
    if (int(now_ms) - int(last_shown_ms)) >= cooldown_ms:
        return CooldownDecision(allowed=True, reason="cooldown_passed", last_shown_ms=int(last_shown_ms))
    return CooldownDecision(allowed=False, reason="cooldown_active", last_shown_ms=int(last_shown_ms))
