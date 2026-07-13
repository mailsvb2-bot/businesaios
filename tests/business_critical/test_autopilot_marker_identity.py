from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.boot.handler_groups.core import _track_marker_event


class FakeEffects:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def track_event(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {"ok": True}


def _env() -> SimpleNamespace:
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-autopilot",
            correlation_id="correlation-autopilot",
        )
    )


@pytest.mark.lock
def test_tenant_id_never_becomes_system_marker_user_id() -> None:
    effects = FakeEffects()

    _track_marker_event(
        payload={
            "tenant_id": "business-a",
            "product_id": "crm-pro",
            "payload": {"run_id": "run-1"},
        },
        effects=effects,
        env=_env(),
        event_type="autopilot_started",
    )

    call = effects.calls[-1]
    assert call["user_id"] == "system"
    assert call["payload"] == {
        "run_id": "run-1",
        "tenant_id": "business-a",
        "product_id": "crm-pro",
    }


@pytest.mark.lock
def test_explicit_user_actor_is_preserved_without_losing_tenant_scope() -> None:
    effects = FakeEffects()

    _track_marker_event(
        payload={
            "tenant_id": "business-a",
            "user_id": "owner-7",
            "payload": {"run_id": "run-2"},
        },
        effects=effects,
        env=_env(),
        event_type="autopilot_decision",
    )

    call = effects.calls[-1]
    assert call["user_id"] == "owner-7"
    assert call["payload"]["tenant_id"] == "business-a"
