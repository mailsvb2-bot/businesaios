from pathlib import Path


def test_retention_adapter_uses_split_helpers_v26():
    text = Path("core/retention/decision_adapter.py").read_text(encoding="utf-8")
    assert "build_retention_debug" in text
    assert "make_telemetry_step" in text
    assert "render_offer_step" in text


def test_unified_policy_uses_retention_integration_v26():
    text = Path("core/policies/telegram/unified_policy.py").read_text(encoding="utf-8")
    assert "apply_retention_constraints_to_state" in text
    assert "merge_retention_plan" in text
