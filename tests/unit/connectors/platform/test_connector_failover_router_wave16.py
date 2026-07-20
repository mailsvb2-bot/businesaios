from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from connectors.platform.connector_capability_contract import (
    ConnectorCapabilityDescriptor,
    ConnectorMaturity,
)
from connectors.platform.connector_contract import (
    ConnectorRequest,
    ConnectorVerificationRequest,
)
from connectors.platform.connector_failover_router import ConnectorFailoverRouter
from connectors.platform.connector_registry import ConnectorRegistry, ConnectorRegistryEntry
from connectors.platform.connector_retry_policy import ConnectorRetryPolicy, ConnectorRetryRule
from interfaces.common.connector_health import ConnectorHealth
from interfaces.common.connector_result import ConnectorResult


class _DirectTimeoutPolicy:
    def run(self, fn, **kwargs):
        return fn()


class _ScriptedConnector:
    def __init__(
        self,
        *,
        provider: str,
        outcomes: list[object],
        connector_id: str = "payments",
        version: str = "v1",
        write: bool = True,
    ) -> None:
        self.connector_id = connector_id
        self.provider = provider
        self.version = version
        self._outcomes = list(outcomes)
        self.execute_calls = 0
        self.verify_calls = 0
        self._write = write

    def capabilities(self) -> ConnectorCapabilityDescriptor:
        return ConnectorCapabilityDescriptor(
            connector_id=self.connector_id,
            provider=self.provider,
            version=self.version,
            maturity=ConnectorMaturity.CAPABILITY_SHELL,
            supports_read=True,
            supports_write=self._write,
            supports_verify=True,
            supports_dry_run=True,
            supports_idempotency=True,
            operation_names=("charge",),
        )

    def health(self) -> ConnectorHealth:
        return ConnectorHealth(connector_name=self.connector_id, healthy=True)

    def execute(self, request: ConnectorRequest) -> ConnectorResult:
        self.execute_calls += 1
        return self._next()

    def verify(self, request: ConnectorVerificationRequest) -> ConnectorResult:
        self.verify_calls += 1
        return self._next()

    def build_snapshot(self, *, tenant_id: str):
        return {"tenant_id": tenant_id}

    def _next(self) -> ConnectorResult:
        if not self._outcomes:
            raise AssertionError("unexpected connector call")
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        assert isinstance(outcome, ConnectorResult)
        return outcome


@dataclass
class _Breaker:
    blocked_provider: str | None = None
    fail_success_record: bool = False
    fail_failure_record: bool = False

    def __post_init__(self) -> None:
        self.successes: list[str] = []
        self.failures: list[tuple[str, str]] = []

    def allow_call(self, *, provider: str, **kwargs):
        if provider == self.blocked_provider:
            return SimpleNamespace(
                allowed=False,
                state="open",
                reason="circuit_open",
                blocked_until=123.0,
            )
        return SimpleNamespace(
            allowed=True,
            state="closed",
            reason="closed",
            blocked_until=None,
        )

    def record_success(self, *, provider: str, **kwargs):
        self.successes.append(provider)
        if self.fail_success_record:
            raise RuntimeError("breaker success write failed")

    def record_failure(self, *, provider: str, reason: str, **kwargs):
        self.failures.append((provider, reason))
        if self.fail_failure_record:
            raise RuntimeError("breaker failure write failed")


class _HealthMonitor:
    def __init__(self, *, unhealthy_provider: str | None = None, fail_record: bool = False) -> None:
        self.unhealthy_provider = unhealthy_provider
        self.fail_record = fail_record
        self.samples = []

    def verdict(self, *, provider: str, **kwargs):
        healthy = provider != self.unhealthy_provider
        return SimpleNamespace(
            healthy=healthy,
            reason="healthy" if healthy else "probe_failed",
            stale=False,
        )

    def record(self, sample):
        self.samples.append(sample)
        if self.fail_record:
            raise RuntimeError("health write failed")


class _FailingObservability:
    def __init__(self) -> None:
        self.calls = 0

    def record(self, event) -> None:
        self.calls += 1
        raise RuntimeError("observability unavailable")


def _registry(*connectors: _ScriptedConnector) -> ConnectorRegistry:
    registry = ConnectorRegistry()
    for rank, connector in enumerate(connectors, start=1):
        registry.register(
            ConnectorRegistryEntry(
                connector_id=connector.connector_id,
                provider=connector.provider,
                version=connector.version,
                connector=connector,
                rank=rank,
            )
        )
    return registry


def _retry_policy(max_attempts: int = 1) -> ConnectorRetryPolicy:
    return ConnectorRetryPolicy(
        default_rule=ConnectorRetryRule(
            max_attempts=max_attempts,
            base_delay_seconds=0,
            max_delay_seconds=0,
            jitter_ratio=0,
        )
    )


def _request(*, idempotency_key: str | None = None, dry_run: bool = False) -> ConnectorRequest:
    return ConnectorRequest(
        tenant_id="tenant-a",
        connector_id="payments",
        operation="charge",
        payload={"amount": 100},
        idempotency_key=idempotency_key,
        dry_run=dry_run,
        trace_id="trace-1",
    )


def _router(
    *connectors: _ScriptedConnector,
    breaker=None,
    health=None,
    observability=None,
    sleep_fn=None,
    max_attempts: int = 1,
) -> ConnectorFailoverRouter:
    return ConnectorFailoverRouter(
        registry=_registry(*connectors),
        circuit_breaker=breaker,
        health_monitor=health,
        observability=observability,
        retry_policy=_retry_policy(max_attempts),
        timeout_policy=_DirectTimeoutPolicy(),
        sleep_fn=sleep_fn,
    )


def test_non_idempotent_write_does_not_fail_over_after_ambiguous_exception() -> None:
    primary = _ScriptedConnector(provider="a", outcomes=[ConnectionError("response lost")])
    fallback = _ScriptedConnector(
        provider="b",
        outcomes=[ConnectorResult(ok=True, code="ok")],
    )
    router = _router(primary, fallback)

    with pytest.raises(ConnectionError, match="response lost"):
        router.execute(_request(), require_write=True)

    assert primary.execute_calls == 1
    assert fallback.execute_calls == 0


def test_non_idempotent_write_can_select_fallback_before_any_call() -> None:
    primary = _ScriptedConnector(
        provider="a",
        outcomes=[ConnectorResult(ok=True, code="unexpected")],
    )
    fallback = _ScriptedConnector(
        provider="b",
        outcomes=[ConnectorResult(ok=True, code="ok")],
    )
    breaker = _Breaker(blocked_provider="a")
    router = _router(primary, fallback, breaker=breaker)

    routed = router.execute(_request(), require_write=True)

    assert routed.provider == "b"
    assert routed.fallback_depth == 1
    assert primary.execute_calls == 0
    assert fallback.execute_calls == 1
    assert breaker.failures == []


def test_idempotency_key_allows_failover_after_exception() -> None:
    primary = _ScriptedConnector(provider="a", outcomes=[ConnectionError("lost")])
    fallback = _ScriptedConnector(
        provider="b",
        outcomes=[ConnectorResult(ok=True, code="ok")],
    )
    router = _router(primary, fallback)

    routed = router.execute(
        _request(idempotency_key="idem-1"),
        require_write=True,
    )

    assert routed.provider == "b"
    assert primary.execute_calls == 1
    assert fallback.execute_calls == 1


def test_process_control_exceptions_are_never_swallowed_or_failed_over() -> None:
    primary = _ScriptedConnector(provider="a", outcomes=[KeyboardInterrupt()])
    fallback = _ScriptedConnector(
        provider="b",
        outcomes=[ConnectorResult(ok=True, code="ok")],
    )
    router = _router(primary, fallback)

    with pytest.raises(KeyboardInterrupt):
        router.execute(_request(idempotency_key="idem"), require_write=True)

    assert fallback.execute_calls == 0


def test_control_plane_recording_failure_cannot_duplicate_successful_write() -> None:
    primary = _ScriptedConnector(
        provider="a",
        outcomes=[ConnectorResult(ok=True, code="ok")],
    )
    fallback = _ScriptedConnector(
        provider="b",
        outcomes=[ConnectorResult(ok=True, code="duplicate")],
    )
    breaker = _Breaker(fail_success_record=True)
    health = _HealthMonitor(fail_record=True)
    observability = _FailingObservability()
    router = _router(
        primary,
        fallback,
        breaker=breaker,
        health=health,
        observability=observability,
    )

    routed = router.execute(
        _request(idempotency_key="idem"),
        require_write=True,
    )

    assert routed.result.ok is True
    assert routed.provider == "a"
    assert primary.execute_calls == 1
    assert fallback.execute_calls == 0
    assert observability.calls == 1


def test_control_plane_failure_does_not_replace_explicit_connector_error() -> None:
    result = ConnectorResult(ok=False, code="validation_error", message="bad")
    primary = _ScriptedConnector(provider="a", outcomes=[result])
    breaker = _Breaker(fail_failure_record=True)
    health = _HealthMonitor(fail_record=True)
    router = _router(primary, breaker=breaker, health=health)

    routed = router.execute(_request(), require_write=False)

    assert routed.result is result
    assert breaker.failures == [("a", "validation_error")]


def test_sleep_failure_does_not_become_connector_failure() -> None:
    primary = _ScriptedConnector(
        provider="a",
        outcomes=[
            ConnectorResult(ok=False, code="timeout"),
            ConnectorResult(ok=True, code="ok"),
        ],
    )

    def broken_sleep(classification) -> None:
        raise RuntimeError("sleep unavailable")

    router = _router(primary, sleep_fn=broken_sleep, max_attempts=2)
    routed = router.execute(_request(), require_write=False)

    assert routed.result.ok is True
    assert primary.execute_calls == 2


def test_last_route_exception_wins_over_older_result_error() -> None:
    primary = _ScriptedConnector(
        provider="a",
        outcomes=[ConnectorResult(ok=False, code="timeout")],
    )
    fallback = _ScriptedConnector(provider="b", outcomes=[ConnectionError("last")])
    router = _router(primary, fallback)

    with pytest.raises(ConnectionError, match="last"):
        router.execute(_request(idempotency_key="idem"), require_write=True)


def test_last_route_result_wins_over_older_exception() -> None:
    primary = _ScriptedConnector(provider="a", outcomes=[ConnectionError("first")])
    final = ConnectorResult(ok=False, code="validation_error")
    fallback = _ScriptedConnector(provider="b", outcomes=[final])
    router = _router(primary, fallback)

    routed = router.execute(
        _request(idempotency_key="idem"),
        require_write=True,
    )

    assert routed.result is final
    assert routed.provider == "b"


def test_verify_failover_remains_available() -> None:
    primary = _ScriptedConnector(provider="a", outcomes=[ConnectionError("verify lost")])
    fallback = _ScriptedConnector(
        provider="b",
        outcomes=[ConnectorResult(ok=True, code="verified")],
    )
    router = _router(primary, fallback)
    request = ConnectorVerificationRequest(
        tenant_id="tenant-a",
        connector_id="payments",
        operation="charge",
    )

    routed = router.verify(request)

    assert routed.provider == "b"
    assert primary.verify_calls == 1
    assert fallback.verify_calls == 1


def test_no_candidates_fails_explicitly() -> None:
    router = ConnectorFailoverRouter(
        registry=ConnectorRegistry(),
        retry_policy=_retry_policy(),
        timeout_policy=_DirectTimeoutPolicy(),
    )
    with pytest.raises(RuntimeError, match="no connector candidates"):
        router.execute(_request())


def test_unhealthy_routes_are_skipped_and_report_no_healthy_route() -> None:
    primary = _ScriptedConnector(
        provider="a",
        outcomes=[ConnectorResult(ok=True, code="unexpected")],
    )
    health = _HealthMonitor(unhealthy_provider="a")
    router = _router(primary, health=health)

    with pytest.raises(RuntimeError, match="no healthy connector route"):
        router.execute(_request())

    assert primary.execute_calls == 0


def test_retryable_exception_retries_same_safe_route() -> None:
    primary = _ScriptedConnector(
        provider="a",
        outcomes=[ConnectionError("temporary"), ConnectorResult(ok=True, code="ok")],
    )
    router = _router(primary, max_attempts=2, sleep_fn=lambda classification: None)

    routed = router.execute(_request(), require_write=False)

    assert routed.result.ok is True
    assert primary.execute_calls == 2
    assert [attempt.outcome for attempt in routed.attempts] == ["exception", "success"]


def test_last_result_is_returned_when_remaining_routes_are_blocked() -> None:
    primary_result = ConnectorResult(ok=False, code="timeout")
    primary = _ScriptedConnector(provider="a", outcomes=[primary_result])
    fallback = _ScriptedConnector(
        provider="b",
        outcomes=[ConnectorResult(ok=True, code="unexpected")],
    )
    breaker = _Breaker(blocked_provider="b")
    router = _router(primary, fallback, breaker=breaker)

    routed = router.execute(_request(), require_write=False)

    assert routed.result is primary_result
    assert routed.provider == "a"
    assert fallback.execute_calls == 0


def test_explicit_version_safety_requires_same_version_before_first_write_call() -> None:
    v1 = _ScriptedConnector(
        provider="a",
        version="v1",
        outcomes=[ConnectorResult(ok=True, code="ok")],
    )
    v2 = _ScriptedConnector(
        provider="b",
        version="v2",
        outcomes=[ConnectorResult(ok=True, code="ok")],
    )
    entries = _registry(v1, v2).list_entries(connector_id="payments")
    router = _router(v1)
    context = __import__(
        "connectors.platform.connector_retry_policy",
        fromlist=["RetryContext"],
    ).RetryContext(
        operation="charge",
        write=True,
        dry_run=False,
        idempotency_key_present=False,
    )

    assert (
        router._route_safe_for_request(
            entry=entries[0],
            route_index=1,
            requested_version="v1",
            retry_context=context,
            prior_call_attempted=False,
        )
        is True
    )
    assert (
        router._route_safe_for_request(
            entry=entries[1],
            route_index=1,
            requested_version="v1",
            retry_context=context,
            prior_call_attempted=False,
        )
        is False
    )


def test_router_rejects_broken_retry_policy_with_zero_attempts() -> None:
    primary = _ScriptedConnector(
        provider="a",
        outcomes=[ConnectorResult(ok=True, code="unexpected")],
    )

    class _BrokenRetryPolicy:
        def resolve_rule(self, *, operation: str):
            return SimpleNamespace(max_attempts=0)

        def maybe_sleep(self, classification) -> None:
            raise AssertionError("sleep must not be called")

    router = ConnectorFailoverRouter(
        registry=_registry(primary),
        retry_policy=_BrokenRetryPolicy(),  # type: ignore[arg-type]
        timeout_policy=_DirectTimeoutPolicy(),
    )

    with pytest.raises(ValueError, match="max_attempts"):
        router.execute(_request())
    assert primary.execute_calls == 0
