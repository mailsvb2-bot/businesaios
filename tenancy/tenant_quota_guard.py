from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import Iterable

from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_contract import TenantPolicyStoreContract, TenantQuotaCheck, utc_now


CANON_TENANT_QUOTA_GUARD = True


class QuotaDimension(str, Enum):
    ACTIONS_PER_HOUR = "actions_per_hour"
    ACTIONS_PER_DAY = "actions_per_day"
    OUTBOUND_MESSAGES_PER_DAY = "outbound_messages_per_day"
    PUBLICATIONS_PER_DAY = "publications_per_day"
    MEMORY_WRITES_PER_DAY = "memory_writes_per_day"
    CONNECTOR_CALLS_PER_HOUR = "connector_calls_per_hour"
    DAILY_BUDGET = "daily_budget"


@dataclass
class _Counter:
    tenant_id: str
    dimension: str
    window_key: str
    used: float = 0.0
    updated_at: datetime = field(default_factory=utc_now)


class TenantQuotaGuard:
    def __init__(
        self,
        *,
        policy_store: TenantPolicyStoreContract | None = None,
    ) -> None:
        self._policy_store = policy_store
        self._counters: dict[tuple[str, str, str], _Counter] = {}
        self._lock = RLock()

    def check(
        self,
        *,
        tenant_id: str,
        dimension: str,
        amount: float = 1.0,
    ) -> TenantQuotaCheck:
        tid = require_tenant_id(tenant_id)
        dim = self._require_dimension(dimension)
        requested = self._require_amount(amount)
        with self._lock:
            return self._build_check_locked(tenant_id=tid, dimension=dim, amount=requested)

    def check_many(
        self,
        *,
        tenant_id: str,
        requests: Iterable[tuple[str, float]],
    ) -> dict[str, TenantQuotaCheck]:
        tid = require_tenant_id(tenant_id)
        prepared = [(self._require_dimension(d), self._require_amount(a)) for d, a in tuple(requests)]
        with self._lock:
            return {
                dimension: self._build_check_locked(tenant_id=tid, dimension=dimension, amount=amount)
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
        requested = self._require_amount(amount)
        with self._lock:
            verdict = self._build_check_locked(tenant_id=tid, dimension=dim, amount=requested)
            if not verdict.allowed:
                return verdict
            counter = self._counter_for_locked(tid, dim)
            counter.used += requested
            counter.updated_at = utc_now()
            return self._build_consumed_verdict_locked(counter=counter, requested=requested)

    def consume_many(
        self,
        *,
        tenant_id: str,
        requests: Iterable[tuple[str, float]],
    ) -> dict[str, TenantQuotaCheck]:
        tid = require_tenant_id(tenant_id)
        prepared = [(self._require_dimension(d), self._require_amount(a)) for d, a in tuple(requests)]
        with self._lock:
            checks = {
                dimension: self._build_check_locked(tenant_id=tid, dimension=dimension, amount=amount)
                for dimension, amount in prepared
            }
            failed = next((check for check in checks.values() if not check.allowed), None)
            if failed is not None:
                return checks
            consumed: dict[str, TenantQuotaCheck] = {}
            for dimension, amount in prepared:
                counter = self._counter_for_locked(tid, dimension)
                counter.used += amount
                counter.updated_at = utc_now()
                consumed[dimension] = self._build_consumed_verdict_locked(counter=counter, requested=amount)
            return consumed

    def reset(self, *, tenant_id: str, dimension: str | None = None) -> None:
        tid = require_tenant_id(tenant_id)
        with self._lock:
            if dimension is None:
                keys = [key for key in self._counters if key[0] == tid]
            else:
                dim = self._require_dimension(dimension)
                keys = [key for key in self._counters if key[0] == tid and key[1] == dim]
            for key in keys:
                self._counters.pop(key, None)

    def snapshot(self, *, tenant_id: str) -> dict[str, float]:
        tid = require_tenant_id(tenant_id)
        with self._lock:
            result: dict[str, float] = {}
            if self._policy_store is not None:
                bundle = self._policy_store.get(tid)
                if bundle is not None:
                    for dimension in sorted(dict(bundle.quotas).keys()):
                        result[str(dimension)] = 0.0
            for (counter_tid, dimension, _window_key), counter in self._counters.items():
                if counter_tid == tid:
                    result[dimension] = result.get(dimension, 0.0) + float(counter.used)
            return result

    def _build_check_locked(self, *, tenant_id: str, dimension: str, amount: float) -> TenantQuotaCheck:
        limit = self._limit_for_locked(tenant_id, dimension)
        counter = self._counters.get((tenant_id, dimension, self._window_key(dimension)))
        used = 0.0 if counter is None else float(counter.used)
        if limit is None:
            return TenantQuotaCheck(
                allowed=True,
                reason="no quota configured",
                tenant_id=tenant_id,
                dimension=dimension,
                requested=amount,
                used=used,
                limit=None,
                remaining=None,
                retry_after_seconds=None,
            )
        remaining = max(0.0, float(limit) - used)
        allowed = amount <= remaining
        return TenantQuotaCheck(
            allowed=allowed,
            reason="ok" if allowed else "quota exceeded",
            tenant_id=tenant_id,
            dimension=dimension,
            requested=amount,
            used=used,
            limit=float(limit),
            remaining=remaining,
            retry_after_seconds=None if allowed else self._retry_after_seconds(dimension),
        )

    def _build_consumed_verdict_locked(self, *, counter: _Counter, requested: float) -> TenantQuotaCheck:
        limit = self._limit_for_locked(counter.tenant_id, counter.dimension)
        remaining = None if limit is None else max(0.0, float(limit) - float(counter.used))
        return TenantQuotaCheck(
            allowed=True,
            reason="consumed",
            tenant_id=counter.tenant_id,
            dimension=counter.dimension,
            requested=requested,
            used=float(counter.used),
            limit=None if limit is None else float(limit),
            remaining=remaining,
            retry_after_seconds=None,
        )

    def _limit_for_locked(self, tenant_id: str, dimension: str) -> float | None:
        if self._policy_store is None:
            return None
        bundle = self._policy_store.get(tenant_id)
        if bundle is None:
            return None
        raw = bundle.quotas.get(dimension)
        if raw is None:
            return None
        return float(raw)

    def _counter_for_locked(self, tenant_id: str, dimension: str) -> _Counter:
        window_key = self._window_key(dimension)
        key = (tenant_id, dimension, window_key)
        current = self._counters.get(key)
        if current is None:
            current = _Counter(tenant_id=tenant_id, dimension=dimension, window_key=window_key)
            self._counters[key] = current
        return current

    @staticmethod
    def _require_dimension(dimension: str) -> str:
        dim = str(dimension or "").strip()
        if not dim:
            raise ValueError("dimension is required")
        return dim

    @staticmethod
    def _require_amount(amount: float) -> float:
        requested = float(amount)
        if requested < 0:
            raise ValueError("amount must be >= 0")
        return requested

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
