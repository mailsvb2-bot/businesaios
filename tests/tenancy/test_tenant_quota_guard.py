from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from connectors.platform.connector_quota_guard import ConnectorQuotaGuard
from tenancy.tenant_audit_scope import TenantAuditScope
from tenancy.tenant_billing_scope import TenantBillingScope
from tenancy.tenant_connector_scope import TenantConnectorScope
from tenancy.tenant_feature_flags import TenantFeatureFlags
from tenancy.tenant_memory_scope import TenantMemoryScope
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore, TenantPolicyBundle
from tenancy.tenant_quota_counter_store import (
    InMemoryTenantQuotaCounterStore,
    PersistentTenantQuotaCounterStore,
    TenantQuotaCounterState,
)
from tenancy.tenant_quota_guard import TenantQuotaGuard
from tenancy.tenant_runtime_limits import TenantRuntimeLimits


def _bundle(tenant_id: str, quotas: dict[str, float]) -> TenantPolicyBundle:
    return TenantPolicyBundle(
        tenant_id=tenant_id,
        feature_flags=TenantFeatureFlags(tenant_id=tenant_id),
        runtime_limits=TenantRuntimeLimits(tenant_id=tenant_id),
        memory_scope=TenantMemoryScope(tenant_id=tenant_id),
        connector_scope=TenantConnectorScope(tenant_id=tenant_id, require_explicit_allowlist=False),
        audit_scope=TenantAuditScope(tenant_id=tenant_id),
        billing_scope=TenantBillingScope(tenant_id=tenant_id),
        quotas=quotas,
    )


def test_tenant_quota_guard_enforces_limits_per_tenant() -> None:
    store = InMemoryTenantPolicyStore()
    store.save(_bundle('tenant-a', {'actions_per_hour': 2}))
    store.save(_bundle('tenant-b', {'actions_per_hour': 2}))
    guard = TenantQuotaGuard(policy_store=store)

    first = guard.consume(tenant_id='tenant-a', dimension='actions_per_hour')
    second = guard.consume(tenant_id='tenant-a', dimension='actions_per_hour')
    blocked = guard.check(tenant_id='tenant-a', dimension='actions_per_hour')
    other_tenant = guard.check(tenant_id='tenant-b', dimension='actions_per_hour')

    assert first.allowed is True
    assert second.used == 2.0
    assert blocked.allowed is False
    assert blocked.remaining == 0.0
    assert other_tenant.allowed is True
    assert guard.snapshot(tenant_id='tenant-b')['actions_per_hour'] == 0.0


def test_tenant_quota_guard_reset_clears_usage() -> None:
    store = InMemoryTenantPolicyStore()
    store.save(_bundle('tenant-a', {'actions_per_day': 1}))
    guard = TenantQuotaGuard(policy_store=store)

    guard.consume(tenant_id='tenant-a', dimension='actions_per_day')
    assert guard.check(tenant_id='tenant-a', dimension='actions_per_day').allowed is False

    guard.reset(tenant_id='tenant-a', dimension='actions_per_day')

    assert guard.check(tenant_id='tenant-a', dimension='actions_per_day').allowed is True


def test_tenant_quota_guard_unconfigured_dimension_is_fail_open_but_tracked_separately() -> None:
    store = InMemoryTenantPolicyStore()
    store.save(_bundle('tenant-a', {'actions_per_hour': 1}))
    guard = TenantQuotaGuard(policy_store=store)

    verdict = guard.consume(tenant_id='tenant-a', dimension='custom_metric')

    assert verdict.allowed is True
    assert verdict.limit is None
    assert guard.snapshot(tenant_id='tenant-a')['custom_metric'] == 1.0

def test_tenant_quota_guard_persists_usage_across_restart(tmp_path) -> None:
    policies = InMemoryTenantPolicyStore()
    policies.save(_bundle('tenant-a', {'connector_calls_per_hour': 2}))
    path = tmp_path / 'quota-counters.json'

    first = TenantQuotaGuard(
        policy_store=policies,
        counter_store=PersistentTenantQuotaCounterStore(path),
    )
    first.consume(tenant_id='tenant-a', dimension='connector_calls_per_hour')
    assert first.check(tenant_id='tenant-a', dimension='connector_calls_per_hour').remaining == 1.0

    restarted = TenantQuotaGuard(
        policy_store=policies,
        counter_store=PersistentTenantQuotaCounterStore(path),
    )
    assert restarted.check(tenant_id='tenant-a', dimension='connector_calls_per_hour').used == 1.0
    restarted.consume(tenant_id='tenant-a', dimension='connector_calls_per_hour')
    assert restarted.check(tenant_id='tenant-a', dimension='connector_calls_per_hour').allowed is False


def test_tenant_quota_snapshot_ignores_stale_windows(tmp_path) -> None:
    policies = InMemoryTenantPolicyStore()
    policies.save(_bundle('tenant-a', {'actions_per_hour': 2}))
    store = PersistentTenantQuotaCounterStore(tmp_path / 'quota-counters.json')
    guard = TenantQuotaGuard(policy_store=policies, counter_store=store)
    store.save(
        TenantQuotaCounterState(
            tenant_id='tenant-a',
            counter_key='tenant:actions_per_hour',
            window_key='1999010101',
            used=Decimal('99'),
            updated_at=datetime.now(timezone.utc),
        )
    )
    assert guard.snapshot(tenant_id='tenant-a')['actions_per_hour'] == 0.0

def test_connector_local_quota_persists_across_restart(tmp_path) -> None:
    path = tmp_path / 'quota-counters.json'
    first_store = PersistentTenantQuotaCounterStore(path)
    first = ConnectorQuotaGuard(
        per_connector_hour_limit=1,
        counter_store=first_store,
    )
    consumed = first.consume(
        tenant_id='tenant-a',
        connector_id='telegram',
    )
    assert consumed.allowed is True
    assert consumed.remaining == 0.0

    restarted = ConnectorQuotaGuard(
        per_connector_hour_limit=1,
        counter_store=PersistentTenantQuotaCounterStore(path),
    )
    blocked = restarted.check(
        tenant_id='tenant-a',
        connector_id='telegram',
    )
    assert blocked.allowed is False
    assert blocked.reason == 'connector_local_quota_exceeded'
    assert blocked.remaining == 0.0


def test_connector_quota_rejects_split_counter_stores() -> None:
    shared = InMemoryTenantQuotaCounterStore()
    tenant_guard = TenantQuotaGuard(counter_store=shared)

    with pytest.raises(ValueError, match='share one counter_store'):
        ConnectorQuotaGuard(
            quota_guard=tenant_guard,
            counter_store=InMemoryTenantQuotaCounterStore(),
            per_connector_hour_limit=1,
        )

