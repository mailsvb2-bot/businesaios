from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_observability_exposes_trace_story_owner() -> None:
    text = (ROOT / "runtime" / "runtime_observability.py").read_text(encoding="utf-8")
    assert "CANON_RUNTIME_OBSERVABILITY_ONE_TRACE_STORY = True" in text
    assert "def record_trace_story(" in text
    assert "def record_world_state_trace(" in text
    assert "def record_decision_trace(" in text


def test_world_state_and_decision_surfaces_use_runtime_trace_story() -> None:
    integration = (ROOT / "runtime" / "integration" / "world_state_integration_service.py").read_text(encoding="utf-8")
    gateway = (ROOT / "runtime" / "decision_gateway.py").read_text(encoding="utf-8")
    assert "record_world_state_trace(" in integration
    assert "record_decision_trace(" in gateway
