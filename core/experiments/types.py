from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from config.experiments_defaults import DEFAULT_EXPERIMENT_DEFAULTS
from core.experiments.enums import (
    ExperimentStatus,
    MetricDirection,
    RiskLevel,
    RolloutDecision,
    VariantRole,
)


@dataclass(frozen=True)
class MetricDefinition:
    metric_key: str
    direction: MetricDirection
    minimum_detectable_effect: float = DEFAULT_EXPERIMENT_DEFAULTS.metric_minimum_detectable_effect
    guardrail: bool = False


@dataclass(frozen=True)
class VariantSpec:
    variant_id: str
    name: str
    role: VariantRole
    traffic_share: float


@dataclass(frozen=True)
class ExperimentPlan:
    experiment_id: str
    name: str
    hypothesis: str
    subject_key: str
    audience_key: str
    owner: str
    status: ExperimentStatus
    variants: list[VariantSpec]
    metrics: list[MetricDefinition]
    minimum_sample_size: int
    overlap_keys: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentAssignment:
    assignment_id: str
    experiment_id: str
    subject_id: str
    variant_id: str
    assigned_at: str
    correlation_id: str


@dataclass(frozen=True)
class VariantMetricSnapshot:
    variant_id: str
    exposures: int
    conversions: int
    value: float = DEFAULT_EXPERIMENT_DEFAULTS.variant_metric_value


@dataclass(frozen=True)
class ExperimentResult:
    result_id: str
    experiment_id: str
    primary_metric_key: str
    control_variant_id: str
    treatment_variant_id: str
    control: VariantMetricSnapshot
    treatment: VariantMetricSnapshot
    uplift: float
    p_value: float
    significant: bool
    risk_level: RiskLevel
    rollout_decision: RolloutDecision
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvaluationSummary:
    experiment_id: str
    significant: bool
    uplift: float
    p_value: float
    risk_level: RiskLevel
    rollout_decision: RolloutDecision
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExperimentStatusView:
    experiment_id: str
    status: ExperimentStatus
    assignment_count: int
    result_count: int


@dataclass(frozen=True)
class ExperimentResultView:
    experiment_id: str
    primary_metric_key: str
    uplift: float
    p_value: float
    significant: bool
    risk_level: RiskLevel
    rollout_decision: RolloutDecision
    notes: list[str]


# backward-compatible legacy surface
@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    hypothesis: str
    traffic_share: float


ExperimentMap = Mapping[str, ExperimentPlan]
OptionalExperiment = ExperimentPlan | None
