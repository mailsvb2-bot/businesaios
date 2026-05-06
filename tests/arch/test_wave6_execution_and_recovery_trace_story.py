from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_observability_exposes_execution_and_recovery_trace_methods() -> None:
    text = (ROOT / "runtime" / "runtime_observability.py").read_text(encoding="utf-8")
    assert "def record_execution_trace(" in text
    assert "def record_recovery_trace(" in text


def test_runtime_execution_and_recovery_surfaces_use_trace_story() -> None:
    execution = (ROOT / "runtime" / "execution" / "executor_trace_runtime.py").read_text(encoding="utf-8")
    recovery = (ROOT / "runtime" / "executor_recovery_flow.py").read_text(encoding="utf-8")
    assert "trace_kind='execution'" in execution or 'trace_kind="execution"' in execution
    assert "record_recovery_trace" in recovery
