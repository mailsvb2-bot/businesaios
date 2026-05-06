from __future__ import annotations

import time
from datetime import timedelta

import pytest

from connectors.platform.connector_capability_contract import (
    ConnectorCapabilityDescriptor,
    ConnectorMaturity,
)
from connectors.platform.connector_contract import (
    BaseConnectorPlatformAdapter,
    ConnectorRequest,
    ConnectorVerificationRequest,
)
from connectors.platform.connector_fallback_router import ConnectorFallbackRouter
from connectors.platform.connector_health_monitor import ConnectorHealthMonitor, ConnectorHealthSample, utc_now
from connectors.platform.connector_observability import ConnectorExecutionEvent, ConnectorObservability
from connectors.platform.connector_quota_guard import ConnectorQuotaGuard
from connectors.platform.connector_registry import ConnectorRegistry, ConnectorRegistryEntry
from connectors.platform.connector_sandbox import ConnectorSandbox, ConnectorSandboxPolicy
from connectors.platform.connector_secret_binding import ConnectorSecretBinding, ConnectorSecretBindingResolver
from connectors.platform.connector_timeout_policy import ConnectorTimeoutPolicy, ConnectorTimeoutRule
from connectors.platform.connector_version_registry import ConnectorVersionRecord, ConnectorVersionRegistry
from interfaces.common.base_connector import BaseConnector
from interfaces.common.connector_capabilities import ConnectorCapabilities
from interfaces.common.connector_health import ConnectorHealth
from interfaces.common.connector_maturity import ConnectorMaturity as LegacyConnectorMaturity
from interfaces.common.connector_result import ConnectorResult
from security.connector_secret_scope import ConnectorSecretScope, SecretScopeBinding
from tenancy.tenant_audit_scope import TenantAuditScope
from tenancy.tenant_billing_scope import TenantBillingScope
from tenancy.tenant_connector_scope import TenantConnectorScope
from tenancy.tenant_feature_flags import TenantFeatureFlags
from tenancy.tenant_memory_scope import TenantMemoryScope
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore, TenantPolicyBundle
from tenancy.tenant_quota_guard import QuotaDimension, TenantQuotaGuard
from tenancy.tenant_runtime_limits import TenantRuntimeLimits


class DummyBaseConnector(BaseConnector):
    connector_name = 'dummy_base'

    def __init__(self, *, healthy: bool = True) -> None:
        super().__init__()
        from interfaces.common.auth_session import AuthSession
        object.__setattr__(self, 'session', AuthSession(configured=True))
        self._healthy = healthy

    def connector_maturity(self):
        return LegacyConnectorMaturity.REAL

    def connector_capabilities(self):
        return ConnectorCapabilities(
            read=True,
            write=True,
            verify=True,
            dry_run=True,
            idempotent=True,
            requires_human_approval=False,
            evidence_fields=('external_id',),
            metadata={'maturity': 'real'},
        )

    def capabilities(self):
        base = super().capabilities()
        base['operation_names'] = ['sync_customer', 'verify_customer']
        return base

    def health(self):
        return ConnectorHealth(connector_name=self.connector_name, healthy=self._healthy, reason='ok')

    def _execute_configured(self, operation, payload, *, idempotency_key=None, dry_run=False):
        return ConnectorResult(ok=True, code='ok', message='done', payload={'operation': operation, 'dry_run': dry_run})

    def _verify_configured(self, operation, payload, result_payload=None):
        return ConnectorResult(ok=True, code='verified', message='verified', payload={'operation': operation})


class DummyPlatformConnector:
    def __init__(self, *, connector_id: str, provider: str, version: str, healthy: bool = True, rank: int = 100):
        self.connector_id = connector_id
        self.provider = provider
        self.version = version
        self.healthy = healthy
        self.rank = rank

    def capabilities(self):
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

    def health(self):
        return ConnectorHealth(connector_name=self.connector_id, healthy=self.healthy, reason='ok' if self.healthy else 'down')

    def execute(self, request):
        return ConnectorResult(ok=True, code='ok', payload={'connector_id': self.connector_id, 'operation': request.operation})

    def verify(self, request):
        return ConnectorResult(ok=True, code='verified', payload={'connector_id': self.connector_id, 'operation': request.operation})

    def build_snapshot(self, *, tenant_id: str):
        return {'tenant_id': tenant_id, 'connector_id': self.connector_id, 'version': self.version}


def test_base_connector_adapter_executes_and_verifies() -> None:
    adapter = BaseConnectorPlatformAdapter(
        connector_id='crm_sync',
        provider='hubspot',
        version='v1',
        connector=DummyBaseConnector(),
    )
    result = adapter.execute(
        ConnectorRequest(tenant_id='tenant-a', connector_id='crm_sync', operation='sync_customer', payload={'id': '1'})
    )
    assert result.ok is True
    verify = adapter.verify(
        ConnectorVerificationRequest(
            tenant_id='tenant-a',
            connector_id='crm_sync',
            operation='sync_customer',
            request_payload={'id': '1'},
            result_payload={'external_id': 'x'},
        )
    )
    assert verify.ok is True
    snapshot = adapter.build_snapshot(tenant_id='tenant-a')
    assert snapshot['capabilities']['supports_verify'] is True


def test_registry_and_version_registry_prevent_silent_breakage() -> None:
    registry = ConnectorRegistry()
    entry = ConnectorRegistryEntry(
        connector_id='crm_sync',
        provider='hubspot',
        version='v1',
        connector=DummyPlatformConnector(connector_id='crm_sync', provider='hubspot', version='v1'),
    )
    registry.register(entry)
    with pytest.raises(KeyError):
        registry.register(entry)
    versions = ConnectorVersionRegistry(registry=registry)
    versions.register(ConnectorVersionRecord(connector_id='crm_sync', version='v1'), make_default=True)
    versions.register(
        ConnectorVersionRecord(
            connector_id='crm_sync',
            version='v2',
            deprecated=True,
            replacement_version='v1',
        )
    )
    assert versions.resolve(connector_id='crm_sync') == 'v1'
    with pytest.raises(ValueError):
        versions.resolve(connector_id='crm_sync', requested_version='v2', strict=True)
    assert versions.resolve(connector_id='crm_sync', requested_version='v2', strict=False) == 'v1'


def test_health_monitor_detects_stale_and_consecutive_failures() -> None:
    registry = ConnectorRegistry()
    connector = DummyPlatformConnector(connector_id='crm_sync', provider='hubspot', version='v1', healthy=False)
    registry.register(
        ConnectorRegistryEntry(connector_id='crm_sync', provider='hubspot', version='v1', connector=connector)
    )
    monitor = ConnectorHealthMonitor(registry=registry, consecutive_failure_threshold=2, stale_after_seconds=1)
    monitor.record(ConnectorHealthSample('crm_sync', 'hubspot', 'v1', False, 'down'))
    verdict = monitor.verdict(connector_id='crm_sync', version='v1', probe_if_missing=False)
    assert verdict.healthy is False
    monitor.record(ConnectorHealthSample('crm_sync', 'hubspot', 'v1', False, 'down'))
    verdict = monitor.verdict(connector_id='crm_sync', version='v1', probe_if_missing=False)
    assert verdict.reason == 'consecutive_failures'
    stale_sample = ConnectorHealthSample(
        'crm_sync',
        'hubspot',
        'v1',
        True,
        'ok',
        recorded_at=utc_now() - timedelta(seconds=10),
    )
    monitor.record(stale_sample)
    verdict = monitor.verdict(connector_id='crm_sync', version='v1', probe_if_missing=False)
    assert verdict.reason == 'stale_health_sample'


def test_fallback_router_prefers_requested_provider_but_can_fall_back_cross_provider() -> None:
    registry = ConnectorRegistry()
    registry.register(
        ConnectorRegistryEntry(
            connector_id='crm_sync',
            provider='hubspot',
            version='v1',
            connector=DummyPlatformConnector(connector_id='crm_sync', provider='hubspot', version='v1', healthy=False),
            rank=10,
        )
    )
    registry.register(
        ConnectorRegistryEntry(
            connector_id='crm_sync',
            provider='salesforce',
            version='v2',
            connector=DummyPlatformConnector(connector_id='crm_sync', provider='salesforce', version='v2', healthy=True),
            rank=20,
        )
    )
    health = ConnectorHealthMonitor(registry=registry)
    health.probe(connector_id='crm_sync', version='v1')
    health.probe(connector_id='crm_sync', version='v2')
    router = ConnectorFallbackRouter(registry=registry, health_monitor=health)
    route = router.resolve(
        connector_id='crm_sync',
        operation='sync_customer',
        preferred_provider='hubspot',
        require_write=True,
        require_verify=True,
    )
    assert route.provider == 'salesforce'
    assert route.fallback_depth == 1


def test_timeout_policy_enforces_timeout() -> None:
    policy = ConnectorTimeoutPolicy(default_timeout_seconds=0.01, max_timeout_seconds=0.05)
    with pytest.raises(TimeoutError):
        policy.run(lambda: time.sleep(0.1), operation='sync_customer')
    decision = policy.resolve(operation='sync_customer', requested_timeout=1.0)
    assert decision.clamped is True
    assert decision.timeout_seconds == 0.05


def test_secret_binding_checks_scope() -> None:
    scope = ConnectorSecretScope(
        bindings=(
            SecretScopeBinding(
                tenant_id='tenant-a',
                connector_id='crm_sync',
                allowed_secret_names=('hubspot_api_key',),
            ),
        )
    )
    resolver = ConnectorSecretBindingResolver(connector_scope=scope)
    resolver.register(
        ConnectorSecretBinding(
            tenant_id='tenant-a',
            connector_id='crm_sync',
            secret_name='hubspot_api_key',
            alias='api_key',
        )
    )
    binding = resolver.resolve(tenant_id='tenant-a', connector_id='crm_sync', secret_name='api_key')
    assert binding.secret_name == 'hubspot_api_key'


def test_observability_records_metrics_and_audit() -> None:
    observability = ConnectorObservability()
    observability.record(
        ConnectorExecutionEvent(
            tenant_id='tenant-a',
            connector_id='crm_sync',
            version='v1',
            operation='sync_customer',
            status='success',
            duration_ms=12.5,
            fallback_depth=1,
            payload={'ok': True},
        )
    )
    assert observability.metrics.counters['connector.calls.total'] == 1
    latest = observability.audit_log.latest()
    assert latest is not None
    assert latest['kind'] == 'connector_execution'


def test_sandbox_allows_dry_run_but_blocks_mutation_without_policy() -> None:
    sandbox = ConnectorSandbox(
        policies=(
            ConnectorSandboxPolicy(
                connector_id='crm_sync',
                allow_network=True,
                allow_mutations=False,
                allowed_operations=('sync_customer',),
            ),
        )
    )
    assert sandbox.is_allowed(connector_id='crm_sync', operation='sync_customer', dry_run=True) is True
    assert sandbox.is_allowed(connector_id='crm_sync', operation='sync_customer', dry_run=False) is False


def test_connector_quota_guard_enforces_local_limit() -> None:
    policy_store = InMemoryTenantPolicyStore()
    policy_store.save(
        TenantPolicyBundle(
            tenant_id='tenant-a',
            feature_flags=TenantFeatureFlags(tenant_id='tenant-a'),
            runtime_limits=TenantRuntimeLimits(tenant_id='tenant-a'),
            memory_scope=TenantMemoryScope(tenant_id='tenant-a'),
            connector_scope=TenantConnectorScope(tenant_id='tenant-a', allowed_connectors=('crm_sync',)),
            audit_scope=TenantAuditScope(tenant_id='tenant-a'),
            billing_scope=TenantBillingScope(tenant_id='tenant-a'),
            quotas={QuotaDimension.CONNECTOR_CALLS_PER_HOUR.value: 10},
        )
    )
    quota_guard = ConnectorQuotaGuard(
        quota_guard=TenantQuotaGuard(policy_store=policy_store),
        per_connector_hour_limit=2,
    )
    first = quota_guard.consume(tenant_id='tenant-a', connector_id='crm_sync', requested_calls=1)
    second = quota_guard.consume(tenant_id='tenant-a', connector_id='crm_sync', requested_calls=1)
    third = quota_guard.check(tenant_id='tenant-a', connector_id='crm_sync', requested_calls=1)
    assert first.allowed is True
    assert second.allowed is True
    assert third.allowed is False
    assert third.reason == 'connector_local_quota_exceeded'


def test_timeout_policy_rules_resolve_verify_and_dry_run() -> None:
    policy = ConnectorTimeoutPolicy(
        default_timeout_seconds=10,
        max_timeout_seconds=20,
        rules=(ConnectorTimeoutRule('sync_customer', 5, verify_timeout_seconds=2, dry_run_timeout_seconds=1),),
    )
    assert policy.resolve(operation='sync_customer').timeout_seconds == 5
    assert policy.resolve(operation='sync_customer', verify=True).timeout_seconds == 2
    assert policy.resolve(operation='sync_customer', dry_run=True).timeout_seconds == 1



def test_registry_supports_same_version_across_multiple_providers() -> None:
    registry = ConnectorRegistry()
    registry.register(
        ConnectorRegistryEntry(
            connector_id='crm',
            provider='hubspot',
            version='v1',
            connector=DummyPlatformConnector(connector_id='crm', provider='hubspot', version='v1'),
            rank=10,
        )
    )
    registry.register(
        ConnectorRegistryEntry(
            connector_id='crm',
            provider='pipedrive',
            version='v1',
            connector=DummyPlatformConnector(connector_id='crm', provider='pipedrive', version='v1'),
            rank=20,
        )
    )

    assert registry.providers_for(connector_id='crm') == ('hubspot', 'pipedrive')
    assert registry.get_entry(connector_id='crm', version='v1', provider='hubspot').provider == 'hubspot'
    assert registry.get_entry(connector_id='crm', version='v1', provider='pipedrive').provider == 'pipedrive'



def test_health_monitor_keeps_provider_histories_separate() -> None:
    registry = ConnectorRegistry()
    hubspot = DummyPlatformConnector(connector_id='crm', provider='hubspot', version='v1')
    pipedrive = DummyPlatformConnector(connector_id='crm', provider='pipedrive', version='v1')
    hubspot.healthy = False
    pipedrive.healthy = True
    registry.register(ConnectorRegistryEntry(connector_id='crm', provider='hubspot', version='v1', connector=hubspot, rank=10))
    registry.register(ConnectorRegistryEntry(connector_id='crm', provider='pipedrive', version='v1', connector=pipedrive, rank=20))
    monitor = ConnectorHealthMonitor(registry=registry)

    assert monitor.probe(connector_id='crm', version='v1', provider='hubspot').healthy is False
    assert monitor.probe(connector_id='crm', version='v1', provider='pipedrive').healthy is True
    assert monitor.is_healthy(connector_id='crm', version='v1', provider='hubspot') is False
    assert monitor.is_healthy(connector_id='crm', version='v1', provider='pipedrive') is True



def test_secret_binding_resolves_by_alias_and_secret_name() -> None:
    scope = ConnectorSecretScope(
        bindings=(
            SecretScopeBinding(
                tenant_id='tenant-1',
                connector_id='crm',
                allowed_secret_names=('hubspot-api-key',),
            ),
        )
    )
    resolver = ConnectorSecretBindingResolver(connector_scope=scope)
    binding = ConnectorSecretBinding(
        tenant_id='tenant-1',
        connector_id='crm',
        secret_name='hubspot-api-key',
        alias='primary',
        mode='read',
    )
    resolver.register(binding)

    assert resolver.resolve(tenant_id='tenant-1', connector_id='crm', secret_name='hubspot-api-key') == binding
    assert resolver.resolve(tenant_id='tenant-1', connector_id='crm', secret_name='primary') == binding



def test_quota_guard_remaining_reflects_global_and_local_limits_after_consume() -> None:
    guard = ConnectorQuotaGuard(per_connector_hour_limit=3.0)
    first = guard.consume(tenant_id='tenant-1', connector_id='crm', requested_calls=1.0)
    second = guard.consume(tenant_id='tenant-1', connector_id='crm', requested_calls=1.0)

    assert first.remaining == 2.0
    assert second.remaining == 1.0
