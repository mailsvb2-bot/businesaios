from pathlib import Path


def test_forbidden_operator_actions_are_separate() -> None:
    assert Path("infra/forbidden_operator_actions.py").exists()
    assert Path("infra/escalation_routes.py").exists()
