from __future__ import annotations

from pathlib import Path

from runtime import admin_pricing_support
from runtime.admin_pricing_support import (
    build_pricing_change_payload,
    emit_pricing_change_event,
    emit_pricing_reset,
)


class _EventLog:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.events: list[dict[str, object]] = []

    def emit(self, **payload: object) -> None:
        if self.fail:
            raise RuntimeError("event store unavailable")
        self.events.append(dict(payload))


def test_admin_pricing_payload_and_event_are_public_pure_helpers() -> None:
    payload = build_pricing_change_payload(
        request_id="request-1",
        plan_id=7,
        new_price=1250,
        pricing_version="v2",
        requested_by="admin-1",
        reason="reviewed",
        suggested_pricing_version="v3",
        rejected_by="admin-2",
        plans_path="plans.json",
        override_path="override.json",
        override_persisted=True,
    )
    assert payload == {
        "request_id": "request-1",
        "plan_id": 7,
        "new_price": 1250,
        "pricing_version": "v2",
        "requested_by": "admin-1",
        "reason": "reviewed",
        "suggested_pricing_version": "v3",
        "rejected_by": "admin-2",
        "plans_path": "plans.json",
        "override_path": "override.json",
        "override_persisted": True,
    }
    event_log = _EventLog()
    emit_pricing_change_event(
        event_log,
        event_type="pricing_change_requested",
        decision_id="decision-1",
        correlation_id="correlation-1",
        admin_id="admin-1",
        payload=payload,
    )
    assert event_log.events == [
        {
            "event_type": "pricing_change_requested",
            "source": "pricing.governance",
            "user_id": "admin-1",
            "decision_id": "decision-1",
            "correlation_id": "correlation-1",
            "payload": payload,
        }
    ]


def test_admin_pricing_reset_is_best_effort_and_auditable(monkeypatch) -> None:
    event_log = _EventLog()
    emit_pricing_reset(
        event_log,
        decision_id="decision-1",
        correlation_id="correlation-1",
        admin_id="admin-1",
    )
    assert event_log.events[0]["payload"] == {
        "key": "admin:pricing_session",
        "value": {},
    }

    swallowed: list[tuple[str, str]] = []
    monkeypatch.setattr(
        admin_pricing_support,
        "swallow",
        lambda module, key: swallowed.append((module, key)),
    )
    emit_pricing_reset(
        _EventLog(fail=True),
        decision_id="decision-2",
        correlation_id="correlation-2",
        admin_id="admin-2",
    )
    assert swallowed == [
        (
            "runtime.admin_pricing_support",
            "admin_pricing_support.emit_pricing_reset",
        )
    ]


def test_public_admin_state_surface_does_not_import_internal_effect_module() -> None:
    root = Path(__file__).resolve().parents[3]
    source = (root / "runtime" / "admin_state_support.py").read_text(
        encoding="utf-8"
    )
    assert "runtime._internal.effects_domains.admin_pricing_effects" not in source
    assert "from runtime.admin_pricing_support import" in source


def test_admin_pricing_payload_omits_empty_optional_fields() -> None:
    assert build_pricing_change_payload() == {
        "request_id": "",
        "override_persisted": False,
    }
