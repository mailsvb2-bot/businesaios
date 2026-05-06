from __future__ import annotations

from decimal import Decimal

from config.ads_rl_policy import AdsRLRewardPolicy, AdsRLServicePolicy
from config.economics_builder_policy import BudgetEnvelopeBuilderPolicy
from config.strategic_finance_advisory_policy import StrategicFinanceAdvisoryPolicyDefaults
from core.economics.builders.budget_envelope_builder import BudgetEnvelopeBuilder
from core.economics.enums import BudgetPressureLevel, MarginHealthStatus
from core.economics.types import CashflowSignal, MarginSnapshot, SpendSignal
from core.finance.strategic.allocation.allocation_constraints import AllocationConstraints
from core.finance.strategic.services.advisory_policy import StrategicFinanceAdvisoryPolicy
from core.growth.ads.rl.contracts import AdsRLAction, AdsRLOptSpec, AdsRLState
from core.growth.ads.rl.reward import compute_reward
from core.growth.ads.rl.service import AdsRLOptimizerDeps, AdsRLOptimizerService
from runtime.platform.event_store.memory_event_store import MemoryEventStore


class _DummyAds:
    def get_campaign_metrics(self, *args, **kwargs):
        raise AssertionError('not used in this test')


def test_budget_envelope_builder_uses_policy_owner_for_legacy_knobs() -> None:
    builder = BudgetEnvelopeBuilder(
        policy=BudgetEnvelopeBuilderPolicy(
            reserve_ratio=0.10,
            minimum_budget_ratio_of_cash=0.40,
            medium_pressure_spend_multiple=2.0,
            minimum_free_cash_threshold=1.0,
            low_pressure_multiplier=1.0,
            medium_pressure_multiplier=0.8,
            high_pressure_multiplier=0.5,
            extreme_pressure_multiplier=0.2,
        )
    )
    result = builder.build(
        cashflow=CashflowSignal(cash_in=0.0, cash_out=0.0, runway_days=0, unrestricted_cash=1000.0, currency='USD'),
        spend=SpendSignal(period_days=30, marketing_spend=10.0, sales_spend=10.0, operations_spend=10.0, currency='USD'),
        margin=MarginSnapshot(gross_margin_ratio=0.4, net_margin_ratio=0.2, status=MarginHealthStatus.STABLE),
    )
    assert result.protected_cash_reserve == 100.0
    assert result.recommended_spend_cap == 400.0
    assert result.pressure_level == BudgetPressureLevel.LOW


def test_strategic_finance_advisory_policy_uses_instance_objective() -> None:
    policy = StrategicFinanceAdvisoryPolicy(
        StrategicFinanceAdvisoryPolicyDefaults(objective='custom_objective')
    )
    assert policy._policy.objective == 'custom_objective'


def test_compute_reward_honors_custom_reward_policy() -> None:
    state = AdsRLState(tenant_id='t', platform='meta', campaign_id='c', ts_ms=0, spend=0.0, revenue=10.0)
    spec = AdsRLOptSpec(platform='meta', campaign_id='c', daily_budgets=[], bid_caps=[], cpa_targets=[], creatives=[], audiences=[], objectives=[], reward_mode='roas')
    breakdown = compute_reward(
        state=state,
        spec=spec,
        policy=AdsRLRewardPolicy(roas_when_no_spend_with_revenue=77.0),
    )
    assert breakdown.reward == 77.0


def test_ads_rl_service_report_uses_instance_policy_default_limit() -> None:
    service = AdsRLOptimizerService(
        AdsRLOptimizerDeps(
            ads=_DummyAds(),
            event_store=MemoryEventStore(),
            policy=AdsRLServicePolicy(default_report_limit=7),
        )
    )
    called = {}

    def _load_recent_observed(*, tenant_id: str, campaign_id: str, limit: int):
        called['limit'] = limit
        return []

    service._exp.load_recent_observed = _load_recent_observed  # type: ignore[method-assign]
    report = service.report(tenant_id='t', campaign_id='c')
    assert called['limit'] == 7
    assert report['campaign_id'] == 'c'
