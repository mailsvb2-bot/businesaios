from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from typing import Iterable, Sequence

from advisory.revenue_os.action_mapper import RevenueActionMapper, RevenueActionMapping
from advisory.revenue_os.approval_policy import ApprovalSummary, RevenueApprovalPolicy
from advisory.revenue_os.audit_events import RevenueAuditEvent
from advisory.revenue_os.churn_model import ChurnModel, ChurnProjection
from advisory.revenue_os.contracts import (
    PaywallVariant,
    RevenueDecisionIntent,
    RevenueExperiment,
    RevenueSnapshot,
    SubscriptionPlan,
    _required_text,
)
from advisory.revenue_os.experiment_engine import RevenueExperimentEngine
from advisory.revenue_os.experiment_registry import ExperimentRegistry, InMemoryExperimentRegistry
from advisory.revenue_os.feature_flags import RevenueFeatureFlags
from advisory.revenue_os.ltv_model import LTVModel, LTVProjection
from advisory.revenue_os.observability_export import RevenueObservabilityExporter
from advisory.revenue_os.paywall_optimizer import PaywallOptimizer
from advisory.revenue_os.pricing_engine import RevenuePricingEngine
from advisory.revenue_os.subscription_engine import SubscriptionEngine
from advisory.revenue_os.tenant_policy import TenantRevenuePolicyStore
from advisory.revenue_os.world_state import RevenueWorldState, RevenueWorldStateBuilder

CANON_ADVISORY_REVENUE_OS_FACADE = True


@dataclass(frozen=True, slots=True)
class RevenueOSReport:
    world_state: RevenueWorldState
    ltv: LTVProjection
    churn: ChurnProjection
    intents: tuple[RevenueDecisionIntent, ...]
    experiments: tuple[RevenueExperiment, ...]
    approval: ApprovalSummary
    action_mappings: tuple[RevenueActionMapping, ...]
    audit_records: tuple[dict[str, object], ...]
    summary: dict[str, object]


class RevenueOSFacade:
    def __init__(
        self,
        *,
        world_state_builder: RevenueWorldStateBuilder | None = None,
        churn_model: ChurnModel | None = None,
        ltv_model: LTVModel | None = None,
        pricing_engine: RevenuePricingEngine | None = None,
        paywall_optimizer: PaywallOptimizer | None = None,
        subscription_engine: SubscriptionEngine | None = None,
        experiment_engine: RevenueExperimentEngine | None = None,
        approval_policy: RevenueApprovalPolicy | None = None,
        action_mapper: RevenueActionMapper | None = None,
        policy_store: TenantRevenuePolicyStore | None = None,
        exporter: RevenueObservabilityExporter | None = None,
        experiment_registry: ExperimentRegistry | None = None,
    ) -> None:
        self._world_state_builder = world_state_builder or RevenueWorldStateBuilder()
        self._churn_model = churn_model or ChurnModel()
        self._ltv_model = ltv_model or LTVModel()
        self._pricing_engine = pricing_engine or RevenuePricingEngine()
        self._paywall_optimizer = paywall_optimizer or PaywallOptimizer()
        self._subscription_engine = subscription_engine or SubscriptionEngine()
        self._experiment_engine = experiment_engine or RevenueExperimentEngine()
        self._approval_policy = approval_policy or RevenueApprovalPolicy()
        self._action_mapper = action_mapper or RevenueActionMapper()
        self._policy_store = policy_store or TenantRevenuePolicyStore()
        self._exporter = exporter or RevenueObservabilityExporter()
        self._experiment_registry = experiment_registry or InMemoryExperimentRegistry()

    def analyze(
        self,
        *,
        tenant_id: str,
        product_id: str,
        snapshots: Iterable[RevenueSnapshot],
        plans: Sequence[SubscriptionPlan],
        paywall_variants: Sequence[PaywallVariant],
        target_cac: float | None = None,
    ) -> RevenueOSReport:
        normalized_tenant_id = _required_text(tenant_id, field_name='tenant_id')
        normalized_product_id = _required_text(product_id, field_name='product_id')
        normalized_snapshots = tuple(item.normalized_copy() for item in snapshots)
        normalized_plans = tuple(item.normalized_copy() for item in plans)
        normalized_paywall_variants = tuple(item.normalized_copy() for item in paywall_variants)
        if not normalized_snapshots:
            raise ValueError('at least one revenue snapshot is required')
        policy = self._policy_store.get(normalized_tenant_id)
        flags = RevenueFeatureFlags.from_policy(
            pricing=policy.pricing_enabled,
            paywall=policy.paywall_enabled,
            subscriptions=policy.subscriptions_enabled,
            experiments=policy.experiments_enabled,
        )
        world_state = self._world_state_builder.build(
            tenant_id=normalized_tenant_id,
            product_id=normalized_product_id,
            snapshots=normalized_snapshots,
        )
        churn = self._churn_model.project(normalized_snapshots)
        ltv = self._ltv_model.project(normalized_snapshots, target_cac=target_cac)
        latest_snapshot = normalized_snapshots[-1]

        intents: list[RevenueDecisionIntent] = []
        if flags.pricing and normalized_plans:
            pricing_recommendations = [
                self._pricing_engine.recommend(
                    plan=plan,
                    latest_snapshot=latest_snapshot,
                    ltv=ltv,
                    churn=churn,
                )
                for plan in normalized_plans
            ]
            pricing_recommendations.sort(key=lambda item: (-item.confidence, abs(item.change_pct), item.plan_id))
            intents.append(pricing_recommendations[0].to_intent().normalized_copy())
        if flags.paywalls and normalized_paywall_variants:
            intents.append(
                self._paywall_optimizer.recommend(normalized_paywall_variants, churn=churn).to_intent().normalized_copy()
            )
        if flags.subscriptions and normalized_plans:
            intents.append(self._subscription_engine.recommend(normalized_plans, churn=churn).to_intent().normalized_copy())

        experiments: list[RevenueExperiment] = []
        if flags.experiments:
            max_daily_exposure_override = policy.max_daily_exposure_override
            for recommendation in self._experiment_engine.build(
                tenant_id=normalized_tenant_id,
                product_id=normalized_product_id,
                intents=intents,
            ):
                experiment = recommendation.experiment
                if max_daily_exposure_override is not None:
                    experiment = RevenueExperiment(
                        experiment_id=experiment.experiment_id,
                        kind=experiment.kind,
                        hypothesis=experiment.hypothesis,
                        metric_primary=experiment.metric_primary,
                        metric_guardrails=experiment.metric_guardrails,
                        arms=experiment.arms,
                        holdout_allocation=experiment.holdout_allocation,
                        max_daily_exposure=max_daily_exposure_override,
                        created_at=experiment.created_at,
                        metadata=experiment.metadata,
                    )
                registered = self._experiment_registry.put_if_absent(
                    dedup_key=recommendation.dedup_key,
                    experiment=experiment,
                )
                experiments.append(registered.experiment)

        approval = self._approval_policy.summarize(intents)
        action_mappings = self._action_mapper.map_intents(intents)
        audit_events = (
            RevenueAuditEvent(
                event_type='revenue_os.analysis_completed',
                observed_at=normalized_snapshots[-1].observed_at.astimezone(timezone.utc),
                tenant_id=normalized_tenant_id,
                product_id=normalized_product_id,
                payload={
                    'intents_count': len(intents),
                    'experiments_count': len(experiments),
                    'approval_required_count': approval.approval_required_count,
                },
            ),
        )
        audit_records = self._exporter.build_records(audit_events)
        summary = {
            'tenant_id': normalized_tenant_id,
            'product_id': normalized_product_id,
            'flags': {
                'pricing': flags.pricing,
                'paywalls': flags.paywalls,
                'subscriptions': flags.subscriptions,
                'experiments': flags.experiments,
            },
            'world_state_metrics': dict(world_state.metrics),
            'ltv': ltv.to_dict(),
            'churn': churn.to_dict(),
            'approval': approval.to_dict(),
            'experiments_count': len(experiments),
            'action_mappings_count': len(action_mappings),
        }
        return RevenueOSReport(
            world_state=world_state,
            ltv=ltv,
            churn=churn,
            intents=tuple(intents),
            experiments=tuple(experiments),
            approval=approval,
            action_mappings=tuple(action_mappings),
            audit_records=tuple(audit_records),
            summary=summary,
        )


__all__ = ['CANON_ADVISORY_REVENUE_OS_FACADE', 'RevenueOSFacade', 'RevenueOSReport']
