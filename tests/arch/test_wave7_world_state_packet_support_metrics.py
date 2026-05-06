from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_world_state_integration_service_delegates_packet_metrics_to_support_owner() -> None:
    service = (ROOT / "runtime" / "integration" / "world_state_integration_service.py").read_text(encoding="utf-8")
    support = (ROOT / "runtime" / "integration" / "world_state_packet_support.py").read_text(encoding="utf-8")
    assert "emit_world_state_packet_metrics(" in service
    assert "def emit_world_state_packet_metrics(" in support
