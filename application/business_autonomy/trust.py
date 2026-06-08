from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from collections.abc import Mapping


class BusinessTrustTier(str, Enum):
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class BusinessTrustSnapshot:
    business_id: str
    trust_tier: BusinessTrustTier
    score: float
    reasons: tuple[str, ...] = ()
    metadata: Mapping[str, object] | None = None


@dataclass(frozen=True)
class TrustPolicyDecision:
    allowed: bool
    requires_approval: bool
    reason: str


class BusinessTrustRegistry:
    def __init__(self) -> None:
        self._items: dict[str, BusinessTrustSnapshot] = {}

    def register(self, snapshot: BusinessTrustSnapshot) -> None:
        self._items[snapshot.business_id] = snapshot

    def get(self, business_id: str) -> BusinessTrustSnapshot:
        return self._items.get(
            business_id,
            BusinessTrustSnapshot(
                business_id=business_id,
                trust_tier=BusinessTrustTier.UNKNOWN,
                score=0.0,
                reasons=("No trust profile registered.",),
                metadata={},
            ),
        )
