from __future__ import annotations

import threading
from dataclasses import dataclass

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
        return ConnectorHealth(connector_name=self.connector_id, healthy=True, reason='ok')

    def execute(self, request: ConnectorRequest) -> ConnectorResult:
        return ConnectorResult(ok=self.result_code == 'ok', code=self.result_code, message=self.result_code, payload={'provider': self.provider})

    def verify(self, request: ConnectorVerificationRequest) -> ConnectorResult:
        return ConnectorResult(ok=True, code='verified', message='verified', payload={})

    def build_snapshot(self, *, tenant_id: str):
        return {'tenant_id': tenant_id}


def _registry(*entries: ConnectorRegistryEntry) -> ConnectorRegistry:
    registry = ConnectorRegistry()
    registry.register_many(entries)
    return registry


def test_failover_router_hard_stops_non_idempotent_unsafe_failover(tmp_path) -> None:
    primary = _DummyConnector('crm', 'hubspot', 'v1', result_code='connector_unavailable')
    backup = _DummyConnector('crm', 'salesforce', 'v2', result_code='ok')
    registry = _registry(
        ConnectorRegistryEntry('crm', 'hubspot', 'v1', primary, rank=10),
        ConnectorRegistryEntry('crm', 'salesforce', 'v2', backup, rank=20),
    )
    versions = ConnectorVersionRegistry(registry=registry)
    versions.register(ConnectorVersionRecord('crm', 'v1'), make_default=True)
    versions.register(ConnectorVersionRecord('crm', 'v2'))
    monitor = ConnectorHealthMonitor(registry=registry, history_path=tmp_path / 'health.json')
    router = ConnectorFailoverRouter(
        registry=registry,
        version_registry=versions,
        health_monitor=monitor,
        retry_policy=ConnectorRetryPolicy(),
        observability=ConnectorObservability(),
        allow_replacement_version_failover=True,
    )

    result = router.execute(ConnectorRequest(tenant_id='tenant-a', connector_id='crm', operation='sync_customer'), require_write=True)

    assert result.provider == 'hubspot'
    assert result.result.ok is False
    assert not any(item.provider == 'salesforce' and item.attempt > 0 for item in result.attempts)


def test_connector_health_snapshot_is_thread_safe(tmp_path) -> None:
    registry = _registry(ConnectorRegistryEntry('crm', 'hubspot', 'v1', _DummyConnector('crm', 'hubspot', 'v1'), rank=10))
    monitor = ConnectorHealthMonitor(registry=registry, history_path=tmp_path / 'health.json')

    def writer() -> None:
        for _ in range(50):
            monitor.record(ConnectorHealthSample('crm', 'hubspot', 'v1', True, 'ok'))
            monitor.snapshot()

    threads = [threading.Thread(target=writer) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    snap = monitor.snapshot()
    assert snap['history']
    assert snap['history'][0]['connector_id'] == 'crm'


def test_circuit_breaker_half_open_window_is_enforced(tmp_path) -> None:
    breaker = ConnectorCircuitBreaker(
        default_rule=CircuitBreakerRule(connector_id='*', failure_threshold=1, recovery_timeout_seconds=0.01, half_open_max_calls=1, half_open_window_seconds=0.5),
        state_path=tmp_path / 'breaker.json',
    )
    breaker.record_failure(connector_id='crm', provider='hubspot', version='v1', operation='sync_customer', reason='timeout')
    import time
    time.sleep(0.02)
    first = breaker.allow_call(connector_id='crm', provider='hubspot', version='v1', operation='sync_customer')
    second = breaker.allow_call(connector_id='crm', provider='hubspot', version='v1', operation='sync_customer')
    assert first.allowed is True
    assert first.state == BreakerState.HALF_OPEN.value
    assert second.allowed is False
    assert second.reason == 'half_open_budget_exhausted'


def test_connector_observability_records_route_and_attempt_labels() -> None:
    obs = ConnectorObservability()
    obs.record(
        __import__('connectors.platform.connector_observability', fromlist=['ConnectorExecutionEvent']).ConnectorExecutionEvent(
            tenant_id='tenant-a',
            connector_id='crm',
            provider='hubspot',
            version='v1',
            operation='execute:sync_customer',
            status='blocked',
            fallback_depth=1,
            route_index=1,
            attempt=2,
            breaker_state='open',
        )
    )
    assert obs.metrics.gauges['connector.route_index'] == 1.0
    assert obs.metrics.gauges['connector.attempt'] == 2.0
