from __future__ import annotations

from dataclasses import dataclass

import pytest

from connectors.platform.connector_capability_contract import ConnectorCapabilityDescriptor, ConnectorMaturity
from connectors.platform.connector_circuit_breaker import BreakerState, CircuitBreakerRule, ConnectorCircuitBreaker
from connectors.platform.connector_contract import ConnectorRequest, ConnectorVerificationRequest
from connectors.platform.connector_failover_router import ConnectorFailoverRouter
from connectors.platform.connector_health_monitor import ConnectorHealthMonitor, ConnectorHealthSample
from connectors.platform.connector_observability import ConnectorObservability
from connectors.platform.connector_registry import ConnectorRegistry, ConnectorRegistryEntry
from connectors.platform.connector_retry_policy import ConnectorRetryPolicy
from connectors.platform.connector_version_registry import ConnectorVersionRecord, ConnectorVersionRegistry
from interfaces.common.connector_health import ConnectorHealth
from interfaces.common.connector_result import ConnectorResult


@dataclass
class _DummyConnector:
    connector_id: str
    provider: str
    version: str
    result_code: str = 'ok'
    healthy: bool = True
    raise_timeout: bool = False

    def capabilities(self) -> ConnectorCapabilityDescriptor:
        return ConnectorCapabilityDescriptor(
            connector_id=self.connector_id,
            provider=self.provider,
            version=self.version,
            maturity=ConnectorMaturity.REAL,
            supports_read=True,
            supports_write=True,
            supports_verify=True,
            operation_names=('sync_customer',),
        )

    def health(self) -> ConnectorHealth:
        return ConnectorHealth(connector_name=self.connector_id, healthy=self.healthy, reason='ok' if self.healthy else 'down')

    def execute(self, request: ConnectorRequest) -> ConnectorResult:
        if self.raise_timeout:
            raise TimeoutError('slow upstream')
        return ConnectorResult(ok=self.result_code == 'ok', code=self.result_code, message=self.result_code, payload={'provider': self.provider})

    def verify(self, request: ConnectorVerificationRequest) -> ConnectorResult:
        return ConnectorResult(ok=True, code='verified', message='verified', payload={})

    def build_snapshot(self, *, tenant_id: str):
        return {'tenant_id': tenant_id}


def _registry(*entries: ConnectorRegistryEntry) -> ConnectorRegistry:
    registry = ConnectorRegistry()
    registry.register_many(entries)
    return registry


def test_circuit_breaker_opens_and_half_open_recovers(tmp_path) -> None:
    breaker = ConnectorCircuitBreaker(
        default_rule=CircuitBreakerRule(connector_id='*', failure_threshold=2, recovery_timeout_seconds=0.01),
        state_path=tmp_path / 'breaker.json',
    )
    breaker.record_failure(connector_id='crm', provider='hubspot', version='v1', operation='sync_customer', reason='timeout')
    snap = breaker.record_failure(connector_id='crm', provider='hubspot', version='v1', operation='sync_customer', reason='timeout')
    assert snap.state == BreakerState.OPEN.value
    permit = breaker.allow_call(connector_id='crm', provider='hubspot', version='v1', operation='sync_customer')
    assert permit.allowed is False
    import time
    time.sleep(0.02)
    permit = breaker.allow_call(connector_id='crm', provider='hubspot', version='v1', operation='sync_customer')
    assert permit.allowed is True
    assert permit.state == BreakerState.HALF_OPEN.value
    snap = breaker.record_success(connector_id='crm', provider='hubspot', version='v1', operation='sync_customer')
    assert snap.state == BreakerState.CLOSED.value


def test_failover_router_skips_blocked_route_and_uses_healthy_backup(tmp_path) -> None:
    primary = _DummyConnector('crm', 'hubspot', 'v1', result_code='timeout')
    backup = _DummyConnector('crm', 'salesforce', 'v1', result_code='ok')
    registry = _registry(
        ConnectorRegistryEntry('crm', 'hubspot', 'v1', primary, rank=10),
        ConnectorRegistryEntry('crm', 'salesforce', 'v1', backup, rank=20),
    )
    versions = ConnectorVersionRegistry(registry=registry)
    versions.register(ConnectorVersionRecord('crm', 'v1'), make_default=True)
    health = ConnectorHealthMonitor(registry=registry, history_path=tmp_path / 'health.json')
    breaker = ConnectorCircuitBreaker(default_rule=CircuitBreakerRule(connector_id='*', failure_threshold=1, recovery_timeout_seconds=60), state_path=tmp_path / 'breaker.json')
    breaker.force_open(connector_id='crm', provider='hubspot', version='v1', operation='sync_customer', reason='forced_open')
    router = ConnectorFailoverRouter(registry=registry, version_registry=versions, health_monitor=health, circuit_breaker=breaker, observability=ConnectorObservability())

    result = router.execute(ConnectorRequest(tenant_id='tenant-a', connector_id='crm', operation='sync_customer', idempotency_key='idem-1'), require_write=True)

    assert result.result.ok is True
    assert result.provider == 'salesforce'
    assert any(item.outcome == 'blocked' for item in result.attempts)


def test_failover_router_does_not_failover_non_idempotent_write(tmp_path) -> None:
    primary = _DummyConnector('crm', 'hubspot', 'v1', result_code='connector_unavailable')
    backup = _DummyConnector('crm', 'salesforce', 'v1', result_code='ok')
    registry = _registry(
        ConnectorRegistryEntry('crm', 'hubspot', 'v1', primary, rank=10),
        ConnectorRegistryEntry('crm', 'salesforce', 'v1', backup, rank=20),
    )
    health = ConnectorHealthMonitor(registry=registry, history_path=tmp_path / 'health.json')
    router = ConnectorFailoverRouter(registry=registry, health_monitor=health, retry_policy=ConnectorRetryPolicy())

    result = router.execute(ConnectorRequest(tenant_id='tenant-a', connector_id='crm', operation='sync_customer'), require_write=True)

    assert result.result.ok is False
    assert result.provider == 'hubspot'
    assert result.fallback_depth == 0
    assert not any(item.provider == 'salesforce' and item.attempt > 0 for item in result.attempts)


def test_health_monitor_memory_mode_does_not_require_path() -> None:
    registry = _registry(ConnectorRegistryEntry('crm', 'hubspot', 'v1', _DummyConnector('crm', 'hubspot', 'v1')))
    monitor = ConnectorHealthMonitor(registry=registry, history_path=None)
    monitor.record(ConnectorHealthSample('crm', 'hubspot', 'v1', True, 'ok', metadata={'latency_ms': 12.5}))
    verdict = monitor.verdict(connector_id='crm', version='v1', provider='hubspot', probe_if_missing=False)
    assert verdict.healthy is True
    assert verdict.latency_ms == 12.5


def test_observability_records_failover_metric() -> None:
    obs = ConnectorObservability()
    obs.record(
        __import__('connectors.platform.connector_observability', fromlist=['ConnectorExecutionEvent']).ConnectorExecutionEvent(
            tenant_id='tenant-a', connector_id='crm', provider='hubspot', version='v1', operation='execute:sync_customer', status='blocked', fallback_depth=1
        )
    )
    assert obs.metrics.counters['connector.calls.total'] == 1
    assert obs.metrics.counters['connector.failover.total'] == 1
    assert obs.metrics.counters['connector.blocked.total'] == 1
