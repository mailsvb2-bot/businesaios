from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Iterable, Protocol

from core.finance.money import legacy_float, money_decimal, quantity_decimal
from core.tenancy.normalization import require_tenant_id
from governance.persistence_codec import atomic_write_json, read_json_or_default
from tenancy.tenant_contract import TenantPolicyStoreContract, TenantQuotaCheck, utc_now

CANON_TENANT_QUOTA_COUNTER_STORE = True
quota_quantity_decimal = quantity_decimal
quota_require_tenant_id = require_tenant_id

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

def _normalized_state(state: TenantQuotaCounterState) -> TenantQuotaCounterState:
    state.validate()
    return TenantQuotaCounterState(
        tenant_id=require_tenant_id(state.tenant_id),
        counter_key=str(state.counter_key).strip(),
        window_key=str(state.window_key).strip(),
        used=quantity_decimal(state.used, name="used"),
        updated_at=state.updated_at,
    )

class TenantQuotaCounterStore(Protocol):
    def get(self, *, tenant_id: str, counter_key: str, window_key: str) -> TenantQuotaCounterState | None: ...
    def save(self, state: TenantQuotaCounterState) -> TenantQuotaCounterState: ...
    def increment(
        self,
        *,
        tenant_id: str,
        counter_key: str,
        window_key: str,
        amount: Decimal,
        updated_at: datetime,
    ) -> TenantQuotaCounterState: ...
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
        normalized = _normalized_state(state)
        key = (normalized.tenant_id, normalized.counter_key, normalized.window_key)
        with self._lock:
            self._states[key] = normalized
        return normalized

    def increment(
        self,
        *,
        tenant_id: str,
        counter_key: str,
        window_key: str,
        amount: Decimal,
        updated_at: datetime,
    ) -> TenantQuotaCounterState:
        tid = require_tenant_id(tenant_id)
        key = (tid, str(counter_key).strip(), str(window_key).strip())
        delta = quantity_decimal(amount, name="amount")
        if updated_at.tzinfo is None:
            raise ValueError("updated_at must be timezone-aware")
        with self._lock:
            current = self._states.get(key)
            used = Decimal("0") if current is None else current.used
            state = TenantQuotaCounterState(
                tenant_id=tid,
                counter_key=key[1],
                window_key=key[2],
                used=used + delta,
                updated_at=updated_at,
            )
            self._states[key] = state
            return state

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
            return tuple(self._states[key] for key in sorted(self._states) if key[0] == tid)

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
    """Legacy/simple JSON backend retained for compatibility and focused tests."""

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

    def increment(
        self,
        *,
        tenant_id: str,
        counter_key: str,
        window_key: str,
        amount: Decimal,
        updated_at: datetime,
    ) -> TenantQuotaCounterState:
        state = super().increment(
            tenant_id=tenant_id,
            counter_key=counter_key,
            window_key=window_key,
            amount=amount,
            updated_at=updated_at,
        )
        self._flush()
        return state

    def delete(self, *, tenant_id: str, counter_key: str | None = None) -> None:
        super().delete(tenant_id=tenant_id, counter_key=counter_key)
        self._flush()

    def _load(self) -> None:
        raw = read_json_or_default(self._path, default={"states": []})
        rows = raw.get("states", []) if isinstance(raw, dict) else []
        self._states = {}
        for raw_state in rows:
            item = dict(raw_state)
            super().save(
                TenantQuotaCounterState(
                    tenant_id=str(item.get("tenant_id") or ""),
                    counter_key=str(item.get("counter_key") or ""),
                    window_key=str(item.get("window_key") or ""),
                    used=quantity_decimal(item.get("used", 0), name="used"),
                    updated_at=datetime.fromisoformat(str(item.get("updated_at") or "")),
                )
            )

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

CANON_TENANT_QUOTA_GUARD = True

class QuotaDimension(str, Enum):
    ACTIONS_PER_HOUR = "actions_per_hour"
    ACTIONS_PER_DAY = "actions_per_day"
    OUTBOUND_MESSAGES_PER_DAY = "outbound_messages_per_day"
    PUBLICATIONS_PER_DAY = "publications_per_day"
    MEMORY_WRITES_PER_DAY = "memory_writes_per_day"
    CONNECTOR_CALLS_PER_HOUR = "connector_calls_per_hour"
    DAILY_BUDGET = "daily_budget"

class TenantQuotaGuard:
    def __init__(
        self,
        *,
        policy_store: TenantPolicyStoreContract | None = None,
        counter_store: TenantQuotaCounterStore | None = None,
    ) -> None:
        self._policy_store = policy_store
        self._counter_store = counter_store or InMemoryTenantQuotaCounterStore()
        self._lock = RLock()

    @property
    def counter_store(self) -> TenantQuotaCounterStore:
        return self._counter_store

    def check(
        self,
        *,
        tenant_id: str,
        dimension: str,
        amount: float = 1.0,
    ) -> TenantQuotaCheck:
        tid = require_tenant_id(tenant_id)
        dim = self._require_dimension(dimension)
        requested = self._require_amount(dim, amount)
        with self._lock:
            return self._build_check_locked(
                tenant_id=tid,
                dimension=dim,
                amount=requested,
            )

    def check_many(
        self,
        *,
        tenant_id: str,
        requests: Iterable[tuple[str, float]],
    ) -> dict[str, TenantQuotaCheck]:
        tid = require_tenant_id(tenant_id)
        prepared = [
            (dim, self._require_amount(dim, amount))
            for raw_dimension, amount in tuple(requests)
            for dim in (self._require_dimension(raw_dimension),)
        ]
        with self._lock:
            return {
                dimension: self._build_check_locked(
                    tenant_id=tid,
                    dimension=dimension,
                    amount=amount,
                )
                for dimension, amount in prepared
            }

    def consume(
        self,
        *,
        tenant_id: str,
        dimension: str,
        amount: float = 1.0,
    ) -> TenantQuotaCheck:
        tid = require_tenant_id(tenant_id)
        dim = self._require_dimension(dimension)
        requested = self._require_amount(dim, amount)
        with self._lock:
            verdict = self._build_check_locked(
                tenant_id=tid,
                dimension=dim,
                amount=requested,
            )
            if not verdict.allowed:
                return verdict
            state = self._consume_locked(tid, dim, requested)
            return self._build_consumed_verdict_locked(
                state=state,
                requested=requested,
            )

    def consume_many(
        self,
        *,
        tenant_id: str,
        requests: Iterable[tuple[str, float]],
    ) -> dict[str, TenantQuotaCheck]:
        tid = require_tenant_id(tenant_id)
        prepared = [
            (dim, self._require_amount(dim, amount))
            for raw_dimension, amount in tuple(requests)
            for dim in (self._require_dimension(raw_dimension),)
        ]
        with self._lock:
            checks = {
                dimension: self._build_check_locked(
                    tenant_id=tid,
                    dimension=dimension,
                    amount=amount,
                )
                for dimension, amount in prepared
            }
            failed = next((check for check in checks.values() if not check.allowed), None)
            if failed is not None:
                return checks
            consumed: dict[str, TenantQuotaCheck] = {}
            for dimension, amount in prepared:
                state = self._consume_locked(tid, dimension, amount)
                consumed[dimension] = self._build_consumed_verdict_locked(
                    state=state,
                    requested=amount,
                )
            return consumed

    def reset(self, *, tenant_id: str, dimension: str | None = None) -> None:
        tid = require_tenant_id(tenant_id)
        with self._lock:
            counter_key = None if dimension is None else self._counter_key(self._require_dimension(dimension))
            if counter_key is None:
                for state in self._counter_store.list_for_tenant(tenant_id=tid):
                    if state.counter_key.startswith("tenant:"):
                        self._counter_store.delete(tenant_id=tid, counter_key=state.counter_key)
            else:
                self._counter_store.delete(tenant_id=tid, counter_key=counter_key)

    def snapshot(self, *, tenant_id: str) -> dict[str, float]:
        tid = require_tenant_id(tenant_id)
        with self._lock:
            result: dict[str, Decimal] = {}
            if self._policy_store is not None:
                bundle = self._policy_store.get(tid)
                if bundle is not None:
                    for dimension in sorted(dict(bundle.quotas).keys()):
                        result[str(dimension)] = Decimal("0")
            for state in self._counter_store.list_for_tenant(tenant_id=tid):
                if not state.counter_key.startswith("tenant:"):
                    continue
                dimension = state.counter_key.removeprefix("tenant:")
                if state.window_key != self._window_key(dimension):
                    continue
                result[dimension] = state.used
            return {
                dimension: legacy_float(value, name=f"{dimension}_used")
                for dimension, value in result.items()
            }

    def _build_check_locked(
        self,
        *,
        tenant_id: str,
        dimension: str,
        amount: Decimal,
    ) -> TenantQuotaCheck:
        limit = self._limit_for_locked(tenant_id, dimension)
        state = self._counter_store.get(
            tenant_id=tenant_id,
            counter_key=self._counter_key(dimension),
            window_key=self._window_key(dimension),
        )
        used = Decimal("0") if state is None else state.used
        requested_value = legacy_float(amount, name="requested")
        used_value = legacy_float(used, name="used")
        if limit is None:
            return TenantQuotaCheck(
                allowed=True,
                reason="no quota configured",
                tenant_id=tenant_id,
                dimension=dimension,
                requested=requested_value,
                used=used_value,
                limit=None,
                remaining=None,
                retry_after_seconds=None,
            )
        remaining = max(Decimal("0"), limit - used)
        allowed = amount <= remaining
        return TenantQuotaCheck(
            allowed=allowed,
            reason="ok" if allowed else "quota exceeded",
            tenant_id=tenant_id,
            dimension=dimension,
            requested=requested_value,
            used=used_value,
            limit=legacy_float(limit, name="limit"),
            remaining=legacy_float(remaining, name="remaining"),
            retry_after_seconds=(
                None if allowed else self._retry_after_seconds(dimension)
            ),
        )

    def _build_consumed_verdict_locked(
        self,
        *,
        state: TenantQuotaCounterState,
        requested: Decimal,
    ) -> TenantQuotaCheck:
        dimension = state.counter_key.removeprefix("tenant:")
        limit = self._limit_for_locked(state.tenant_id, dimension)
        remaining = None if limit is None else max(Decimal("0"), limit - state.used)
        return TenantQuotaCheck(
            allowed=True,
            reason="consumed",
            tenant_id=state.tenant_id,
            dimension=dimension,
            requested=legacy_float(requested, name="requested"),
            used=legacy_float(state.used, name="used"),
            limit=None if limit is None else legacy_float(limit, name="limit"),
            remaining=(
                None
                if remaining is None
                else legacy_float(remaining, name="remaining")
            ),
            retry_after_seconds=None,
        )

    def _limit_for_locked(self, tenant_id: str, dimension: str) -> Decimal | None:
        if self._policy_store is None:
            return None
        bundle = self._policy_store.get(tenant_id)
        if bundle is None:
            return None
        raw = bundle.quotas.get(dimension)
        if raw is None:
            return None
        return self._require_amount(dimension, raw)

    def _consume_locked(self, tenant_id: str, dimension: str, amount: Decimal) -> TenantQuotaCounterState:
        window_key = self._window_key(dimension)
        counter_key = self._counter_key(dimension)
        return self._counter_store.increment(
            tenant_id=tenant_id,
            counter_key=counter_key,
            window_key=window_key,
            amount=amount,
            updated_at=utc_now(),
        )

    @staticmethod
    def _counter_key(dimension: str) -> str:
        return f"tenant:{dimension}"

    @staticmethod
    def _require_dimension(dimension: str) -> str:
        dim = str(dimension or "").strip()
        if not dim:
            raise ValueError("dimension is required")
        return dim

    @staticmethod
    def _require_amount(dimension: str, amount: object) -> Decimal:
        if dimension == QuotaDimension.DAILY_BUDGET.value:
            return money_decimal(amount, name="amount")
        return quantity_decimal(amount, name="amount")

    @staticmethod
    def _window_key(dimension: str) -> str:
        now = datetime.now(timezone.utc)
        if dimension.endswith("_per_hour"):
            return now.strftime("%Y%m%d%H")
        return now.strftime("%Y%m%d")

    @staticmethod
    def _retry_after_seconds(dimension: str) -> int:
        return 3600 if str(dimension).endswith("_per_hour") else 86400

__all__ = [
    "CANON_TENANT_QUOTA_COUNTER_STORE",
    "CANON_TENANT_QUOTA_GUARD",
    "InMemoryTenantQuotaCounterStore",
    "PersistentTenantQuotaCounterStore",
    "QuotaDimension",
    "TenantQuotaCounterState",
    "TenantQuotaCounterStore",
    "TenantQuotaGuard",
    "tenant_quota_counter_store_path",
]
