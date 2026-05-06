from core.ai.world_state import WorldStateV1
from core.ai_ceo.contracts import CEOPlanV1
from core.ai_ceo.ledger import GrowthSnapshotV1
from core.ai_ceo.planner import build_ceo_plan
from core.ai_ceo.safety import AutonomyPolicyV1


def _state() -> WorldStateV1:
    return WorldStateV1(
        schema_version=1,
        user={"user_id": "u1"},
        session={"args": "14 low"},
        product={},
        economy={},
        timestamp_ms=1,
        tenant_id="t1",
        user_id="u1",
    )


def test_build_ceo_plan_never_returns_none_when_ranking_fails(monkeypatch):
    import core.ai_ceo.planner as planner

    def boom(*args, **kwargs):
        raise RuntimeError("rank failed")

    monkeypatch.setattr(planner, "rank_steps", boom)
    plan = build_ceo_plan(
        state=_state(),
        snapshot=GrowthSnapshotV1(profit_minor=100, revenue_minor=200, spend_minor=100, leads=3),
        autonomy=AutonomyPolicyV1(),
    )
    assert isinstance(plan, CEOPlanV1)
    assert len(plan.steps) == 3


def test_safe_offer_returns_dict_even_on_bad_product():
    s = _state()
    s = WorldStateV1(**{**s.__dict__, "product": object()})
    plan = build_ceo_plan(
        state=s,
        snapshot=GrowthSnapshotV1(profit_minor=1, revenue_minor=2, spend_minor=1, leads=1),
        autonomy=AutonomyPolicyV1(),
    )
    assert isinstance(plan.steps[0].payload.get("offer"), dict)
