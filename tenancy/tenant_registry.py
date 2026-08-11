from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from threading import RLock

from core.tenancy.normalization import normalize_tenant_id, require_tenant_id
from governance.persistence_codec import atomic_write_json, from_dataclass, read_json_or_default, to_jsonable
from tenancy.tenant_contract import TenantPlan, TenantRecord, TenantRegistryContract, TenantStatus

CANON_TENANT_REGISTRY = True


class InMemoryTenantRegistry(TenantRegistryContract):
    def __init__(self, records: tuple[TenantRecord, ...] = ()) -> None:
        self._records: dict[str, TenantRecord] = {}
        self._aliases: dict[str, str] = {}
        self._lock = RLock()
        InMemoryTenantRegistry.register_many(self, records)

    def register(self, record: TenantRecord) -> TenantRecord:
        return InMemoryTenantRegistry.register_many(self, (record,))[0]

    def register_many(self, records: tuple[TenantRecord, ...] | list[TenantRecord]) -> tuple[TenantRecord, ...]:
        with self._lock:
            shadow_records, shadow_aliases = dict(self._records), dict(self._aliases)
            stored: list[TenantRecord] = []
            for record in records:
                record.validate()
                tenant_id = require_tenant_id(record.tenant_id)
                existing = shadow_records.get(tenant_id)
                if existing is not None:
                    if existing != record:
                        raise ValueError(f"tenant already registered: {tenant_id}")
                    stored.append(existing)
                    continue
                aliases = self._normalized_aliases(record.aliases)
                for alias in aliases:
                    owner = shadow_aliases.get(alias)
                    if owner is not None and owner != tenant_id:
                        raise ValueError(f"alias collision: {alias}")
                shadow_records[tenant_id] = record
                shadow_aliases.update(dict.fromkeys(aliases, tenant_id))
                stored.append(record)
            self._records, self._aliases = shadow_records, shadow_aliases
            return tuple(stored)

    def lookup(self, tenant_id: str) -> TenantRecord | None:
        tid = normalize_tenant_id(tenant_id)
        if not tid:
            return None
        with self._lock:
            return self._records.get(tid)

    get = lookup

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
            return self._records.get(hint) or self._records.get(self._aliases.get(hint, ""))

    def assert_active(self, tenant_id: str) -> TenantRecord:
        record = self.require(tenant_id)
        if record.status is not TenantStatus.ACTIVE:
            raise PermissionError(f"tenant is not active: {record.tenant_id}")
        return record

    def list_active(self) -> tuple[TenantRecord, ...]:
        with self._lock:
            active = (record for record in self._records.values() if record.status is TenantStatus.ACTIVE)
            return tuple(sorted(active, key=lambda item: item.tenant_id))

    def _replace_record(self, tenant_id: str, **changes: object) -> TenantRecord:
        updated = replace(self.require(tenant_id), **changes)
        updated.validate()
        with self._lock:
            self._records[updated.tenant_id] = updated
        return updated

    def set_status(self, *, tenant_id: str, status: TenantStatus) -> TenantRecord:
        return self._replace_record(tenant_id, status=status)

    def set_plan(self, *, tenant_id: str, plan: TenantPlan) -> TenantRecord:
        return self._replace_record(tenant_id, plan=plan if isinstance(plan, TenantPlan) else TenantPlan(str(plan)))

    @staticmethod
    def _normalized_aliases(values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(alias for item in values if (alias := normalize_tenant_id(item))))


def ensure_tenant_record(
    tenant_registry: TenantRegistryContract,
    tenant_id: str,
    *,
    display_name: str | None = None,
    plan: TenantPlan = TenantPlan.STARTER,
) -> TenantRecord:
    tid = require_tenant_id(tenant_id)
    lookup = getattr(tenant_registry, "lookup", None)
    existing = lookup(tid) if callable(lookup) else tenant_registry.get(tid)
    if existing is not None:
        return existing
    record = TenantRecord(tenant_id=tid, display_name=str(display_name or tid), plan=plan)
    register_many = getattr(tenant_registry, "register_many", None)
    return register_many((record,))[0] if callable(register_many) else getattr(tenant_registry, "register")(record)


def tenancy_data_dir() -> Path:
    explicit = os.getenv("BUSINESAIOS_TENANCY_DATA_DIR", "").strip()
    return Path(explicit) if explicit else Path(os.getenv("DATA_DIR", "data").strip() or "data") / "tenancy"


def tenant_registry_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_TENANT_REGISTRY_PATH", "").strip()
    return Path(explicit) if explicit else tenancy_data_dir() / "tenant_registry.json"


class PersistentTenantRegistry(InMemoryTenantRegistry):
    def __init__(self, path: str | Path | None = None, records: tuple[TenantRecord, ...] = ()) -> None:
        self._path = Path(path) if path is not None else tenant_registry_path()
        super().__init__()
        self._load()
        if records:
            self.register_many(records)

    @property
    def path(self) -> Path:
        return self._path

    def _persist(self, value):
        self._flush()
        return value

    def register(self, record: TenantRecord) -> TenantRecord:
        return self._persist(super().register(record))

    def set_status(self, *, tenant_id: str, status: TenantStatus) -> TenantRecord:
        return self._persist(super().set_status(tenant_id=tenant_id, status=status))

    def set_plan(self, *, tenant_id: str, plan: TenantPlan) -> TenantRecord:
        return self._persist(super().set_plan(tenant_id=tenant_id, plan=plan))

    def register_many(self, records: tuple[TenantRecord, ...] | list[TenantRecord]) -> tuple[TenantRecord, ...]:
        return self._persist(super().register_many(records))

    def _load(self) -> None:
        raw = read_json_or_default(self._path, default={"records": []})
        self._records, self._aliases = {}, {}
        for item in raw.get("records", []) if isinstance(raw, dict) else []:
            if isinstance(item, dict):
                InMemoryTenantRegistry.register(self, from_dataclass(TenantRecord, dict(item)))

    def _flush(self) -> None:
        with self._lock:
            records = [to_jsonable(item) for item in sorted(self._records.values(), key=lambda item: item.tenant_id)]
        atomic_write_json(self._path, {"records": records})


def build_default_tenant_registry() -> InMemoryTenantRegistry:
    return InMemoryTenantRegistry() if os.getenv("BUSINESAIOS_TENANT_REGISTRY_BACKEND", "file").strip().lower() == "memory" else PersistentTenantRegistry()


__all__ = [
    "CANON_TENANT_REGISTRY",
    "InMemoryTenantRegistry",
    "PersistentTenantRegistry",
    "build_default_tenant_registry",
    "ensure_tenant_record",
    "tenancy_data_dir",
    "tenant_registry_path",
]
