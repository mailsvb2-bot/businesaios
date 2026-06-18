from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from threading import RLock
import os

from core.tenancy.normalization import normalize_tenant_id, require_tenant_id
from governance.persistence_codec import atomic_write_json, from_dataclass, read_json_or_default, to_jsonable
from tenancy.tenant_contract import TenantPlan, TenantRecord, TenantRegistryContract, TenantStatus


CANON_TENANT_REGISTRY = True


class InMemoryTenantRegistry(TenantRegistryContract):
    def __init__(self, records: tuple[TenantRecord, ...] = ()) -> None:
        self._records: dict[str, TenantRecord] = {}
        self._aliases: dict[str, str] = {}
        self._lock = RLock()
        for record in records:
            self.register(record)

    def register(self, record: TenantRecord) -> TenantRecord:
        record.validate()
        tenant_id = require_tenant_id(record.tenant_id)
        with self._lock:
            existing = self._records.get(tenant_id)
            if existing is not None:
                if existing != record:
                    raise ValueError(f"tenant already registered: {tenant_id}")
                return existing
            for alias in self._normalized_aliases(record.aliases):
                owner = self._aliases.get(alias)
                if owner is not None and owner != tenant_id:
                    raise ValueError(f"alias collision: {alias}")
            self._records[tenant_id] = record
            for alias in self._normalized_aliases(record.aliases):
                self._aliases[alias] = tenant_id
            return record

    def register_many(self, records: tuple[TenantRecord, ...] | list[TenantRecord]) -> tuple[TenantRecord, ...]:
        prepared = tuple(records)
        with self._lock:
            shadow_records = dict(self._records)
            shadow_aliases = dict(self._aliases)
            stored: list[TenantRecord] = []
            for record in prepared:
                record.validate()
                tenant_id = require_tenant_id(record.tenant_id)
                existing = shadow_records.get(tenant_id)
                if existing is not None:
                    if existing != record:
                        raise ValueError(f"tenant already registered: {tenant_id}")
                    stored.append(existing)
                    continue
                for alias in self._normalized_aliases(record.aliases):
                    owner = shadow_aliases.get(alias)
                    if owner is not None and owner != tenant_id:
                        raise ValueError(f"alias collision: {alias}")
                shadow_records[tenant_id] = record
                for alias in self._normalized_aliases(record.aliases):
                    shadow_aliases[alias] = tenant_id
                stored.append(record)
            self._records = shadow_records
            self._aliases = shadow_aliases
            return tuple(stored)

    def lookup(self, tenant_id: str) -> TenantRecord | None:
        tid = normalize_tenant_id(tenant_id)
        if not tid:
            return None
        with self._lock:
            return self._records.get(tid)

    def get(self, tenant_id: str) -> TenantRecord | None:
        return self.lookup(tenant_id)

    def require(self, tenant_id: str) -> TenantRecord:
        record = self.lookup(tenant_id)
        if record is None:
            raise KeyError(f"unknown tenant: {tenant_id}")
        return record

    def resolve(self, tenant_hint: str) -> TenantRecord | None:
        hint = normalize_tenant_id(tenant_hint)
        if not hint:
            return None
        with self._lock:
            direct = self._records.get(hint)
            if direct is not None:
                return direct
            mapped = self._aliases.get(hint)
            if mapped is None:
                return None
            return self._records.get(mapped)

    def assert_active(self, tenant_id: str) -> TenantRecord:
        record = self.require(tenant_id)
        if record.status is not TenantStatus.ACTIVE:
            raise PermissionError(f"tenant is not active: {record.tenant_id}")
        return record

    def list_active(self) -> tuple[TenantRecord, ...]:
        with self._lock:
            items = [record for record in self._records.values() if record.status is TenantStatus.ACTIVE]
            return tuple(sorted(items, key=lambda item: item.tenant_id))

    def set_status(self, *, tenant_id: str, status: TenantStatus) -> TenantRecord:
        current = self.require(tenant_id)
        updated = replace(current, status=status)
        with self._lock:
            self._records[updated.tenant_id] = updated
        return updated

    @staticmethod
    def _normalized_aliases(values: tuple[str, ...]) -> tuple[str, ...]:
        result: list[str] = []
        seen: set[str] = set()
        for item in values:
            alias = normalize_tenant_id(item)
            if alias and alias not in seen:
                seen.add(alias)
                result.append(alias)
        return tuple(result)




def ensure_tenant_record(tenant_registry: TenantRegistryContract, tenant_id: str, *, display_name: str | None = None, plan: TenantPlan = TenantPlan.STARTER) -> TenantRecord:
    tid = require_tenant_id(tenant_id)
    lookup = getattr(tenant_registry, 'lookup', None)
    existing = lookup(tid) if callable(lookup) else tenant_registry.get(tid)
    if existing is not None:
        return existing
    record = TenantRecord(tenant_id=tid, display_name=str(display_name or tid), plan=plan)
    register_many = getattr(tenant_registry, 'register_many', None)
    if callable(register_many):
        return register_many((record,))[0]
    register_one = getattr(tenant_registry, 'register')
    return register_one(record)


def tenancy_data_dir() -> Path:
    explicit = os.getenv("BUSINESAIOS_TENANCY_DATA_DIR", "").strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("DATA_DIR", "data").strip() or "data"
    return Path(data_dir) / "tenancy"


def tenant_registry_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_TENANT_REGISTRY_PATH", "").strip()
    if explicit:
        return Path(explicit)
    return tenancy_data_dir() / "tenant_registry.json"
