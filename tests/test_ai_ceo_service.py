from core.actions.action_names import ADS_APPLY_EXECUTE_V1
from core.ai_ceo.contracts import CEOIntentV1
from core.ai_ceo.ledger import GrowthSnapshotV1
from core.ai_ceo.service import build_minimal_plan_steps


def test_ai_ceo_service_builds_conservative_steps():
    steps = build_minimal_plan_steps(
        tenant_id="t1",
        user_id="u1",
        snapshot=GrowthSnapshotV1(),
        intent=CEOIntentV1(schema_version=1, kind="increase_profit", horizon_days=14, risk_level="low"),
    )
    assert steps
    assert all(step.action != ADS_APPLY_EXECUTE_V1 for step in steps)
