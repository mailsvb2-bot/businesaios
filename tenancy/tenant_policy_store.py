from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Mapping
import os

from core.tenancy.normalization import require_tenant_id
from governance.persistence_codec import atomic_write_json, from_dataclass, read_json_or_default, to_jsonable
from tenancy.tenant_audit_scope import TenantAuditScope
from tenancy.tenant_billing_scope import TenantBillingScope
from tenancy.tenant_connector_scope import TenantConnectorScope
from tenancy.tenant_time import utc_now
from tenancy.tenant_feature_flags import TenantFeatureFlags
from tenancy.tenant_memory_scope import TenantMemoryScope
from tenancy.tenant_runtime_limits import TenantRuntimeLimits


CANON_TENANT_POLICY_STORE = True


@dataclass(frozen=True)
class TenantPolicyBundle:
    tenant_id: str
    feature_flags: TenantFeatureFlags
    runtime_limits: TenantRuntimeLimits
    memory_scope: TenantMemoryScope
    connector_scope: TenantConnectorScope
    audit_scope: TenantAuditScope
    billing_scope: TenantBillingScope
    quotas: Mapping[str, float] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        tid = require_tenant_id(self.tenant_id)
        self.feature_flags.validate()
        self.runtime_limits.validate()
        self.memory_scope.validate()
        self.connector_scope.validate()
        self.audit_scope.validate()
        self.billing_scope.validate()

        for child_tenant_id in (
            self.feature_flags.tenant_id,
            self.runtime_limits.tenant_id,
            self.memory_scope.tenant_id,
            self.connector_scope.tenant_id,
            self.audit_scope.tenant_id,
            self.billing_scope.tenant_id,
        ):
            if require_tenant_id(child_tenant_id) != tid:
                raise ValueError("cross-tenant policy bundle is forbidden")

        if self.updated_at.tzinfo is None:
            raise ValueError("updated_at must be timezone-aware")

        for key, value in self.quotas.items():
            if not str(key or "").strip():
                raise ValueError("quota keys must be non-empty")
            if float(value) < 0:
                raise ValueError("quota limits must be >= 0")


class InMemoryTenantPolicyStore:
    def __init__(self, bundles: tuple[TenantPolicyBundle, ...] = ()) -> None:
        self._bundles: dict[str, TenantPolicyBundle] = {}
        self._lock = RLock()
        for bundle in bundles:
            self.save(bundle)

    def get(self, tenant_id: str) -> TenantPolicyBundle | None:
        tid = require_tenant_id(tenant_id)
        with self._lock:
            return self._bundles.get(tid)

    def require(self, tenant_id: str) -> TenantPolicyBundle:
        bundle = self.get(tenant_id)
        if bundle is None:
            raise KeyError(f"missing tenant policy bundle: {tenant_id}")
        return bundle

    def save(self, bundle: TenantPolicyBundle) -> TenantPolicyBundle:
        bundle.validate()
        with self._lock:
            self._bundles[require_tenant_id(bundle.tenant_id)] = bundle
        return bundle




def build_default_tenant_policy_bundle(tenant_id: str) -> TenantPolicyBundle:
    tid = require_tenant_id(tenant_id)
    runtime_limits = TenantRuntimeLimits(tenant_id=tid)
    quotas = {
        'actions_per_day': float(runtime_limits.max_actions_per_run),
        'outbound_messages_per_day': float(runtime_limits.max_outbound_messages_per_day),
        'publications_per_day': float(runtime_limits.max_publications_per_day),
        'memory_writes_per_day': float(runtime_limits.max_memory_writes_per_day),
        'connector_calls_per_hour': float(runtime_limits.max_connector_calls_per_hour),
        'daily_budget': float(runtime_limits.max_daily_budget),
    }
    return TenantPolicyBundle(
        tenant_id=tid,
        feature_flags=TenantFeatureFlags(tenant_id=tid),
        runtime_limits=runtime_limits,
        memory_scope=TenantMemoryScope(tenant_id=tid),
        connector_scope=TenantConnectorScope(tenant_id=tid),
        audit_scope=TenantAuditScope(tenant_id=tid),
        billing_scope=TenantBillingScope(tenant_id=tid),
        quotas=quotas,
    )


def ensure_tenant_policy_bundle(store: InMemoryTenantPolicyStore, tenant_id: str) -> TenantPolicyBundle:
    tid = require_tenant_id(tenant_id)
    current = store.get(tid)
    if current is not None:
        return current
    return store.save(build_default_tenant_policy_bundle(tid))


def tenancy_policy_store_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_TENANT_POLICY_STORE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("BUSINESAIOS_TENANCY_DATA_DIR", "").strip()
    if data_dir:
        return Path(data_dir) / "tenant_policies.json"
    base = os.getenv("DATA_DIR", "data").strip() or "data"
    return Path(base) / "tenancy" / "tenant_policies.json"


class PersistentTenantPolicyStore(InMemoryTenantPolicyStore):
    def __init__(self, path: str | Path | None = None) -> None:
        super().__init__()
        self._path = Path(path) if path is not None else tenancy_policy_store_path()
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def save(self, bundle: TenantPolicyBundle) -> TenantPolicyBundle:
        saved = super().save(bundle)
        self._flush()
        return saved

    def _load(self) -> None:
        raw = read_json_or_default(self._path, default={"bundles": []})
        bundles = raw.get("bundles", []) if isinstance(raw, dict) else []
        self._bundles = {}
        for item in bundles:
            bundle = from_dataclass(TenantPolicyBundle, dict(item))
            super().save(bundle)

    def _flush(self) -> None:
        with self._lock:
            bundles = [to_jsonable(item) for item in sorted(self._bundles.values(), key=lambda item: item.tenant_id)]
        atomic_write_json(self._path, {"bundles": bundles})


def build_default_tenant_policy_store() -> InMemoryTenantPolicyStore:
    mode = os.getenv("BUSINESAIOS_TENANT_POLICY_STORE_BACKEND", "file").strip().lower()
    if mode == "memory":
        return InMemoryTenantPolicyStore()
    return PersistentTenantPolicyStore()


__all__ = [
    "CANON_TENANT_POLICY_STORE",
    "InMemoryTenantPolicyStore",
    "PersistentTenantPolicyStore",
    "TenantPolicyBundle",
    "build_default_tenant_policy_bundle",
    "ensure_tenant_policy_bundle",
    "build_default_tenant_policy_store",
    "tenancy_policy_store_path",
]
