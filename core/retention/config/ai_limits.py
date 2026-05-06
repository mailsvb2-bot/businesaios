from __future__ import annotations

"""Hard AI limits.

This is the thin compatibility layer over canonical retention pricing config.
AI may choose only from predefined offer arms and discount values.
"""

from dataclasses import dataclass
from typing import Final, Tuple

from core.retention.config.pricing_ladder import ALLOWED_DISCOUNTS_PCT


@dataclass(frozen=True)
class AiLimits:
    allowed_arms: Tuple[str, ...]
    allowed_discounts_pct: Tuple[int, ...]


LIMITS: Final[AiLimits] = AiLimits(
    allowed_arms=("offer_30_14900", "offer_90_21900", "offer_bundle_14_30"),
    allowed_discounts_pct=tuple(int(v) for v in ALLOWED_DISCOUNTS_PCT),
)


def is_allowed_arm(offer_arm: str) -> bool:
    return str(offer_arm or "").strip() in set(LIMITS.allowed_arms)


def is_allowed_discount_pct(discount_pct: int | str | None) -> bool:
    try:
        value = int(discount_pct)  # type: ignore[arg-type]
    except Exception:
        return False
    return value in set(LIMITS.allowed_discounts_pct)
