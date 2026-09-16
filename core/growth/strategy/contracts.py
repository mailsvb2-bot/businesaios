from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from contracts.growth_hypothesis import (
    GROWTH_MESSAGING_CHANNELS as GROWTH_MESSAGING_CHANNELS,
)
from contracts.growth_hypothesis import (
    GROWTH_NON_MESSAGING_CHANNELS as GROWTH_NON_MESSAGING_CHANNELS,
)
from contracts.growth_hypothesis import (
    GROWTH_PAID_CHANNELS as GROWTH_PAID_CHANNELS,
)
from contracts.growth_hypothesis import (
    GROWTH_PARTNERSHIP_VISIBILITY_NOTE as GROWTH_PARTNERSHIP_VISIBILITY_NOTE,
)
from contracts.growth_hypothesis import (
    Channel as Channel,
)
from contracts.growth_hypothesis import (
    FunnelStage as FunnelStage,
)
from contracts.growth_hypothesis import (
    GrowthHypothesisV1 as GrowthHypothesisV1,
)


@dataclass(frozen=True)
class GrowthGoalV1:
    schema_version: int = 1
    primary_stage: FunnelStage = "acquisition"
    horizon_days: int = 14
    kpi: str = "profit_minor"
    target_delta_pct: float = 10.0
    constraints: tuple[str, ...] = ()


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
    sales_funnel: dict[str, Any] = field(default_factory=dict)



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
