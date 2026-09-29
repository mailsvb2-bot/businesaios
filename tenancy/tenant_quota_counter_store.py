from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from threading import RLock
from typing import Protocol

from core.finance.money import quantity_decimal
from core.tenancy.normalization import require_tenant_id
from governance.persistence_codec import atomic_write_json, read_json_or_default
from tenancy.tenant_contract import utc_now


CANON_TENANT_QUOTA_COUNTER_STORE = True


@dataclass(frozen=True)
class TenantQuotaCounterState:
    tenant_id: str
    counter_key: str
    window_key: str
    used: Decimal
    updated_at: datetime

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.counter_key or "").strip():
            raise ValueError("counter_key is required")
        if not str(self.window_key or "").strip():
            raise ValueError("window_key is required")
        quantity_decimal(self.used, name="used")
        if self.updated_at.tzinfo is None:
            raise ValueError("updated_at must be timezone-aware")


class TenantQuotaCounterStore(Protocol):
    def get(self, *, tenant_id: str, counter_key: str, window_key: str) -> TenantQuotaCounterState | None: ...
    def save(self, state: TenantQuotaCounterState) -> TenantQuotaCounterState: ...
    def delete(self, *, tenant_id: str, counter_key: str | None = None) -> None: ...
    def list_for_tenant(self, *, tenant_id: str) -> tuple[TenantQuotaCounterState, ...]: ...


class InMemoryTenantQuotaCounterStore:
    def __init__(self) -> None:
        self._states: dict[tuple[str, str, str], TenantQuotaCounterState] = {}
        self._lock = RLock()

    def get(self, *, tenant_id: str, counter_key: str, window_key: str) -> TenantQuotaCounterState | None:
        key = (require_tenant_id(tenant_id), str(counter_key).strip(), str(window_key).strip())
        with self._lock:
            return self._states.get(key)

    def save(self, state: TenantQuotaCounterState) -> TenantQuotaCounterState:
        state.validate()
        normalized = TenantQuotaCounterState(
            tenant_id=require_tenant_id(state.tenant_id),
            counter_key=str(state.counter_key).strip(),
            window_key=str(state.window_key).strip(),
            used=quantity_decimal(state.used, name="used"),
            updated_at=state.updated_at,
        )
        key = (normalized.tenant_id, normalized.counter_key, normalized.window_key)
        with self._lock:
            self._states[key] = normalized
        return normalized

    def delete(self, *, tenant_id: str, counter_key: str | None = None) -> None:
        tid = require_tenant_id(tenant_id)
        normalized_key = None if counter_key is None else str(counter_key).strip()
        with self._lock:
            for key in tuple(self._states):
                if key[0] == tid and (normalized_key is None or key[1] == normalized_key):
                    self._states.pop(key, None)

    def list_for_tenant(self, *, tenant_id: str) -> tuple[TenantQuotaCounterState, ...]:
        tid = require_tenant_id(tenant_id)
        with self._lock:
            return tuple(
                self._states[key]
                for key in sorted(self._states)
                if key[0] == tid
            )


def tenant_quota_counter_store_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_TENANT_QUOTA_COUNTER_STORE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("BUSINESAIOS_TENANCY_DATA_DIR", "").strip()
    if data_dir:
        return Path(data_dir) / "tenant_quota_counters.json"
    base = os.getenv("DATA_DIR", "data").strip() or "data"
    return Path(base) / "tenancy" / "tenant_quota_counters.json"


class PersistentTenantQuotaCounterStore(InMemoryTenantQuotaCounterStore):
    def __init__(self, path: str | Path | None = None) -> None:
        super().__init__()
        self._path = Path(path) if path is not None else tenant_quota_counter_store_path()
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def save(self, state: TenantQuotaCounterState) -> TenantQuotaCounterState:
        saved = super().save(state)
        self._flush()
        return saved

    def delete(self, *, tenant_id: str, counter_key: str | None = None) -> None:
        super().delete(tenant_id=tenant_id, counter_key=counter_key)
        self._flush()

    def _load(self) -> None:
        raw = read_json_or_default(self._path, default={"states": []})
        rows = raw.get("states", []) if isinstance(raw, dict) else []
        self._states = {}
        for raw_state in rows:
            item = dict(raw_state)
            state = TenantQuotaCounterState(
                tenant_id=str(item.get("tenant_id") or ""),
                counter_key=str(item.get("counter_key") or ""),
                window_key=str(item.get("window_key") or ""),
                used=quantity_decimal(item.get("used", 0), name="used"),
                updated_at=datetime.fromisoformat(str(item.get("updated_at") or "")),
            )
            super().save(state)

    def _flush(self) -> None:
        with self._lock:
            rows = [
                {
                    "tenant_id": state.tenant_id,
                    "counter_key": state.counter_key,
                    "window_key": state.window_key,
                    "used": str(state.used),
                    "updated_at": state.updated_at.isoformat(),
                }
                for state in sorted(
                    self._states.values(),
                    key=lambda value: (value.tenant_id, value.counter_key, value.window_key),
                )
            ]
        atomic_write_json(self._path, {"states": rows})


def build_default_tenant_quota_counter_store() -> TenantQuotaCounterStore:
    mode = os.getenv("BUSINESAIOS_TENANT_QUOTA_COUNTER_STORE_BACKEND", "file").strip().lower()
    if mode == "memory":
        return InMemoryTenantQuotaCounterStore()
    return PersistentTenantQuotaCounterStore()


__all__ = [
    "CANON_TENANT_QUOTA_COUNTER_STORE",
    "InMemoryTenantQuotaCounterStore",
    "PersistentTenantQuotaCounterStore",
    "TenantQuotaCounterState",
    "TenantQuotaCounterStore",
    "build_default_tenant_quota_counter_store",
    "tenant_quota_counter_store_path",
]
