from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Mapping

CANON_ADVISORY_REVENUE_OS_CONTRACTS = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _required_text(value: Any, *, field_name: str) -> str:
    token = str(value or '').strip()
    if not token:
        raise ValueError(f'{field_name} is required')
    return token


def _utc_datetime(value: datetime, *, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f'{field_name} must be a datetime')
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f'{field_name} must be timezone-aware')
    return value.astimezone(timezone.utc)


def _ratio(value: float, *, minimum: float = 0.0, maximum: float = 1.0) -> float:
    numeric = float(value)
    if numeric < minimum:
        return minimum
    if numeric > maximum:
        return maximum
    return numeric


@dataclass(frozen=True, slots=True)
class PricePoint:
    product_id: str
    currency: str
    amount: float
    billing_period_days: int = 30
    compare_at_amount: float | None = None
    trial_days: int = 0
    source: str = 'catalog'
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def normalized_copy(self) -> 'PricePoint':
        amount = float(self.amount)
        compare_at_amount = None if self.compare_at_amount is None else float(self.compare_at_amount)
        billing_period_days = int(self.billing_period_days)
        trial_days = int(self.trial_days)
        if amount < 0.0:
            raise ValueError('amount must be >= 0')
        if compare_at_amount is not None and compare_at_amount < amount:
            raise ValueError('compare_at_amount must be >= amount')
        if billing_period_days <= 0:
            raise ValueError('billing_period_days must be > 0')
        if trial_days < 0:
            raise ValueError('trial_days must be >= 0')
        return replace(
            self,
            product_id=_required_text(self.product_id, field_name='product_id'),
            currency=_required_text(self.currency, field_name='currency').upper(),
            amount=round(amount, 6),
            compare_at_amount=None if compare_at_amount is None else round(compare_at_amount, 6),
            billing_period_days=billing_period_days,
            trial_days=trial_days,
            source=_required_text(self.source, field_name='source'),
            metadata=dict(self.metadata),
        )


@dataclass(frozen=True, slots=True)
class SubscriptionPlan:
    plan_id: str
    tier: str
    price: PricePoint
    feature_flags: tuple[str, ...] = ()
    seats_included: int = 1
    recommended: bool = False

    def normalized_copy(self) -> 'SubscriptionPlan':
        seats_included = int(self.seats_included)
        if seats_included <= 0:
            raise ValueError('seats_included must be > 0')
        return replace(
            self,
            plan_id=_required_text(self.plan_id, field_name='plan_id'),
            tier=_required_text(self.tier, field_name='tier').lower(),
            price=self.price.normalized_copy(),
            feature_flags=tuple(sorted({_required_text(flag, field_name='feature_flag') for flag in self.feature_flags})),
            seats_included=seats_included,
            recommended=bool(self.recommended),
        )


@dataclass(frozen=True, slots=True)
class PaywallVariant:
    variant_id: str
    headline: str
    theme: str = 'default'
    emphasizes_trial: bool = False
    social_proof_density: float = 0.0
    friction_score: float = 0.5
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def normalized_copy(self) -> 'PaywallVariant':
        return replace(
            self,
            variant_id=_required_text(self.variant_id, field_name='variant_id'),
            headline=_required_text(self.headline, field_name='headline'),
            theme=_required_text(self.theme, field_name='theme').lower(),
            emphasizes_trial=bool(self.emphasizes_trial),
            social_proof_density=round(_ratio(self.social_proof_density), 6),
            friction_score=round(_ratio(self.friction_score), 6),
            metadata=dict(self.metadata),
        )


@dataclass(frozen=True, slots=True)
class RevenueSnapshot:
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

    @property
    def conversion_rate(self) -> float:
        return 0.0 if self.visitors <= 0 else self.conversions / self.visitors

    @property
    def trial_start_rate(self) -> float:
        return 0.0 if self.visitors <= 0 else self.trials_started / self.visitors

    @property
    def trial_to_paid_rate(self) -> float:
        return 0.0 if self.trials_started <= 0 else self.conversions / self.trials_started

    @property
    def churn_rate(self) -> float:
        base = self.retained_subscribers + self.churned_subscribers
        return 0.0 if base <= 0 else self.churned_subscribers / base

    @property
    def refund_rate(self) -> float:
        return 0.0 if self.conversions <= 0 else self.refunds / self.conversions

    @property
    def arpu(self) -> float:
        return 0.0 if self.active_subscribers <= 0 else self.net_revenue / self.active_subscribers

    @property
    def contribution_margin(self) -> float:
        return 0.0 if self.net_revenue <= 0 else max(0.0, (self.net_revenue - self.acquisition_spend) / self.net_revenue)

    def normalized_copy(self) -> 'RevenueSnapshot':
        visitors = int(self.visitors)
        trials_started = int(self.trials_started)
        conversions = int(self.conversions)
        retained_subscribers = int(self.retained_subscribers)
        churned_subscribers = int(self.churned_subscribers)
        refunds = int(self.refunds)
        active_subscribers = int(self.active_subscribers)
        trial_subscribers = int(self.trial_subscribers)
        gross_revenue = round(float(self.gross_revenue), 6)
        net_revenue = round(float(self.net_revenue), 6)
        acquisition_spend = round(float(self.acquisition_spend), 6)
        if visitors < 0 or trials_started < 0 or conversions < 0:
            raise ValueError('traffic counters must be >= 0')
        if retained_subscribers < 0 or churned_subscribers < 0 or refunds < 0:
            raise ValueError('subscriber counters must be >= 0')
        if active_subscribers < 0 or trial_subscribers < 0:
            raise ValueError('subscriber state counters must be >= 0')
        if trials_started > visitors:
            raise ValueError('trials_started cannot exceed visitors')
        if conversions > trials_started:
            raise ValueError('conversions cannot exceed trials_started')
        if refunds > conversions:
            raise ValueError('refunds cannot exceed conversions')
        if gross_revenue < 0.0 or net_revenue < 0.0 or acquisition_spend < 0.0:
            raise ValueError('revenue and spend values must be >= 0')
        if gross_revenue < net_revenue:
            raise ValueError('gross_revenue must be >= net_revenue')
        if active_subscribers < retained_subscribers:
            raise ValueError('active_subscribers must be >= retained_subscribers')
        if trial_subscribers > active_subscribers:
            raise ValueError('trial_subscribers must be <= active_subscribers')
        return replace(
            self,
            observed_at=_utc_datetime(self.observed_at, field_name='observed_at'),
            visitors=visitors,
            trials_started=trials_started,
            conversions=conversions,
            retained_subscribers=retained_subscribers,
            churned_subscribers=churned_subscribers,
            refunds=refunds,
            gross_revenue=gross_revenue,
            net_revenue=net_revenue,
            acquisition_spend=acquisition_spend,
            active_subscribers=active_subscribers,
            trial_subscribers=trial_subscribers,
        )


@dataclass(frozen=True, slots=True)
class RevenueDecisionIntent:
    action_type: str
    intent_kind: str
    confidence: float
    payload: Mapping[str, Any]
    evidence: Mapping[str, Any]
    reason_codes: tuple[str, ...]
    blast_radius: str = 'low'
    requires_approval: bool = False
    owner: str = 'advisory.revenue_os'

    def normalized_copy(self) -> 'RevenueDecisionIntent':
        blast_radius = _required_text(self.blast_radius, field_name='blast_radius').lower()
        if blast_radius not in {'low', 'moderate', 'high'}:
            raise ValueError('blast_radius must be low, moderate, or high')
        owner = _required_text(self.owner, field_name='owner')
        if owner != 'advisory.revenue_os':
            raise ValueError('owner must remain advisory.revenue_os')
        return replace(
            self,
            action_type=_required_text(self.action_type, field_name='action_type'),
            intent_kind=_required_text(self.intent_kind, field_name='intent_kind').lower(),
            confidence=round(_ratio(self.confidence), 6),
            payload=dict(self.payload),
            evidence=dict(self.evidence),
            reason_codes=tuple(sorted({_required_text(item, field_name='reason_code') for item in self.reason_codes})),
            blast_radius=blast_radius,
            requires_approval=bool(self.requires_approval),
            owner='advisory.revenue_os',
        )


@dataclass(frozen=True, slots=True)
class RevenueExperimentArm:
    arm_id: str
    label: str
    allocation: float
    intent: RevenueDecisionIntent

    def normalized_copy(self) -> 'RevenueExperimentArm':
        return replace(
            self,
            arm_id=_required_text(self.arm_id, field_name='arm_id'),
            label=_required_text(self.label, field_name='label'),
            allocation=round(_ratio(self.allocation), 6),
            intent=self.intent.normalized_copy(),
        )


@dataclass(frozen=True, slots=True)
class RevenueExperiment:
    experiment_id: str
    kind: str
    hypothesis: str
    metric_primary: str
    metric_guardrails: tuple[str, ...]
    arms: tuple[RevenueExperimentArm, ...]
    holdout_allocation: float = 0.1
    max_daily_exposure: int = 5_000
    created_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def normalized_copy(self) -> 'RevenueExperiment':
        normalized_arms = tuple(arm.normalized_copy() for arm in self.arms)
        if len(normalized_arms) < 2:
            raise ValueError('experiment requires at least two arms')
        arm_ids = [arm.arm_id for arm in normalized_arms]
        if len(arm_ids) != len(set(arm_ids)):
            raise ValueError('arm ids must be unique')
        total = round(sum(arm.allocation for arm in normalized_arms), 6)
        if total <= 0.0:
            raise ValueError('arm allocations must sum to more than 0')
        holdout_allocation = round(_ratio(self.holdout_allocation, maximum=0.5), 6)
        if round(total + holdout_allocation, 6) > 1.0:
            raise ValueError('sum of arm allocations and holdout cannot exceed 1.0')
        if int(self.max_daily_exposure) <= 0:
            raise ValueError('max_daily_exposure must be > 0')
        return replace(
            self,
            experiment_id=_required_text(self.experiment_id, field_name='experiment_id'),
            kind=_required_text(self.kind, field_name='kind').lower(),
            hypothesis=_required_text(self.hypothesis, field_name='hypothesis'),
            metric_primary=_required_text(self.metric_primary, field_name='metric_primary'),
            metric_guardrails=tuple(sorted({_required_text(item, field_name='metric_guardrail') for item in self.metric_guardrails})),
            arms=normalized_arms,
            holdout_allocation=holdout_allocation,
            max_daily_exposure=int(self.max_daily_exposure),
            created_at=_utc_datetime(self.created_at, field_name='created_at'),
            metadata=dict(self.metadata),
        )


__all__ = [
    'CANON_ADVISORY_REVENUE_OS_CONTRACTS',
    'PaywallVariant',
    'PricePoint',
    'RevenueDecisionIntent',
    'RevenueExperiment',
    'RevenueExperimentArm',
    'RevenueSnapshot',
    'SubscriptionPlan',
    '_ratio',
    '_required_text',
    '_utc_datetime',
    'utc_now',
]
