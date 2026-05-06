from __future__ import annotations

from dataclasses import dataclass

import pytest

from connectors.platform.connector_capability_contract import ConnectorCapabilityDescriptor, ConnectorMaturity
from connectors.platform.connector_contract import ConnectorRequest, ConnectorResult, ConnectorVerificationRequest
from connectors.platform.connector_fallback_router import ConnectorFallbackRouter
from connectors.platform.connector_health_monitor import ConnectorHealthMonitor
from connectors.platform.connector_registry import ConnectorRegistry, ConnectorRegistryEntry
from interfaces.common.connector_health import ConnectorHealth


@dataclass
class _DummyConnector:
    connector_id: str
    provider: str
    version: str
    healthy: bool
    supports_write: bool = True
    supports_verify: bool = True

    def capabilities(self) -> ConnectorCapabilityDescriptor:
        return ConnectorCapabilityDescriptor(
            connector_id=self.connector_id,
            provider=self.provider,
            version=self.version,
            maturity=ConnectorMaturity.REAL,
            supports_read=True,
            supports_write=self.supports_write,
            supports_verify=self.supports_verify,
            operation_names=('sync_customer',),
        )

    def health(self) -> ConnectorHealth:
        return ConnectorHealth(connector_name=self.connector_id, healthy=self.healthy, reason='ok' if self.healthy else 'down')

    def execute(self, request: ConnectorRequest) -> ConnectorResult:
        return ConnectorResult(ok=True, status='ok', payload={})

    def verify(self, request: ConnectorVerificationRequest) -> ConnectorResult:
        return ConnectorResult(ok=True, status='verified', payload={})

    def build_snapshot(self, *, tenant_id: str):
        return {'tenant_id': tenant_id}


def test_connector_fallback_router_skips_unhealthy_primary_and_routes_to_healthy_alternative() -> None:
    registry = ConnectorRegistry()
    registry.register(ConnectorRegistryEntry(connector_id='crm_sync', provider='hubspot', version='v1', connector=_DummyConnector('crm_sync', 'hubspot', 'v1', healthy=False), rank=10))
    registry.register(ConnectorRegistryEntry(connector_id='crm_sync', provider='salesforce', version='v2', connector=_DummyConnector('crm_sync', 'salesforce', 'v2', healthy=True), rank=20))

    monitor = ConnectorHealthMonitor(registry=registry)
    monitor.probe(connector_id='crm_sync', version='v1', provider='hubspot')
    monitor.probe(connector_id='crm_sync', version='v2', provider='salesforce')
    router = ConnectorFallbackRouter(registry=registry, health_monitor=monitor)

    route = router.resolve(connector_id='crm_sync', operation='sync_customer', preferred_provider='hubspot', require_write=True, require_verify=True)

    assert route.provider == 'salesforce'
    assert route.reason == 'fallback_healthy_alternative'
    assert route.attempted_versions == ('hubspot:v1', 'salesforce:v2')


def test_connector_fallback_router_rejects_routes_without_required_verify_capability() -> None:
    registry = ConnectorRegistry()
    registry.register(ConnectorRegistryEntry(connector_id='crm_sync', provider='hubspot', version='v1', connector=_DummyConnector('crm_sync', 'hubspot', 'v1', healthy=True, supports_write=False, supports_verify=False), rank=10))
    router = ConnectorFallbackRouter(registry=registry)

    with pytest.raises(RuntimeError, match='no connector candidates'):
        router.resolve(connector_id='crm_sync', operation='sync_customer', require_write=True, require_verify=True)


def test_connector_fallback_router_fails_closed_when_no_candidates_exist() -> None:
    router = ConnectorFallbackRouter(registry=ConnectorRegistry())

    with pytest.raises(RuntimeError, match='no connector candidates'):
        router.resolve(connector_id='missing', operation='sync_customer')
