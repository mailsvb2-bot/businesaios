from __future__ import annotations

from core.ai.world_state import WorldStateV1
from core.ai_ceo.ledger import GrowthSnapshotV1
from core.ai_ceo.planner import build_ceo_plan
from core.ai_ceo.planner_support import build_plan as build_plan_support
from core.ai_ceo.safety import AutonomyPolicyV1
from core.marketing.llm_composer import LLMComposerConfig, MarketingLLMComposer
from runtime.boot.builders.ads_stack import wire_ads_stack
from runtime.boot.builders.ai_ceo_planner import build_runtime_ai_ceo_planner


class _LLM:
    def generate_sync(self, req):  # pragma: no cover - trivial stub
        return None


def _state() -> WorldStateV1:
    return WorldStateV1(
        schema_version=1,
        tenant_id="t1",
        user_id="u1",
        user={"user_id": "u1", "locale": "ru"},
        session={"channel": "telegram", "locale": "ru"},
        product={"default_offer": {"offer_id": "o1", "title": "Offer", "price_minor": 0, "currency": "RUB"}},
        economy={},
        timestamp_ms=1,
    )


def test_ai_ceo_support_build_plan_matches_contract_shape() -> None:
    plan = build_plan_support(state=_state(), snapshot=GrowthSnapshotV1(), autonomy=AutonomyPolicyV1())
    assert plan.plan_id == "ai_ceo_plan"
    assert isinstance(plan.kpi_targets, dict)
    assert not hasattr(plan, "targets")


def test_ai_ceo_planner_delegates_to_single_canonical_builder() -> None:
    direct = build_ceo_plan(state=_state(), snapshot=GrowthSnapshotV1(), autonomy=AutonomyPolicyV1(), plan_id="same")
    support = build_plan_support(state=_state(), snapshot=GrowthSnapshotV1(), autonomy=AutonomyPolicyV1(), plan_id="same")
    assert direct.steps == support.steps
    assert direct.kpi_targets == support.kpi_targets


def test_marketing_llm_composer_exposes_public_llm_client() -> None:
    llm = _LLM()
    composer = MarketingLLMComposer(llm, LLMComposerConfig(model="m"))
    assert composer.llm_client is llm


def test_ads_stack_prefers_public_llm_property_over_private_attr(tmp_path, monkeypatch) -> None:
    class _Composer:
        llm_client = object()

    monkeypatch.setattr('runtime.boot.builders.ads_stack.env_path', lambda *_args, **_kwargs: tmp_path)
    monkeypatch.setattr('runtime.boot.builders.ads_stack.build_ads_runtime', lambda **_kwargs: object())
    monkeypatch.setattr('runtime.boot.builders.ads_stack.build_ads_service', lambda _runtime: object())
    monkeypatch.setattr('runtime.boot.builders.ads_stack.ads_rl_builder.build_ads_rl_service', lambda **_kwargs: None)
    monkeypatch.setattr('runtime.boot.builders.ads_stack.campaign_builder_builder.build_autopilot_campaign_builder', lambda *, llm_client: llm_client)

    class _Log:
        def getLogger(self, _name):
            return object()

    out = wire_ads_stack(
        tenant_id='t1',
        repo_root=tmp_path,
        event_store=None,
        event_log=None,
        logging_mod=_Log(),
        composer=_Composer(),
    )
    assert out['campaign_builder'] is _Composer.llm_client




def test_runtime_ai_ceo_planner_builds_canonical_plan() -> None:
    planner = build_runtime_ai_ceo_planner(event_store=None)
    plan = planner.build_plan(tenant_id="tenant-a", objective="growth", horizon="30d", decision_id="d1", correlation_id="c1")
    assert plan.plan_id == "d1"
    assert plan.steps
    assert plan.kpi_targets["horizon_days"] == 30
