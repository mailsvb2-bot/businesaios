from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional, Tuple


FunnelStage = Literal["acquisition", "activation", "retention", "referral", "revenue"]
Channel = Literal[
    "organic",
    "seo",
    "content",
    "referral",
    "partnerships",
    "email",
    "sms",
    "push",
    "telegram",
    "meta_ads",
    "google_ads",
    "tiktok_ads",
    "vk_ads",
    "yandex_direct",
    "other_paid",
]


@dataclass(frozen=True)
class GrowthGoalV1:
    schema_version: int = 1
    primary_stage: FunnelStage = "acquisition"
    horizon_days: int = 14
    kpi: str = "profit_minor"
    target_delta_pct: float = 10.0
    constraints: Tuple[str, ...] = ()


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

    top_channels: Tuple[str, ...] = ()
    notes: Tuple[str, ...] = ()


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
    baseline: Optional[float] = None
    target: Optional[float] = None
    horizon_days: int = 14

    action_hints: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OpportunityScoreV1:
    schema_version: int = 1
    hypothesis_id: str = ""
    score: float = 0.0
    impact: float = 0.0
    confidence: float = 0.0
    ease: float = 0.0
    risk_penalty: float = 0.0
    rationale: Tuple[str, ...] = ()


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
    guardrail_metrics: Tuple[str, ...] = ("spend_minor",)

    steps: Tuple[str, ...] = ()
    duration_days: int = 14

    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyPlanV1:
    schema_version: int = 1
    tenant_id: str = ""
    created_ms: int = 0
    goal: GrowthGoalV1 = field(default_factory=GrowthGoalV1)
    signals: GrowthSignalV1 = field(default_factory=GrowthSignalV1)
    top_hypotheses: Tuple[GrowthHypothesisV1, ...] = ()
    notes: Tuple[str, ...] = ()
