from __future__ import annotations

import asyncio

from core.ai_ceo.contracts import CEOIntentV1
from core.ai_ceo.ledger import GrowthSnapshotV1
from core.ai_ceo.service import build_minimal_plan_steps
from core.growth.strategy.contracts import GrowthGoalV1, GrowthSignalV1
from core.growth.strategy.llm_generator import generate_hypotheses
from core.llm.contracts import LLMResponse
from core.traffic.creative_generator import LLMCreativeGenerator
from core.traffic.strategy_service import TrafficStrategyService
from runtime.handlers.ads_apply_execute import _best_effort_route_ids
from runtime.llm_completion_support import read_provider_and_model


class _SyncCreativeGateway:
    def generate_sync(self, req):
        return LLMResponse(
            content='{"headline":"H","primary_text":"P","cta":"Написать","interests":["dentist"]}',
            usage=None,
            finish_reason='stop',
            raw={'mode': 'llm'},
        )


class _CampaignFactory:
    def build(self, **kwargs):
        return kwargs


class _AudienceSelector:
    def suggest_interests(self, *, what):
        return ['base']

    def merge_llm_interests(self, *, heuristic, llm):
        return list(dict.fromkeys(list(heuristic) + list(llm)))


class _BudgetAllocator:
    def daily_from_total(self, *, total_minor_7d):
        return total_minor_7d // 7


class _BidManager:
    def initial_bid_hint(self, *, target_cac_minor):
        return target_cac_minor


class _AsyncOnlyLLM:
    async def generate(self, req):
        return LLMResponse(content='[]', usage=None, finish_reason='stop', raw={})


def test_sync_planner_uses_public_build_with_interests_without_private_fallback_access():
    gen = LLMCreativeGenerator(llm=_SyncCreativeGateway())
    svc = TrafficStrategyService(
        campaign_factory=_CampaignFactory(),
        audience_selector=_AudienceSelector(),
        creative_generator=gen,
        budget_allocator=_BudgetAllocator(),
        bid_manager=_BidManager(),
    )
    plan = svc.plan_7d(
        tenant_id='t1',
        platform='meta',
        account_id='a1',
        what='стоматология',
        offer_title='Чистка',
        region='Москва',
        total_budget_minor_7d=700,
        budget_currency='RUB',
        target_cac_minor=100,
        destination={'url': 'https://x'},
        seed='v1',
    )
    assert 'dentist' in plan.campaign['interests']
    assert plan.metadata['creative_source'] == 'llm'


def test_growth_strategy_llm_generator_fails_closed_inside_running_loop_without_sync_bridge():
    async def _run():
        return generate_hypotheses(
            _AsyncOnlyLLM(),
            tenant_id='t1',
            goal=GrowthGoalV1(primary_stage='revenue', horizon_days=7, kpi='profit_minor', target_delta_pct=5.0),
            signals=GrowthSignalV1(tenant_id='t1', leads_today=1, spend_today_minor=1, revenue_today_minor=1, profit_today_minor=1, conversion_lead_to_purchase_pct=0.1, retention_d7_pct=0.1),
            n=2,
        )

    out = asyncio.run(_run())
    assert out == ()


def test_marketing_llm_provider_reader_returns_effective_default_model(monkeypatch):
    monkeypatch.delenv('MARKETING_LLM_MODEL', raising=False)
    monkeypatch.setenv('MARKETING_LLM_PROVIDER', 'anthropic')
    monkeypatch.delenv('ANTHROPIC_MODEL', raising=False)
    provider, model = read_provider_and_model(provider_override=None, model_override=None)
    assert provider == 'anthropic'
    assert model == 'claude-3-5-sonnet-latest'


def test_ads_apply_route_violation_uses_best_effort_env_ids():
    class _Decision:
        decision_id = 'd1'
        correlation_id = 'c1'
    class _Env:
        decision = _Decision()
    assert _best_effort_route_ids(payload={}, env=_Env()) == ('d1', 'c1')


def test_ai_ceo_service_still_uses_canonical_safe_steps_shape():
    steps = build_minimal_plan_steps(
        tenant_id='t1',
        user_id='u1',
        snapshot=GrowthSnapshotV1(leads=0, spend_minor=0, revenue_minor=0, profit_minor=0),
        intent=CEOIntentV1(kind='increase_profit', horizon_days=7, risk_level='low'),
    )
    assert steps
    assert all(step.action in {'one_click_value@v1', 'send_message@v1'} for step in steps)
