from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from core.tenancy.normalization import require_tenant_id
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


@dataclass
class _LocalConnectorCounter:
    tenant_id: str
    connector_id: str
    window_key: str
    used: float = 0.0
    updated_at: datetime = field(default_factory=utc_now)


class ConnectorQuotaGuard:
    def __init__(
        self,
        *,
        quota_guard: TenantQuotaGuard | None = None,
        per_connector_hour_limit: float | None = None,
    ) -> None:
        if per_connector_hour_limit is not None and float(per_connector_hour_limit) <= 0:
            raise ValueError('per_connector_hour_limit must be > 0 when provided')
        self._quota_guard = quota_guard or TenantQuotaGuard()
        self._per_connector_hour_limit = None if per_connector_hour_limit is None else float(per_connector_hour_limit)
        self._local_counters: dict[tuple[str, str, str], _LocalConnectorCounter] = {}

    def check(self, *, tenant_id: str, connector_id: str, requested_calls: float = 1.0) -> ConnectorQuotaVerdict:
        tid = require_tenant_id(tenant_id)
        cid = str(connector_id or '').strip()
        amount = float(requested_calls)
        if not cid:
            raise ValueError('connector_id is required')
        if amount <= 0:
            raise ValueError('requested_calls must be > 0')
        self._prune_stale_windows()
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
        counter = self._counter_for(tenant_id=tid, connector_id=cid)
        counter.used += amount
        counter.updated_at = utc_now()
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

    def _counter_for(self, *, tenant_id: str, connector_id: str) -> _LocalConnectorCounter:
        key = (tenant_id, connector_id, self._window_key())
        counter = self._local_counters.get(key)
        if counter is None:
            counter = _LocalConnectorCounter(tenant_id=tenant_id, connector_id=connector_id, window_key=key[2])
            self._local_counters[key] = counter
        return counter

    def _local_remaining(self, *, tenant_id: str, connector_id: str) -> float | None:
        if self._per_connector_hour_limit is None:
            return None
        counter = self._counter_for(tenant_id=tenant_id, connector_id=connector_id)
        return max(0.0, self._per_connector_hour_limit - float(counter.used))

    def _prune_stale_windows(self) -> None:
        current_window = self._window_key()
        stale = [key for key in self._local_counters if key[2] != current_window]
        for key in stale:
            self._local_counters.pop(key, None)


__all__ = [
    'CANON_CONNECTOR_QUOTA_GUARD',
    'ConnectorQuotaGuard',
    'ConnectorQuotaVerdict',
]
