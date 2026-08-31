from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_action_intent_and_policy_decision_have_single_contract_owners() -> None:
    role = (ROOT / "contracts" / "CANON_NAMESPACE_ROLE.md").read_text(encoding="utf-8")
    autonomy = (ROOT / "application" / "autonomy" / "autonomy_tiers.py").read_text(encoding="utf-8")
    decision_core = (ROOT / "core" / "ai" / "decision_core.py").read_text(encoding="utf-8")
    assert all(name in role for name in ("ActionIntentV1", "PolicyDecisionV1", "BusinessOutcomeV1"))
    assert "class AutonomyDecision" not in autonomy
    assert "AutonomyDecision = PolicyDecisionV1" in autonomy
    assert "def project_action_intent(" in decision_core
    assert "ExecutableAction(" in decision_core
