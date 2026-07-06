from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from advisory.revenue_os import PaywallVariant, PricePoint, RevenueOSFacade, RevenueSnapshot, SubscriptionPlan
from runtime.monetization.contracts import utc_now
from runtime.monetization.revenue_advisory_contracts import (
    RevenueActionMappingSurface,
    RevenueCandidateAction,
    RevenueDecisionEnvelope,
    RevenueExperimentSurface,
    RevenuePaywallVariantInput,
    RevenuePlanInput,
    RevenueSnapshotInput,
)

CANON_RUNTIME_MONETIZATION_REVENUE_ADVISORY = True


@dataclass(frozen=True, slots=True)
class RevenueAdvisorySummary:
    tenant_id: str
    product_id: str
    generated_at: str
    projected_ltv: float
    projected_churn_rate: float
    recommended_price_plan_id: str | None
    recommended_price_amount: float | None
    recommended_paywall_variant_id: str | None
    recommended_subscription_plan_id: str | None
    highest_blast_radius: str
    approval_required_count: int
    experiments_count: int
    action_mappings_count: int
    flags: Mapping[str, bool]


@dataclass(frozen=True, slots=True)
class RevenueAdvisoryPresenter:
    def build(self, summary: RevenueAdvisorySummary) -> dict[str, Any]:
        return {
            'tenant_id': summary.tenant_id,
            'product_id': summary.product_id,
            'generated_at': summary.generated_at,
            'projected_ltv': float(summary.projected_ltv),
            'projected_churn_rate': float(summary.projected_churn_rate),
            'recommended_price_plan_id': summary.recommended_price_plan_id,
            'recommended_price_amount': None if summary.recommended_price_amount is None else float(summary.recommended_price_amount),
            'recommended_paywall_variant_id': summary.recommended_paywall_variant_id,
            'recommended_subscription_plan_id': summary.recommended_subscription_plan_id,
            'highest_blast_radius': summary.highest_blast_radius,
            'approval_required_count': int(summary.approval_required_count),
            'experiments_count': int(summary.experiments_count),
            'action_mappings_count': int(summary.action_mappings_count),
            'flags': {str(key): bool(value) for key, value in dict(summary.flags).items()},
        }


class RevenueAdvisoryService:
    """Canonical runtime owner for advisory revenue read models and evidence.

    The advisory engine remains advisory-only. Runtime surfaces translate from a
    canonical runtime contract into advisory internals and then back into thin
    runtime payloads so web, billing, and execution layers do not bind to
    advisory contract types directly.
    """

    def __init__(self, *, facade: RevenueOSFacade | None = None, presenter: RevenueAdvisoryPresenter | None = None) -> None:
        self._facade = facade or RevenueOSFacade()
        self._presenter = presenter or RevenueAdvisoryPresenter()

    def analyze(
        self,
        *,
        tenant_id: str,
        product_id: str,
        snapshots: Sequence[RevenueSnapshotInput],
        plans: Sequence[RevenuePlanInput],
        paywall_variants: Sequence[RevenuePaywallVariantInput],
        target_cac: float | None = None,
    ) -> RevenueAdvisorySummary:
        report = self._analyze_report(
            tenant_id=tenant_id,
            product_id=product_id,
            snapshots=snapshots,
            plans=plans,
            paywall_variants=paywall_variants,
            target_cac=target_cac,
        )
        pricing_intent = next((item for item in report.intents if item.action_type == 'revenue.pricing.recommendation'), None)
        paywall_intent = next((item for item in report.intents if item.action_type == 'revenue.paywall.recommendation'), None)
        subscription_intent = next((item for item in report.intents if item.action_type == 'revenue.subscription.recommendation'), None)
        return RevenueAdvisorySummary(
            tenant_id=str(report.summary['tenant_id']),
            product_id=str(report.summary['product_id']),
            generated_at=utc_now().isoformat(),
            projected_ltv=float(report.ltv.predicted_ltv),
            projected_churn_rate=float(report.churn.churn_rate),
            recommended_price_plan_id=self._normalize_optional_text(None if pricing_intent is None else pricing_intent.payload.get('plan_id')),
            recommended_price_amount=None if pricing_intent is None else self._normalize_optional_float(pricing_intent.payload.get('suggested_amount')),
            recommended_paywall_variant_id=self._normalize_optional_text(None if paywall_intent is None else paywall_intent.payload.get('variant_id')),
            recommended_subscription_plan_id=self._normalize_optional_text(None if subscription_intent is None else subscription_intent.payload.get('primary_plan_id')),
            highest_blast_radius=str(report.approval.highest_blast_radius),
            approval_required_count=int(report.approval.approval_required_count),
            experiments_count=len(report.experiments),
            action_mappings_count=len(report.action_mappings),
            flags={str(key): bool(value) for key, value in dict(report.summary.get('flags', {})).items()},
        )

    def build_payload(self, summary: RevenueAdvisorySummary) -> dict[str, Any]:
        return self._presenter.build(summary)

    def build_envelope(
        self,
        *,
        tenant_id: str,
        product_id: str,
        snapshots: Sequence[RevenueSnapshotInput],
        plans: Sequence[RevenuePlanInput],
        paywall_variants: Sequence[RevenuePaywallVariantInput],
        target_cac: float | None = None,
    ) -> RevenueDecisionEnvelope:
        report = self._analyze_report(
            tenant_id=tenant_id,
            product_id=product_id,
            snapshots=snapshots,
            plans=plans,
            paywall_variants=paywall_variants,
            target_cac=target_cac,
        )
        candidate_actions = tuple(
            RevenueCandidateAction(
                action_type=item.action_type,
                kind=item.intent_kind,
                confidence=float(item.confidence),
                payload=dict(item.payload),
                evidence=dict(item.evidence),
                reason_codes=tuple(str(code) for code in item.reason_codes),
                blast_radius=item.blast_radius,
                requires_approval=bool(item.requires_approval),
                owner=item.owner,
            )
            for item in report.intents
        )
        experiments = tuple(
            RevenueExperimentSurface(
                experiment_id=item.experiment_id,
                kind=item.kind,
                hypothesis=item.hypothesis,
                metric_primary=item.metric_primary,
                metric_guardrails=tuple(item.metric_guardrails),
                arms=tuple(
                    {
                        'arm_id': arm.arm_id,
                        'label': arm.label,
                        'allocation': arm.allocation,
                        'intent': {
                            'action_type': arm.intent.action_type,
                            'intent_kind': arm.intent.intent_kind,
                            'confidence': arm.intent.confidence,
                            'payload': dict(arm.intent.payload),
                            'evidence': dict(arm.intent.evidence),
                            'reason_codes': list(arm.intent.reason_codes),
                            'blast_radius': arm.intent.blast_radius,
                            'requires_approval': arm.intent.requires_approval,
                            'owner': arm.intent.owner,
                        },
                    }
                    for arm in item.arms
                ),
                holdout_allocation=float(item.holdout_allocation),
                max_daily_exposure=int(item.max_daily_exposure),
                created_at=item.created_at.isoformat(),
                metadata=dict(item.metadata),
            )
            for item in report.experiments
        )
        action_mappings = tuple(
            RevenueActionMappingSurface(
                catalog_action=item.catalog_action,
                mode=item.mode,
                payload=dict(item.payload),
                confidence=float(item.confidence),
                owner=item.owner,
            )
            for item in report.action_mappings
        )
        explain = {
            'summary': dict(report.summary),
            'ltv': report.ltv.to_dict(),
            'churn': report.churn.to_dict(),
            'approval': report.approval.to_dict(),
            'owner': 'runtime.monetization.revenue_advisory',
            'mode': 'advisory_only',
        }
        return RevenueDecisionEnvelope(
            world_state_patch={
                'economy': {
                    'revenue_world_state': report.world_state.to_dict(),
                    'predicted_ltv': report.ltv.predicted_ltv,
                    'projected_churn': report.churn.churn_rate,
                    'approval_required_count': report.approval.approval_required_count,
                }
            },
            candidate_actions=candidate_actions,
            experiments=experiments,
            action_mappings=action_mappings,
            audit_records=tuple(dict(item) for item in report.audit_records),
            explain=explain,
        )

    def _analyze_report(
        self,
        *,
        tenant_id: str,
        product_id: str,
        snapshots: Sequence[RevenueSnapshotInput],
        plans: Sequence[RevenuePlanInput],
        paywall_variants: Sequence[RevenuePaywallVariantInput],
        target_cac: float | None = None,
    ):
        return self._facade.analyze(
            tenant_id=tenant_id,
            product_id=product_id,
            snapshots=tuple(self._to_advisory_snapshot(item) for item in snapshots),
            plans=tuple(self._to_advisory_plan(item) for item in plans),
            paywall_variants=tuple(self._to_advisory_paywall_variant(item) for item in paywall_variants),
            target_cac=target_cac,
        )

    def _to_advisory_plan(self, plan: RevenuePlanInput) -> SubscriptionPlan:
        return SubscriptionPlan(
            plan_id=plan.plan_id,
            tier=plan.tier,
            price=PricePoint(
                product_id=plan.price.product_id,
                currency=plan.price.currency,
                amount=float(plan.price.amount),
                billing_period_days=max(1, int(plan.price.billing_period_days)),
                trial_days=max(0, int(plan.price.trial_days)),
                source=plan.price.source,
                metadata=dict(plan.price.metadata),
            ),
            feature_flags=tuple(sorted(str(flag) for flag in plan.feature_flags)),
            seats_included=max(0, int(plan.seats_included)),
            recommended=bool(plan.recommended),
        )

    def _to_advisory_paywall_variant(self, variant: RevenuePaywallVariantInput) -> PaywallVariant:
        return PaywallVariant(
            variant_id=variant.variant_id,
            headline=variant.headline,
            theme=variant.theme,
            emphasizes_trial=bool(variant.emphasizes_trial),
            social_proof_density=float(variant.social_proof_density),
            friction_score=float(variant.friction_score),
            metadata=dict(variant.metadata),
        )

    def _to_advisory_snapshot(self, snapshot: RevenueSnapshotInput) -> RevenueSnapshot:
        normalized = snapshot.normalized_copy()
        return RevenueSnapshot(
            observed_at=normalized.observed_at,
            visitors=normalized.visitors,
            trials_started=normalized.trials_started,
            conversions=normalized.conversions,
            retained_subscribers=normalized.retained_subscribers,
            churned_subscribers=normalized.churned_subscribers,
            refunds=normalized.refunds,
            gross_revenue=normalized.gross_revenue,
            net_revenue=normalized.net_revenue,
            acquisition_spend=normalized.acquisition_spend,
            active_subscribers=normalized.active_subscribers,
            trial_subscribers=normalized.trial_subscribers,
        )

    def _normalize_optional_float(self, value: object) -> float | None:
        if value in (None, ''):
            return None
        return float(value)

    def _normalize_optional_text(self, value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


__all__ = [
    'CANON_RUNTIME_MONETIZATION_REVENUE_ADVISORY',
    'RevenueAdvisoryPresenter',
    'RevenueAdvisoryService',
    'RevenueAdvisorySummary',
]
