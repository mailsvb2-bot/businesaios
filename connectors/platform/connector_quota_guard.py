from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from core.finance.money import quantity_decimal
from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_quota_counter_store import (
    InMemoryTenantQuotaCounterStore,
    TenantQuotaCounterStore,
)
from tenancy.tenant_quota_guard import QuotaDimension, TenantQuotaGuard


CANON_CONNECTOR_QUOTA_GUARD = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ConnectorQuotaVerdict:
    allowed: bool
    tenant_id: str
    connector_id: str
    requested_calls: float
    remaining: float | None
    reason: str
    retry_after_seconds: int | None = None


class ConnectorQuotaGuard:
    def __init__(
        self,
        *,
        quota_guard: TenantQuotaGuard | None = None,
        per_connector_hour_limit: float | None = None,
        counter_store: TenantQuotaCounterStore | None = None,
    ) -> None:
        if per_connector_hour_limit is not None and float(per_connector_hour_limit) <= 0:
            raise ValueError('per_connector_hour_limit must be > 0 when provided')
        inherited_store = None if quota_guard is None else quota_guard.counter_store
        if counter_store is not None and inherited_store is not None and counter_store is not inherited_store:
            raise ValueError("quota_guard and connector quota must share one counter_store")
        self._counter_store = counter_store or inherited_store or InMemoryTenantQuotaCounterStore()
        self._quota_guard = quota_guard or TenantQuotaGuard(counter_store=self._counter_store)
        self._per_connector_hour_limit = None if per_connector_hour_limit is None else float(per_connector_hour_limit)

    def check(self, *, tenant_id: str, connector_id: str, requested_calls: float = 1.0) -> ConnectorQuotaVerdict:
        tid = require_tenant_id(tenant_id)
        cid = str(connector_id or '').strip()
        amount = float(requested_calls)
        if not cid:
            raise ValueError('connector_id is required')
        if amount <= 0:
            raise ValueError('requested_calls must be > 0')
        tenant_verdict = self._quota_guard.check(
            tenant_id=tid,
            dimension=QuotaDimension.CONNECTOR_CALLS_PER_HOUR.value,
            amount=amount,
        )
        local_remaining = self._local_remaining(tenant_id=tid, connector_id=cid)
        allowed = bool(tenant_verdict.allowed) and (local_remaining is None or amount <= local_remaining)
        remaining_candidates = [value for value in (tenant_verdict.remaining, local_remaining) if value is not None]
        remaining = min(remaining_candidates) if remaining_candidates else None
        reason = str(tenant_verdict.reason)
        retry_after_seconds = tenant_verdict.retry_after_seconds
        if allowed:
            reason = 'ok'
            retry_after_seconds = None
        elif local_remaining is not None and amount > local_remaining:
            reason = 'connector_local_quota_exceeded'
            retry_after_seconds = 3600
        return ConnectorQuotaVerdict(
            allowed=allowed,
            tenant_id=tid,
            connector_id=cid,
            requested_calls=amount,
            remaining=None if remaining is None else float(remaining),
            reason=reason,
            retry_after_seconds=retry_after_seconds,
        )

    def consume(self, *, tenant_id: str, connector_id: str, requested_calls: float = 1.0) -> ConnectorQuotaVerdict:
        verdict = self.check(tenant_id=tenant_id, connector_id=connector_id, requested_calls=requested_calls)
        if not verdict.allowed:
            return verdict
        tid = require_tenant_id(tenant_id)
        cid = str(connector_id or '').strip()
        amount = float(requested_calls)
        tenant_post = self._quota_guard.consume(
            tenant_id=tid,
            dimension=QuotaDimension.CONNECTOR_CALLS_PER_HOUR.value,
            amount=amount,
        )
        self._consume_local(tenant_id=tid, connector_id=cid, amount=amount)
        local_remaining = self._local_remaining(tenant_id=tid, connector_id=cid)
        remaining_candidates = [value for value in (tenant_post.remaining, local_remaining) if value is not None]
        remaining = min(remaining_candidates) if remaining_candidates else None
        return ConnectorQuotaVerdict(
            allowed=True,
            tenant_id=tid,
            connector_id=cid,
            requested_calls=amount,
            remaining=None if remaining is None else float(remaining),
            reason='consumed',
            retry_after_seconds=None,
        )

    def _window_key(self) -> str:
        return datetime.now(timezone.utc).strftime('%Y%m%d%H')

    @staticmethod
    def _counter_key(connector_id: str) -> str:
        return f"connector:{connector_id}:calls_per_hour"

    def _local_used(self, *, tenant_id: str, connector_id: str) -> float:
        state = self._counter_store.get(
            tenant_id=tenant_id,
            counter_key=self._counter_key(connector_id),
            window_key=self._window_key(),
        )
        return 0.0 if state is None else float(state.used)

    def _consume_local(self, *, tenant_id: str, connector_id: str, amount: float) -> None:
        window_key = self._window_key()
        counter_key = self._counter_key(connector_id)
        self._counter_store.increment(
            tenant_id=tenant_id,
            counter_key=counter_key,
            window_key=window_key,
            amount=quantity_decimal(amount, name="requested_calls"),
            updated_at=utc_now(),
        )

    def _local_remaining(self, *, tenant_id: str, connector_id: str) -> float | None:
        if self._per_connector_hour_limit is None:
            return None
        return max(0.0, self._per_connector_hour_limit - self._local_used(tenant_id=tenant_id, connector_id=connector_id))


__all__ = [
    'CANON_CONNECTOR_QUOTA_GUARD',
    'ConnectorQuotaGuard',
    'ConnectorQuotaVerdict',
]
