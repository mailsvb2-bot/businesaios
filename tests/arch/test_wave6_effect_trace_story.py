from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_observability_exposes_effect_trace_method() -> None:
    text = (ROOT / "runtime" / "runtime_observability.py").read_text(encoding="utf-8")
    assert "def record_effect_trace(" in text


def test_runtime_connector_observability_appends_effect_trace_story() -> None:
    text = (ROOT / "runtime" / "execution" / "executor_observability.py").read_text(encoding="utf-8")
    assert "record_effect_trace" in text
    assert 'trace_name="runtime_effect"' in text or "trace_name='runtime_effect'" in text
