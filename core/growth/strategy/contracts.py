from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from contracts.messaging_channels import ALL_CHANNELS

FunnelStage = Literal["acquisition", "activation", "retention", "referral", "revenue"]

GROWTH_NON_MESSAGING_CHANNELS = (
    "organic",
    "seo",
    "content",
    "referral",
    "partnerships",
)
GROWTH_MESSAGING_CHANNELS = (*ALL_CHANNELS, "push")
GROWTH_PAID_CHANNELS = (
    "meta_ads",
    "google_ads",
    "tiktok_ads",
    "vk_ads",
    "yandex_direct",
    "other_paid",
)
Channel = Literal[
    *GROWTH_NON_MESSAGING_CHANNELS,
    *GROWTH_MESSAGING_CHANNELS,
    *GROWTH_PAID_CHANNELS,
]


@dataclass(frozen=True)
class GrowthGoalV1:
    schema_version: int = 1
    primary_stage: FunnelStage = "acquisition"
    horizon_days: int = 14
    kpi: str = "profit_minor"
    target_delta_pct: float = 10.0
    constraints: tuple[str, ...] = ()


@dataclass(frozen=True)
class SalesFunnelCountsV1:
    discovered: int = 0
    engaged: int = 0
    qualified: int = 0
    checkout: int = 0
    won: int = 0
    lost: int = 0

    @staticmethod
    def _pct(numerator: int, denominator: int) -> float:
        return 0.0 if denominator <= 0 else round(numerator / denominator * 100.0, 1)

    @property
    def engagement_percent(self) -> float:
        return self._pct(self.engaged, self.discovered)

    @property
    def qualification_percent(self) -> float:
        return self._pct(self.qualified, self.engaged)

    @property
    def checkout_percent(self) -> float:
        return self._pct(self.checkout, self.qualified)

    @property
    def win_percent(self) -> float:
        return self._pct(self.won, self.discovered)


@dataclass(frozen=True)
class SalesFunnelSourceV1:
    source: str = "unknown"
    counts: SalesFunnelCountsV1 = field(default_factory=SalesFunnelCountsV1)


@dataclass(frozen=True)
class SalesFunnelSnapshotV1:
    schema_version: int = 1
    tenant_id: str = ""
    start_ms: int = 0
    end_ms: int = 0
    total: SalesFunnelCountsV1 = field(default_factory=SalesFunnelCountsV1)
    by_source: tuple[SalesFunnelSourceV1, ...] = ()


@dataclass(frozen=True)
class GrowthSignalV1:
    schema_version: int = 1
    ts_ms: int = 0
    tenant_id: str = ""

    leads_today: int = 0
    spend_today_minor: int = 0
    revenue_today_minor: int = 0
    profit_today_minor: int = 0

    retention_d1_pct: float = 0.0
    retention_d7_pct: float = 0.0
    conversion_lead_to_purchase_pct: float = 0.0

    top_channels: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    sales_funnel: SalesFunnelSnapshotV1 = field(default_factory=SalesFunnelSnapshotV1)


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


@dataclass(frozen=True)
class OpportunityScoreV1:
    schema_version: int = 1
    hypothesis_id: str = ""
    score: float = 0.0
    impact: float = 0.0
    confidence: float = 0.0
    ease: float = 0.0
    risk_penalty: float = 0.0
    rationale: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExperimentSpecV1:
    schema_version: int = 1
    experiment_id: str = ""
    tenant_id: str = ""
    created_ms: int = 0
    hypothesis_id: str = ""

    name: str = ""
    stage: FunnelStage = "acquisition"
    channel: Channel = "organic"

    primary_metric: str = "profit_minor"
    guardrail_metrics: tuple[str, ...] = ("spend_minor",)

    steps: tuple[str, ...] = ()
    duration_days: int = 14

    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyPlanV1:
    schema_version: int = 1
    tenant_id: str = ""
    created_ms: int = 0
    goal: GrowthGoalV1 = field(default_factory=GrowthGoalV1)
    signals: GrowthSignalV1 = field(default_factory=GrowthSignalV1)
    top_hypotheses: tuple[GrowthHypothesisV1, ...] = ()
    notes: tuple[str, ...] = ()
