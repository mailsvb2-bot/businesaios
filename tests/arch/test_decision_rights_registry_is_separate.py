from pathlib import Path


def test_decision_rights_registry_is_separate() -> None:
    assert Path("infra/decision_rights_registry.py").exists()
    assert Path("infra/authority_scopes.py").exists()
