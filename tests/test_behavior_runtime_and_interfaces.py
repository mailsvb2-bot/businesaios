from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.behavior.runtime.contact_backpressure import should_throttle_contact
from core.behavior.runtime.retry_cooldown import next_retry_time
from interfaces.behavior.thin_runtime_adapter import build_world_state_with_behavior
from interfaces.behavior.thin_telemetry_adapter import ThinBehaviorTelemetryAdapter


def test_should_throttle_contact() -> None:
    assert should_throttle_contact({"contact_frequency_cap": 2}, 2) is True
    assert should_throttle_contact({"contact_frequency_cap": 2}, 1) is False


def test_next_retry_time_moves_forward() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0)
    assert next_retry_time(now, 2) > now


def test_build_world_state_with_behavior(tmp_path: Path) -> None:
    world_state: dict[str, object] = {}
    result = build_world_state_with_behavior(
        "u1",
        [
            {
                "event_id": "1",
                "event_type": "message_open",
                "channel": "telegram",
                "product": "demo",
            }
        ],
        world_state,
        catalog_root=tmp_path / "catalogs",
        policy_root=tmp_path / "policies",
    )
    assert "behavior" in result
    assert "price_constraints" in result


def test_thin_behavior_telemetry_adapter_builds_metrics_event() -> None:
    adapter = ThinBehaviorTelemetryAdapter()
    events = adapter.build_events(
        "u1",
        {"behavior": {"coherence_score": 0.7, "policy_denials": {}}},
        now=datetime(2026, 1, 1, 12, 0, 0),
    )
    assert any(event["event_type"] == "behavior_metrics" for event in events)
