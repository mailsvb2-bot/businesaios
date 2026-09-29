from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from threading import RLock
from typing import Iterable

from core.finance.money import legacy_float, money_decimal, quantity_decimal
from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_contract import TenantPolicyStoreContract, TenantQuotaCheck, utc_now
from tenancy.tenant_quota_counter_store import (
    InMemoryTenantQuotaCounterStore,
    TenantQuotaCounterState,
    TenantQuotaCounterStore,
)


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
        current = self._counter_store.get(
            tenant_id=tenant_id,
            counter_key=counter_key,
            window_key=window_key,
        )
        used = Decimal("0") if current is None else current.used
        return self._counter_store.save(
            TenantQuotaCounterState(
                tenant_id=tenant_id,
                counter_key=counter_key,
                window_key=window_key,
                used=used + amount,
                updated_at=utc_now(),
            )
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
    "CANON_TENANT_QUOTA_GUARD",
    "QuotaDimension",
    "TenantQuotaGuard",
]
