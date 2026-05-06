from core.actions.action_names import ADS_APPLY_EXECUTE_V1, AI_CEO_PLAN_V1, EXECUTE_PLAN_V1
from core.actions.names import (
    ACTION_ADS_APPLY_EXECUTE_V1,
    ACTION_AI_CEO_PLAN_V1,
    ACTION_EXECUTE_PLAN_V1,
)


def test_action_name_shim_points_to_canonical_names():
    assert ADS_APPLY_EXECUTE_V1 == ACTION_ADS_APPLY_EXECUTE_V1
    assert ADS_APPLY_EXECUTE_V1.startswith("ads_apply_") and ADS_APPLY_EXECUTE_V1.endswith("@v1")
    assert AI_CEO_PLAN_V1 == ACTION_AI_CEO_PLAN_V1 == "ai_ceo_plan@v1"
    assert EXECUTE_PLAN_V1 == ACTION_EXECUTE_PLAN_V1 == "execute_plan@v1"
