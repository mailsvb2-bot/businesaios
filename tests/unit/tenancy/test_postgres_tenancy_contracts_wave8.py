from __future__ import annotations

import pytest

from tests.unit.tenancy._postgres_tenancy_wave8_support import (
    PostgresTenantAdmissionBackendConfig,
    PostgresTenantMigrationLockBackendConfig,
    PostgresTenantRuntimeLeaseStoreConfig,
    admission_identifier,
    admission_lock_key,
    migration_identifier,
    migration_lock_key,
    runtime_identifier,
    runtime_lock_key,
)


@pytest.mark.parametrize("fn", [runtime_identifier, admission_identifier, migration_identifier])
def test_safe_identifier_contract(fn):
    assert fn("valid_name_2", field_name="table") == "valid_name_2"
    with pytest.raises(ValueError):
        fn("", field_name="table")
    with pytest.raises(ValueError):
        fn("bad-name", field_name="table")


@pytest.mark.parametrize("fn", [runtime_lock_key, admission_lock_key, migration_lock_key])
def test_advisory_lock_key_is_tenant_stable_signed_int64(fn):
    first = fn(namespace="ns", tenant_id="tenant-a")
    assert first == fn(namespace="ns", tenant_id="tenant-a")
    assert first != fn(namespace="ns", tenant_id="tenant-b")
    assert -(2**63) <= first < 2**63


def test_configs_validate():
    PostgresTenantRuntimeLeaseStoreConfig("dsn").validate()
    PostgresTenantAdmissionBackendConfig("dsn").validate()
    PostgresTenantMigrationLockBackendConfig("dsn").validate()
    for config in (
        PostgresTenantRuntimeLeaseStoreConfig(""),
        PostgresTenantAdmissionBackendConfig(""),
        PostgresTenantMigrationLockBackendConfig(""),
    ):
        with pytest.raises(ValueError):
            config.validate()
