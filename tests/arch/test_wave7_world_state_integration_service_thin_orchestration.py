from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_world_state_integration_service_uses_support_owned_trace_helpers() -> None:
    service = (ROOT / "runtime" / "integration" / "world_state_integration_service.py").read_text(encoding="utf-8")
    support = (ROOT / "runtime" / "integration" / "world_state_packet_support.py").read_text(encoding="utf-8")
    assert "emit_world_state_observed_trace(" in service
    assert "emit_world_state_materialized_trace(" in service
    assert "def emit_world_state_observed_trace(" in support
    assert "def emit_world_state_materialized_trace(" in support
