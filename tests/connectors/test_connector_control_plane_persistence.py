from __future__ import annotations

from dataclasses import dataclass

from connectors.platform.connector_capability_contract import ConnectorCapabilityDescriptor, ConnectorMaturity
from connectors.platform.connector_contract import PlatformConnector
from connectors.platform.connector_health_monitor import ConnectorHealthMonitor, connector_health_monitor_path
from connectors.platform.connector_observability import ConnectorExecutionEvent, ConnectorObservability
from connectors.platform.connector_registry import ConnectorRegistry, ConnectorRegistryEntry
from interfaces.common.connector_health import ConnectorHealth
from observability.action_audit_log import FileActionAuditLog


@dataclass(frozen=True)
class _DummyConnector(PlatformConnector):
    connector_id: str = 'ads'
    provider: str = 'dummy'
    version: str = 'v1'

    def capabilities(self) -> ConnectorCapabilityDescriptor:
        return ConnectorCapabilityDescriptor(
            connector_id=self.connector_id,
            provider=self.provider,
            version=self.version,
            operation_names=('launch_campaign',),
            supports_read=True,
            supports_write=True,
            supports_verify=True,
            maturity=ConnectorMaturity.REAL,
        )

    def health(self) -> ConnectorHealth:
        return ConnectorHealth(healthy=True, reason='ok', metadata={'path': 'dummy'})


def test_connector_health_monitor_persists_history(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('BUSINESAIOS_DATA_DIR', str(tmp_path))
    registry = ConnectorRegistry()
    registry.register(ConnectorRegistryEntry(connector_id='ads', provider='dummy', version='v1', connector=_DummyConnector()))
    monitor = ConnectorHealthMonitor(registry=registry)
    sample = monitor.probe(connector_id='ads')
    reloaded = ConnectorHealthMonitor(registry=registry)
    latest = reloaded.latest(connector_id='ads', version='v1', provider='dummy')
    assert latest is not None
    assert latest.reason == sample.reason
    assert connector_health_monitor_path().exists()


def test_connector_observability_uses_durable_audit_log(tmp_path) -> None:
    audit = FileActionAuditLog(path=tmp_path / 'audit.json')
    obs = ConnectorObservability(audit_log=audit)
    obs.record(
        ConnectorExecutionEvent(
            tenant_id='tenant-a',
            connector_id='ads',
            version='v1',
            operation='launch_campaign',
            status='ok',
            trace_id='trace-1',
        )
    )
    reloaded = FileActionAuditLog(path=tmp_path / 'audit.json')
    latest = reloaded.latest()
    assert latest is not None
    assert latest['connector_id'] == 'ads'
