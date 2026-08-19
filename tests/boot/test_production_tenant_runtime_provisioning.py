from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.boot.system_builder_parts import runtime_services_tenant as subject
from tenancy.tenant_contract import TenantRecord, TenantStatus


class _Registry:
    def __init__(self, *, exists: bool = False, active: bool = True) -> None:
        status = TenantStatus.ACTIVE if active else TenantStatus.SUSPENDED
        self.record = TenantRecord(tenant_id="tenant-live", display_name="tenant-live", status=status) if exists else None
        self.registered: list[TenantRecord] = []

    def lookup(self, tenant_id: str):
        return self.record if self.record and self.record.tenant_id == tenant_id else None

    def assert_active(self, tenant_id: str):
        record = self.lookup(tenant_id)
        if record is None:
            raise KeyError(f"unknown tenant: {tenant_id}")
        if record.status is not TenantStatus.ACTIVE:
            raise PermissionError(f"tenant is not active: {tenant_id}")
        return record

    def register(self, record: TenantRecord):
        self.registered.append(record)
        self.record = record
        return record


class _PolicyStore:
    def __init__(self, *, exists: bool = False) -> None:
        self.bundle = SimpleNamespace(runtime_limits=None) if exists else None
        self.saved: list[object] = []

    def get(self, _tenant_id: str):
        return self.bundle

    def require(self, tenant_id: str):
        if self.bundle is None:
            raise KeyError(f"missing tenant policy bundle: {tenant_id}")
        return self.bundle

    def save(self, bundle):
        self.saved.append(bundle)
        self.bundle = bundle
        return bundle


class _ReachedRuntimeAssembly(RuntimeError):
    pass


def _wire(monkeypatch: pytest.MonkeyPatch, registry: _Registry, policy_store: _PolicyStore) -> None:
    monkeypatch.setattr(subject, "build_default_tenant_registry", lambda: registry)
    monkeypatch.setattr(subject, "build_default_tenant_policy_store", lambda: policy_store)
    monkeypatch.setattr(subject, "TenantQuotaGuard", lambda **kwargs: (_ for _ in ()).throw(_ReachedRuntimeAssembly(str(kwargs))))


@pytest.mark.parametrize(
    ("registry", "policy_store", "error"),
    [
        (_Registry(), _PolicyStore(), "unknown tenant: tenant-live"),
        (_Registry(exists=True), _PolicyStore(), "missing tenant policy bundle: tenant-live"),
    ],
)
def test_production_requires_preprovisioned_tenant_and_policy_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
    registry: _Registry,
    policy_store: _PolicyStore,
    error: str,
) -> None:
    _wire(monkeypatch, registry, policy_store)
    with pytest.raises(KeyError, match=error):
        subject.build_tenant_runtime_services(tenant_id="tenant-live", production=True)
    assert registry.registered == []
    assert policy_store.saved == []


def test_production_preprovisioned_tenant_reaches_runtime_without_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    registry, policy_store = _Registry(exists=True), _PolicyStore(exists=True)
    _wire(monkeypatch, registry, policy_store)
    with pytest.raises(_ReachedRuntimeAssembly):
        subject.build_tenant_runtime_services(tenant_id="tenant-live", production=True)
    assert registry.registered == []
    assert policy_store.saved == []


def test_nonproduction_keeps_bootstrap_convenience(monkeypatch: pytest.MonkeyPatch) -> None:
    registry, policy_store = _Registry(), _PolicyStore()
    _wire(monkeypatch, registry, policy_store)
    with pytest.raises(_ReachedRuntimeAssembly):
        subject.build_tenant_runtime_services(tenant_id="tenant-live", production=False)
    assert [record.tenant_id for record in registry.registered] == ["tenant-live"]
    assert len(policy_store.saved) == 1
