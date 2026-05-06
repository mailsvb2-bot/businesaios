from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_runtime_orchestrator_stays_readiness_owner_only() -> None:
    text = _read("runtime/runtime_orchestrator.py")
    assert "CANON_RUNTIME_ROOT_READINESS_OWNER = True" in text
    assert "CANON_RUNTIME_ROOT_NO_ASSEMBLY = True" in text
    assert "CANON_RUNTIME_ROOT_NO_DECISION_LOGIC = True" in text
    assert "def _mark_runtime_ready(" in text
    assert "compose_runtime(" not in text
    assert ".issue(" not in text



def test_runtime_recovery_stays_fail_closed_without_decision_calls() -> None:
    text = _read("runtime/recovery.py")
    assert "CANON_RUNTIME_RECOVERY_OWNER = True" in text
    assert "CANON_RUNTIME_RECOVERY_NO_DECISION_LOGIC = True" in text
    assert "CANON_RUNTIME_RECOVERY_FAIL_CLOSED = True" in text
    assert "def _handle_non_resume_action(" in text
    assert "def _handle_recovery_execution_failure(" in text
    assert ".issue(" not in text
