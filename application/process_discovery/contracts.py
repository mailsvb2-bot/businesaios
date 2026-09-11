from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AutonomyStage(str, Enum):
    OBSERVE = "observe"
    RECOMMEND = "recommend"
    DRAFT = "draft"
    APPROVAL = "approval"
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"


class MoneyStatus(str, Enum):
    VERIFIED = "verified"
    PARTIAL = "partial"
    MIXED_CURRENCY = "mixed_currency"
    UNAVAILABLE = "unavailable"


class EvidenceGrade(str, Enum):
    INSUFFICIENT = "insufficient"
    DIRECTIONAL = "directional"
    MEASURED = "measured"
    CONTROLLED = "controlled"


class ComparisonDesign(str, Enum):
    BEFORE_AFTER = "before_after"
    MATCHED_CONTROL = "matched_control"
    HOLDOUT = "holdout"
    RANDOMIZED = "randomized"


@dataclass(frozen=True)
class ProcessObservation:
    """One canonical process occurrence.

    ``evidence_id`` is mandatory and server-issued. Repeated rows with the same
    evidence id are deduplicated; conflicting rows with one evidence id fail
    closed. Money is minor units only. Revenue-at-risk is never realized loss.
    """

    tenant_id: str
    business_id: str
    process_key: str
    occurred_at: datetime
    source: str
    evidence_id: str
    manual_minutes: int = 0
    actor_cost_per_hour_minor: int | None = None
    direct_loss_minor: int | None = None
    revenue_at_risk_minor: int | None = None
    currency: str | None = None
    automation_fit: float = 0.0
    operational_risk: float = 0.0
    trust_weight: float = 1.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in (
            ("tenant_id", self.tenant_id),
            ("business_id", self.business_id),
            ("process_key", self.process_key),
            ("source", self.source),
            ("evidence_id", self.evidence_id),
        ):
            if not str(value).strip():
                raise ValueError(f"{name} must be non-empty")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        if self.manual_minutes < 0:
            raise ValueError("manual_minutes must be non-negative")
        for name, value in (
            ("actor_cost_per_hour_minor", self.actor_cost_per_hour_minor),
            ("direct_loss_minor", self.direct_loss_minor),
            ("revenue_at_risk_minor", self.revenue_at_risk_minor),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative")
        for name, value in (
            ("automation_fit", self.automation_fit),
            ("operational_risk", self.operational_risk),
            ("trust_weight", self.trust_weight),
        ):
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        has_money = any(
            value is not None
            for value in (self.actor_cost_per_hour_minor, self.direct_loss_minor, self.revenue_at_risk_minor)
        )
        normalized_currency = str(self.currency or "").strip().upper()
        if has_money and not normalized_currency:
            raise ValueError("currency is required when monetary evidence is present")
        object.__setattr__(self, "currency", normalized_currency or None)
        object.__setattr__(self, "evidence_id", str(self.evidence_id).strip())

    @property
    def labor_cost_known(self) -> bool:
        return self.manual_minutes == 0 or self.actor_cost_per_hour_minor is not None

    @property
    def direct_loss_known(self) -> bool:
        return self.direct_loss_minor is not None

    @property
    def realized_money_complete(self) -> bool:
        return self.labor_cost_known and self.direct_loss_known and self.currency is not None

    @property
    def realized_cost_minor(self) -> int | None:
        if not self.realized_money_complete:
            return None
        labor = 0
        if self.manual_minutes:
            assert self.actor_cost_per_hour_minor is not None
            labor = round(self.manual_minutes * self.actor_cost_per_hour_minor / 60)
        assert self.direct_loss_minor is not None
        return labor + self.direct_loss_minor


@dataclass(frozen=True)
class ProcessBaseline:
    tenant_id: str
    business_id: str
    process_key: str
    window_start: datetime
    window_end: datetime
    window_days: int
    observation_count: int
    source_count: int
    occurrences_per_30d: float
    manual_minutes_per_30d: int
    realized_loss_minor_per_30d: int | None
    revenue_at_risk_minor_per_30d: int | None
    currency: str | None
    money_status: MoneyStatus
    average_automation_fit: float
    average_operational_risk: float
    confidence: float
    evidence_refs: Sequence[str] = field(default_factory=tuple)
    evidence_fingerprint: str = ""


@dataclass(frozen=True)
class DiscoveryPolicy:
    min_observations: int = 5
    min_window_days: int = 7
    min_confidence: float = 0.35
    min_manual_minutes_per_30d: int = 60
    min_realized_loss_minor_per_30d: int = 0
    min_automation_fit: float = 0.45
    max_operational_risk: float = 0.85
    reference_observations: int = 20
    reference_window_days: int = 14
    reference_occurrences_per_30d: float = 20.0

    def __post_init__(self) -> None:
        if self.min_observations < 1 or self.min_window_days < 1:
            raise ValueError("minimum evidence thresholds must be positive")
        if self.reference_observations < 1 or self.reference_window_days < 1:
            raise ValueError("reference evidence thresholds must be positive")
        if self.reference_occurrences_per_30d <= 0:
            raise ValueError("reference_occurrences_per_30d must be positive")
        for name, value in (
            ("min_confidence", self.min_confidence),
            ("min_automation_fit", self.min_automation_fit),
            ("max_operational_risk", self.max_operational_risk),
        ):
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True)
class AutomationOpportunity:
    opportunity_id: str
    baseline: ProcessBaseline
    priority_score: float
    reasons: Sequence[str]
    eligible: bool
    blockers: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class DiscoveryReport:
    tenant_id: str
    business_id: str
    opportunities: Sequence[AutomationOpportunity]
    rejected_processes: Sequence[AutomationOpportunity]
    generated_at: datetime


@dataclass(frozen=True)
class BuildRequest:
    owner_goal: str
    requested_capabilities: Sequence[str] = field(default_factory=tuple)
    expected_coverage: float = 0.5
    setup_cost_minor: int | None = None
    currency: str | None = None
    success_metrics: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.owner_goal.strip():
            raise ValueError("owner_goal must be non-empty")
        if not 0.0 <= float(self.expected_coverage) <= 1.0:
            raise ValueError("expected_coverage must be between 0 and 1")
        if self.setup_cost_minor is not None and self.setup_cost_minor < 0:
            raise ValueError("setup_cost_minor must be non-negative")
        normalized_currency = str(self.currency or "").strip().upper()
        if self.setup_cost_minor is not None and not normalized_currency:
            raise ValueError("currency is required when setup_cost_minor is provided")
        object.__setattr__(self, "currency", normalized_currency or None)


@dataclass(frozen=True)
class AgentBlueprint:
    blueprint_id: str
    tenant_id: str
    business_id: str
    process_key: str
    opportunity_id: str
    baseline_fingerprint: str
    built_at: datetime
    owner_goal: str
    initial_stage: AutonomyStage
    promotion_path: Sequence[AutonomyStage]
    requested_capabilities: Sequence[str]
    forbidden_side_effects: Sequence[str]
    expected_coverage: float
    setup_cost_minor: int | None
    currency: str | None
    success_metrics: Sequence[str]
    rollback_conditions: Sequence[str]
    executable: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InterventionProof:
    """Server-ledger proof that the intervention actually started.

    Browser-created identifiers are never sufficient. The adapter is expected
    to rebuild these coordinates from canonical DecisionCore/action/outcome
    ledgers, following the same trust direction as the owner action flow.
    """

    tenant_id: str
    business_id: str
    blueprint_id: str
    intervention_id: str
    started_at: datetime
    server_validated: bool
    execution_verified: bool
    run_id: str | None = None
    decision_id: str | None = None
    action_id: str | None = None
    evidence_refs: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name, value in (
            ("tenant_id", self.tenant_id),
            ("business_id", self.business_id),
            ("blueprint_id", self.blueprint_id),
            ("intervention_id", self.intervention_id),
        ):
            if not str(value).strip():
                raise ValueError(f"{name} must be non-empty")
        if self.started_at.tzinfo is None:
            raise ValueError("started_at must be timezone-aware")


@dataclass(frozen=True)
class ComparisonEvidence:
    design: ComparisonDesign = ComparisonDesign.BEFORE_AFTER
    validated_server_side: bool = False
    control_observation_count: int = 0
    control_window_days: int = 0
    evidence_refs: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.control_observation_count < 0 or self.control_window_days < 0:
            raise ValueError("control evidence counts must be non-negative")


@dataclass(frozen=True)
class InterventionSpend:
    ai_runtime_cost_minor: int | None = None
    human_review_minutes: int = 0
    reviewer_cost_per_hour_minor: int | None = None
    setup_cost_minor: int | None = None
    setup_amortization_days: int = 90
    currency: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("ai_runtime_cost_minor", self.ai_runtime_cost_minor),
            ("reviewer_cost_per_hour_minor", self.reviewer_cost_per_hour_minor),
            ("setup_cost_minor", self.setup_cost_minor),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.human_review_minutes < 0:
            raise ValueError("human_review_minutes must be non-negative")
        if self.setup_amortization_days < 1:
            raise ValueError("setup_amortization_days must be positive")
        normalized_currency = str(self.currency or "").strip().upper()
        has_money = any(
            value is not None
            for value in (self.ai_runtime_cost_minor, self.reviewer_cost_per_hour_minor, self.setup_cost_minor)
        )
        if has_money and not normalized_currency:
            raise ValueError("currency is required when intervention monetary evidence is present")
        object.__setattr__(self, "currency", normalized_currency or None)


@dataclass(frozen=True)
class ROIReport:
    blueprint_id: str
    intervention_id: str
    process_key: str
    design: ComparisonDesign
    evidence_grade: EvidenceGrade
    baseline: ProcessBaseline
    after: ProcessBaseline
    manual_minutes_saved_per_30d: int
    manual_time_improvement_ratio: float | None
    gross_savings_minor_per_30d: int | None
    intervention_cost_minor_per_30d: int | None
    net_benefit_minor_per_30d: int | None
    roi_ratio: float | None
    currency: str | None
    causal_claim_allowed: bool
    caveats: Sequence[str]
    metadata: Mapping[str, Any] = field(default_factory=dict)
