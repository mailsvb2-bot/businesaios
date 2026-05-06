from core.actions import build_schema_registry
from core.ai.world_state import WorldStateV1
from core.ai_ceo.ledger import GrowthSnapshotV1
from core.ai_ceo.planner import build_ceo_plan
from core.ai_ceo.safety import AutonomyPolicyV1


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


def test_ai_ceo_plan_steps_validate_against_action_catalog():
    reg = build_schema_registry()
    plan = build_ceo_plan(state=_state(), snapshot=GrowthSnapshotV1(), autonomy=AutonomyPolicyV1())
    for step in plan.steps:
        reg.validate(step.action, dict(step.payload or {}))


def test_ai_ceo_plan_contains_no_placeholder_payloads():
    plan = build_ceo_plan(state=_state(), snapshot=GrowthSnapshotV1(), autonomy=AutonomyPolicyV1())
    joined = str([dict(s.payload or {}) for s in plan.steps])
    assert "placeholder" not in joined.lower()
    assert "request_pricing_change@v1" not in [s.action for s in plan.steps]
