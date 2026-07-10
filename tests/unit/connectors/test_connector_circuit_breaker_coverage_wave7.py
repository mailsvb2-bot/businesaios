from __future__ import annotations

import json
from pathlib import Path

import pytest

from connectors.platform.connector_circuit_breaker import (
    BreakerState,
    CircuitBreakerRule,
    ConnectorCircuitBreaker,
    connector_circuit_breaker_path,
)


class FakeClock:
    def __init__(self, value: float = 1000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def test_connector_circuit_breaker_path_uses_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUSINESAIOS_DATA_DIR", str(tmp_path))

    path = connector_circuit_breaker_path()

    assert path == tmp_path / "connectors" / "connector_circuit_breaker_state.json"
    assert path.parent.exists()


def test_circuit_breaker_rule_validation_matching_and_trip_reasons() -> None:
    rule = CircuitBreakerRule(
        connector_id=" connector-1 ",
        provider="provider",
        version="v1",
        operation="sync",
        trip_reasons=("timeout", "timeout", "", "rate_limited"),
    )

    assert rule.connector_id == "connector-1"
    assert rule.matches(connector_id="connector-1", provider="provider", version="v1", operation="sync")
    assert not rule.matches(connector_id="connector-2", provider="provider", version="v1", operation="sync")
    assert rule.trips_on("timeout")
    assert rule.trips_on("rate_limited")
    assert not rule.trips_on("ignored")

    with pytest.raises(ValueError, match="connector_id is required"):
        CircuitBreakerRule(connector_id=" ")

    with pytest.raises(ValueError, match="failure_threshold must be > 0"):
        CircuitBreakerRule(connector_id="x", failure_threshold=0)

    with pytest.raises(ValueError, match="recovery_timeout_seconds must be > 0"):
        CircuitBreakerRule(connector_id="x", recovery_timeout_seconds=0)

    with pytest.raises(ValueError, match="half_open_max_calls must be > 0"):
        CircuitBreakerRule(connector_id="x", half_open_max_calls=0)

    with pytest.raises(ValueError, match="success_threshold must be > 0"):
        CircuitBreakerRule(connector_id="x", success_threshold=0)

    with pytest.raises(ValueError, match="half_open_window_seconds must be > 0"):
        CircuitBreakerRule(connector_id="x", half_open_window_seconds=0)


def test_rule_for_prefers_specific_rule_over_default(tmp_path: Path) -> None:
    clock = FakeClock()
    breaker = ConnectorCircuitBreaker(
        default_rule=CircuitBreakerRule(connector_id="*", failure_threshold=9),
        rules=(
            CircuitBreakerRule(connector_id="*", provider="provider", failure_threshold=5),
            CircuitBreakerRule(connector_id="connector-1", provider="provider", version="v1", operation="sync", failure_threshold=2),
        ),
        state_path=tmp_path / "breaker.json",
        time_fn=clock,
    )

    rule = breaker.rule_for(connector_id="connector-1", provider="provider", version="v1", operation="sync")

    assert rule.connector_id == "connector-1"
    assert rule.failure_threshold == 2

    breaker.register_rule(CircuitBreakerRule(connector_id="connector-2", failure_threshold=4))
    assert breaker.rule_for(connector_id="connector-2", provider="x", version="v1", operation="op").failure_threshold == 4


def test_closed_open_half_open_and_success_close_flow(tmp_path: Path) -> None:
    clock = FakeClock()
    state_path = tmp_path / "breaker.json"
    breaker = ConnectorCircuitBreaker(
        default_rule=CircuitBreakerRule(
            connector_id="*",
            failure_threshold=2,
            recovery_timeout_seconds=10,
            half_open_max_calls=1,
            success_threshold=1,
            half_open_window_seconds=5,
            trip_reasons=("timeout",),
        ),
        state_path=state_path,
        time_fn=clock,
    )

    allowed = breaker.allow_call(connector_id="c", provider="p", version="v", operation="sync")
    assert allowed.allowed is True
    assert allowed.state == BreakerState.CLOSED.value
    assert allowed.reason == "closed"

    first_failure = breaker.record_failure(
        connector_id="c",
        provider="p",
        version="v",
        operation="sync",
        reason="timeout",
        metadata={"attempt": 1},
    )
    assert first_failure.state == BreakerState.CLOSED.value
    assert first_failure.failure_count == 1
    assert first_failure.metadata == {"attempt": 1}

    second_failure = breaker.record_failure(
        connector_id="c",
        provider="p",
        version="v",
        operation="sync",
        reason="timeout",
    )
    assert second_failure.state == BreakerState.OPEN.value
    assert second_failure.open_count == 1
    assert second_failure.blocked_until == 1010.0

    blocked = breaker.allow_call(connector_id="c", provider="p", version="v", operation="sync")
    assert blocked.allowed is False
    assert blocked.reason == "circuit_open"

    clock.advance(11)

    half_open = breaker.allow_call(connector_id="c", provider="p", version="v", operation="sync")
    assert half_open.allowed is True
    assert half_open.state == BreakerState.HALF_OPEN.value
    assert half_open.reason == "half_open_probe"

    exhausted = breaker.allow_call(connector_id="c", provider="p", version="v", operation="sync")
    assert exhausted.allowed is False
    assert exhausted.reason == "half_open_budget_exhausted"

    closed = breaker.record_success(connector_id="c", provider="p", version="v", operation="sync", metadata={"ok": True})
    assert closed.state == BreakerState.CLOSED.value
    assert closed.failure_count == 0
    assert closed.blocked_until is None
    assert closed.last_success_at == clock.value

    rows = breaker.snapshot()
    assert rows[0]["connector_id"] == "c"
    assert rows[0]["state"] == BreakerState.CLOSED.value

    assert json.loads(state_path.read_text(encoding="utf-8"))["state"]


def test_half_open_failure_reopens_and_force_close_resets(tmp_path: Path) -> None:
    clock = FakeClock()
    breaker = ConnectorCircuitBreaker(
        default_rule=CircuitBreakerRule(
            connector_id="*",
            failure_threshold=1,
            recovery_timeout_seconds=3,
            half_open_max_calls=1,
            success_threshold=2,
            trip_reasons=("timeout", "exception"),
        ),
        state_path=tmp_path / "breaker.json",
        time_fn=clock,
    )

    breaker.record_failure(connector_id="c", provider="p", version="v", operation="sync", reason="timeout")
    clock.advance(4)

    assert breaker.allow_call(connector_id="c", provider="p", version="v", operation="sync").reason == "half_open_probe"

    reopened = breaker.record_failure(connector_id="c", provider="p", version="v", operation="sync", reason="exception")
    assert reopened.state == BreakerState.OPEN.value
    assert reopened.open_count == 2

    breaker.force_close(connector_id="c", provider="p", version="v", operation="sync")
    snapshot = breaker.snapshot_for(connector_id="c", provider="p", version="v", operation="sync")
    assert snapshot.state == BreakerState.CLOSED.value
    assert snapshot.failure_count == 0

    breaker.force_open(connector_id="c", provider="p", version="v", operation="sync", reason="manual")
    snapshot = breaker.snapshot_for(connector_id="c", provider="p", version="v", operation="sync")
    assert snapshot.state == BreakerState.OPEN.value
    assert snapshot.last_failure_reason == "manual"


def test_half_open_window_resets_probe_budget(tmp_path: Path) -> None:
    clock = FakeClock()
    breaker = ConnectorCircuitBreaker(
        default_rule=CircuitBreakerRule(
            connector_id="*",
            failure_threshold=1,
            recovery_timeout_seconds=1,
            half_open_max_calls=1,
            success_threshold=2,
            half_open_window_seconds=2,
            trip_reasons=("timeout",),
        ),
        state_path=tmp_path / "breaker.json",
        time_fn=clock,
    )

    breaker.record_failure(connector_id="c", provider="p", version="v", operation="sync", reason="timeout")
    clock.advance(2)

    assert breaker.allow_call(connector_id="c", provider="p", version="v", operation="sync").allowed is True
    assert breaker.allow_call(connector_id="c", provider="p", version="v", operation="sync").reason == "half_open_budget_exhausted"

    clock.advance(3)

    reset_probe = breaker.allow_call(connector_id="c", provider="p", version="v", operation="sync")
    assert reset_probe.allowed is True
    assert reset_probe.reason == "half_open_probe"


def test_state_load_ignores_invalid_rows_and_restores_valid_rows(tmp_path: Path) -> None:
    state_path = tmp_path / "breaker.json"
    state_path.write_text(
        json.dumps(
            {
                "state": [
                    "bad-row",
                    {"connector_id": "", "provider": "p", "version": "v", "operation": "op"},
                    {
                        "connector_id": "c",
                        "provider": "p",
                        "version": "v",
                        "operation": "sync",
                        "state": "open",
                        "failure_count": 3,
                        "success_count": 0,
                        "opened_at": 10,
                        "blocked_until": 20,
                        "last_failure_reason": "timeout",
                        "last_failure_at": 10,
                        "last_success_at": None,
                        "half_open_in_flight": 0,
                        "open_count": 1,
                        "metadata": {"x": 1},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    breaker = ConnectorCircuitBreaker(state_path=state_path, time_fn=FakeClock(11))
    snapshot = breaker.snapshot_for(connector_id="c", provider="p", version="v", operation="sync")

    assert snapshot.state == BreakerState.OPEN.value
    assert snapshot.failure_count == 3
    assert snapshot.metadata == {"x": 1}
    assert len(breaker.snapshot()) == 1


def test_state_load_ignores_missing_or_corrupt_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    breaker = ConnectorCircuitBreaker(state_path=missing, time_fn=FakeClock())
    assert breaker.snapshot() == ()

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json", encoding="utf-8")
    breaker = ConnectorCircuitBreaker(state_path=corrupt, time_fn=FakeClock())
    assert breaker.snapshot() == ()
