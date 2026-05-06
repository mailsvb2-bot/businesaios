from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_decision_gateway_owns_issue_then_execute_sequence() -> None:
    gateway = (ROOT / "runtime" / "decision_gateway.py").read_text(encoding="utf-8")
    helper = (ROOT / "runtime" / "scheduler_parts" / "decision_request.py").read_text(encoding="utf-8")

    assert "CANON_RUNTIME_DECISION_GATEWAY_OWNS_EXECUTION_SEQUENCE = True" in gateway
    assert "def execute_runtime_decision(" in gateway
    assert "issue_runtime_decision(" in gateway
    assert 'lock_execution_envelope(envelope=envelope)' in gateway
    assert 'execute_locked_decision(executor=executor, locked_path=locked_execution)' in gateway

    assert "execute_runtime_decision" in helper
    assert "CANON_RUNTIME_SCHEDULER_DECISION_REQUEST_GATEWAY_EXECUTION_OWNER = True" in helper
    assert "executor.execute(" not in helper
    assert "issue_runtime_decision(" not in helper
