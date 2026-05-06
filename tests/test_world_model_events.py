from __future__ import annotations

from runtime.events.world_model_events import (
    build_world_model_pin_check_event,
    build_world_model_pinned_event,
)


def test_build_world_model_pinned_event():
    event = build_world_model_pinned_event(
        decision_id="d1",
        user_id="u1",
        world_model_meta={"pricing_world_model_hash": "abc"},
        issuer_id="core",
        timestamp_ms=123,
    )
    assert event["type"] == "decision.world_model_pinned"
    assert event["world_model_meta"]["pricing_world_model_hash"] == "abc"


def test_build_world_model_pin_check_event():
    event = build_world_model_pin_check_event(
        decision_id="d1",
        user_id="u1",
        check_result={"ok": True, "reason": "world_model_pin_match"},
        issuer_id="executor",
        timestamp_ms=456,
    )
    assert event["type"] == "decision.world_model_pin_checked"
    assert event["pin_check"]["ok"] is True
