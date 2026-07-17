from __future__ import annotations

import pytest

from core.ai import (
    get_decision_core_singleton,
    reset_decision_core_singleton,
    set_decision_core_singleton,
)
from runtime.boot import boot_decision_core


@pytest.fixture(autouse=True)
def _isolated_singleton():
    reset_decision_core_singleton()
    try:
        yield
    finally:
        reset_decision_core_singleton()


def test_boot_registers_the_exact_core_before_returning(monkeypatch) -> None:
    world_model = object()
    core = object()
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        boot_decision_core,
        "build_world_model",
        lambda *, event_log: world_model,
    )

    def _construct_core(**kwargs):
        captured.update(kwargs)
        return core

    monkeypatch.setattr(
        boot_decision_core,
        "DecisionCore",
        _construct_core,
    )

    result_world_model, result_core = boot_decision_core.build_decision_core(
        policy_selector="selector",
        keyring="keyring",
        schemas="schemas",
        snapshot_store="snapshots",
        event_log="events",
        decision_archive="archive",
        issuer_id="issuer",
    )

    assert result_world_model is world_model
    assert result_core is core
    assert get_decision_core_singleton() is core
    assert captured == {
        "selector": "selector",
        "keyring": "keyring",
        "schema_registry": "schemas",
        "snapshot_store": "snapshots",
        "event_log": "events",
        "decision_archive": "archive",
        "world_model": world_model,
        "issuer_id": "issuer",
    }


def test_conflicting_registration_fails_closed(monkeypatch) -> None:
    registered = object()
    conflicting = object()
    set_decision_core_singleton(registered)

    monkeypatch.setattr(
        "core.observability.arch_violation.log_arch_violation",
        lambda _code: None,
    )
    monkeypatch.setattr(
        "core.runtime.safe_mode.enter_safe_mode",
        lambda _code: None,
    )

    with pytest.raises(
        SystemExit,
        match="ARCH_VIOLATION: MULTI_DECISIONCORE",
    ):
        set_decision_core_singleton(conflicting)

    assert get_decision_core_singleton() is registered
