from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any, Mapping

CANON_RUNTIME_MONETIZATION_REVENUE_ADVISORY_CONTRACTS = True


def ensure_utc_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class RevenuePricePointInput:
    product_id: str
    currency: str
    amount: float
    billing_period_days: int = 30
    trial_days: int = 0
    source: str = 'runtime.monetization'
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RevenuePlanInput:
    plan_id: str
    tier: str
    price: RevenuePricePointInput
    feature_flags: tuple[str, ...] = ()
    seats_included: int = 1
    recommended: bool = False


@dataclass(frozen=True, slots=True)
class RevenuePaywallVariantInput:
    variant_id: str
    headline: str
    theme: str = 'default'
    emphasizes_trial: bool = False
    social_proof_density: float = 0.5
    friction_score: float = 0.5
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RevenueSnapshotInput:
    observed_at: datetime
    visitors: int
    trials_started: int
    conversions: int
    retained_subscribers: int
    churned_subscribers: int
    refunds: int
    gross_revenue: float
    net_revenue: float
    acquisition_spend: float
    active_subscribers: int
    trial_subscribers: int = 0

    def normalized_copy(self) -> RevenueSnapshotInput:
        return RevenueSnapshotInput(
            observed_at=ensure_utc_timestamp(self.observed_at),
            visitors=max(0, int(self.visitors)),
            trials_started=max(0, int(self.trials_started)),
            conversions=max(0, int(self.conversions)),
            retained_subscribers=max(0, int(self.retained_subscribers)),
            churned_subscribers=max(0, int(self.churned_subscribers)),
            refunds=max(0, int(self.refunds)),
            gross_revenue=float(self.gross_revenue),
            net_revenue=float(self.net_revenue),
            acquisition_spend=float(self.acquisition_spend),
            active_subscribers=max(0, int(self.active_subscribers)),
            trial_subscribers=max(0, int(self.trial_subscribers)),
        )


@dataclass(frozen=True, slots=True)
class RevenueCandidateAction:
    action_type: str
    kind: str
    confidence: float
    payload: Mapping[str, Any] = field(default_factory=dict)
    evidence: Mapping[str, Any] = field(default_factory=dict)
    reason_codes: tuple[str, ...] = ()
    blast_radius: str = 'low'
    requires_approval: bool = False
    owner: str = 'advisory.revenue_os'


@dataclass(frozen=True, slots=True)
class RevenueExperimentSurface:
    experiment_id: str
    kind: str
    hypothesis: str
    metric_primary: str
    metric_guardrails: tuple[str, ...] = ()
    arms: tuple[Mapping[str, Any], ...] = ()
    holdout_allocation: float = 0.0
    max_daily_exposure: int = 0
    created_at: str = ''
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RevenueActionMappingSurface:
    catalog_action: str
    mode: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    owner: str = 'advisory.revenue_os'


@dataclass(frozen=True, slots=True)
class RevenueDecisionEnvelope:
    world_state_patch: Mapping[str, Any] = field(default_factory=dict)
    candidate_actions: tuple[RevenueCandidateAction, ...] = ()
    experiments: tuple[RevenueExperimentSurface, ...] = ()
    action_mappings: tuple[RevenueActionMappingSurface, ...] = ()
    audit_records: tuple[Mapping[str, Any], ...] = ()
    explain: Mapping[str, Any] = field(default_factory=dict)


__all__ = [
    'CANON_RUNTIME_MONETIZATION_REVENUE_ADVISORY_CONTRACTS',
    'RevenueActionMappingSurface',
    'RevenueCandidateAction',
    'RevenueDecisionEnvelope',
    'RevenueExperimentSurface',
    'RevenuePaywallVariantInput',
    'RevenuePlanInput',
    'RevenuePricePointInput',
    'RevenueSnapshotInput',
    'ensure_utc_timestamp',
]
