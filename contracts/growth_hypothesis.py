from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from contracts.messaging_channels import ALL_CHANNELS

CANON_GROWTH_HYPOTHESIS_CONTRACT = True

FunnelStage = Literal["acquisition", "activation", "retention", "referral", "revenue"]
GROWTH_NON_MESSAGING_CHANNELS = ("organic", "seo", "content", "referral", "partnerships")
GROWTH_MESSAGING_CHANNELS = (*ALL_CHANNELS, "push")
GROWTH_PAID_CHANNELS = ("meta_ads", "google_ads", "tiktok_ads", "vk_ads", "yandex_direct", "other_paid")
GROWTH_PARTNERSHIP_VISIBILITY_NOTE = "partnership_visibility_required"
Channel = Literal[*GROWTH_NON_MESSAGING_CHANNELS, *GROWTH_MESSAGING_CHANNELS, *GROWTH_PAID_CHANNELS]


@dataclass(frozen=True)
class GrowthHypothesisV1:
    schema_version: int = 1
    hypothesis_id: str = ""
    created_ms: int = 0
    tenant_id: str = ""
    stage: FunnelStage = "acquisition"
    channel: Channel = "organic"
    title: str = ""
    mechanism: str = ""
    expected_impact: str = ""
    effort: Literal["low", "medium", "high"] = "medium"
    risk: Literal["low", "medium", "high"] = "medium"
    metric: str = "profit_minor"
    baseline: float | None = None
    target: float | None = None
    horizon_days: int = 14
    action_hints: dict[str, Any] = field(default_factory=dict)


# Legacy public name remains a strict alias; there is still one class definition.
GrowthHypothesis = GrowthHypothesisV1


__all__ = [
    "CANON_GROWTH_HYPOTHESIS_CONTRACT",
    "Channel",
    "FunnelStage",
    "GROWTH_MESSAGING_CHANNELS",
    "GROWTH_NON_MESSAGING_CHANNELS",
    "GROWTH_PAID_CHANNELS",
    "GROWTH_PARTNERSHIP_VISIBILITY_NOTE",
    "GrowthHypothesis",
    "GrowthHypothesisV1",
]
