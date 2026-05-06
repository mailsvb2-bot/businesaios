from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from connectors.platform.connector_capability_contract import ConnectorCapabilityDescriptor, ConnectorMaturity
from connectors.platform.connector_contract import ConnectorRequest, ConnectorResult, ConnectorVerificationRequest
from connectors.platform.connector_health_monitor import ConnectorHealthMonitor, ConnectorHealthSample, utc_now
from connectors.platform.connector_registry import ConnectorRegistry, ConnectorRegistryEntry
from interfaces.common.connector_health import ConnectorHealth


@dataclass
class _HealthConnector:
    connector_id: str
    provider: str
    version: str
    healthy: bool = True
    raise_error: bool = False

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
        if self.raise_error:
            raise RuntimeError('probe blew up')
        return ConnectorHealth(connector_name=self.connector_id, healthy=self.healthy, reason='ok' if self.healthy else 'down')

    def execute(self, request: ConnectorRequest) -> ConnectorResult:
        return ConnectorResult(ok=True, status='ok', payload={})

    def verify(self, request: ConnectorVerificationRequest) -> ConnectorResult:
        return ConnectorResult(ok=True, status='verified', payload={})

    def build_snapshot(self, *, tenant_id: str):
        return {'tenant_id': tenant_id}


def test_connector_health_monitor_marks_stale_samples_unhealthy() -> None:
    registry = ConnectorRegistry()
    registry.register(ConnectorRegistryEntry(connector_id='crm_sync', provider='hubspot', version='v1', connector=_HealthConnector('crm_sync', 'hubspot', 'v1')))
    monitor = ConnectorHealthMonitor(registry=registry, stale_after_seconds=1)
    monitor.record(ConnectorHealthSample('crm_sync', 'hubspot', 'v1', True, 'ok', recorded_at=utc_now() - timedelta(seconds=5)))

    verdict = monitor.verdict(connector_id='crm_sync', version='v1', provider='hubspot', probe_if_missing=False)

    assert verdict.healthy is False
    assert verdict.reason == 'stale_health_sample'


def test_connector_health_monitor_reports_degraded_connectors() -> None:
    registry = ConnectorRegistry()
    registry.register(ConnectorRegistryEntry(connector_id='crm_sync', provider='hubspot', version='v1', connector=_HealthConnector('crm_sync', 'hubspot', 'v1', healthy=False)))
    monitor = ConnectorHealthMonitor(registry=registry)
    monitor.record(ConnectorHealthSample('crm_sync', 'hubspot', 'v1', False, 'timeout'))
    monitor.record(ConnectorHealthSample('crm_sync', 'hubspot', 'v1', False, 'timeout'))

    degraded = monitor.degraded_connectors()

    assert len(degraded) == 1
    assert degraded[0]['connector_id'] == 'crm_sync'
    assert degraded[0]['reason'] == 'consecutive_failures'


def test_connector_health_monitor_converts_probe_exceptions_into_unhealthy_sample() -> None:
    registry = ConnectorRegistry()
    registry.register(ConnectorRegistryEntry(connector_id='crm_sync', provider='hubspot', version='v1', connector=_HealthConnector('crm_sync', 'hubspot', 'v1', raise_error=True)))
    monitor = ConnectorHealthMonitor(registry=registry)

    sample = monitor.probe(connector_id='crm_sync', version='v1', provider='hubspot')

    assert sample.healthy is False
    assert sample.reason == 'health_probe_exception'
    verdict = monitor.verdict(connector_id='crm_sync', version='v1', provider='hubspot', probe_if_missing=False)
    assert verdict.healthy is False
