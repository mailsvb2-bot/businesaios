from pathlib import Path


def test_decision_ledger_is_separate() -> None:
    assert Path("infra/decision_ledger.py").exists()
    assert Path("infra/rollback_service.py").exists()
