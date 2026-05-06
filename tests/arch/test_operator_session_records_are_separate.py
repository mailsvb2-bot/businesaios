from pathlib import Path


def test_operator_session_records_are_separate() -> None:
    assert Path("infra/operator_session_records.py").exists()
