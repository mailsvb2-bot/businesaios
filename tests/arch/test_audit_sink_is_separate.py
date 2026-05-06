from pathlib import Path


def test_audit_sink_is_separate() -> None:
    assert Path("infra/audit_sink.py").exists()
    assert Path("infra/audit_log_service.py").exists()
