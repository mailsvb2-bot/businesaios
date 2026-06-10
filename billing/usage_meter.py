from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Iterable, Mapping, Protocol

from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_contract import utc_now

CANON_USAGE_METER = True


@dataclass(frozen=True)
class UsageRecord:
    tenant_id: str
    meter_key: str
    quantity: float
    recorded_at: datetime = field(default_factory=utc_now)
    window_key: str | None = None
    idempotency_key: str | None = None
    labels: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.meter_key or "").strip():
            raise ValueError("meter_key is required")
        if float(self.quantity) < 0:
            raise ValueError("quantity must be >= 0")
        if self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")

    def normalized_copy(self) -> "UsageRecord":
        self.validate()
        return replace(
            self,
            tenant_id=require_tenant_id(self.tenant_id),
            meter_key=str(self.meter_key).strip(),
            quantity=float(self.quantity),
            window_key=None if self.window_key is None else str(self.window_key),
            idempotency_key=None if self.idempotency_key is None else str(self.idempotency_key),
            labels={str(k): str(v) for k, v in dict(self.labels).items()},
            metadata=dict(self.metadata),
        )


class UsageMeterContract(Protocol):
    def record(self, record: UsageRecord) -> UsageRecord: ...
    def total(self, *, tenant_id: str, meter_key: str, window_key: str | None = None) -> float: ...
    def snapshot(self, *, tenant_id: str) -> dict[str, float]: ...
    def iter_records(self, *, tenant_id: str | None = None, meter_key: str | None = None) -> Iterable[UsageRecord]: ...


class InMemoryUsageMeter(UsageMeterContract):
    def __init__(self) -> None:
        self._records: list[UsageRecord] = []
        self._idempotency_index: dict[tuple[str, str, str], UsageRecord] = {}

    def record(self, record: UsageRecord) -> UsageRecord:
        normalized = record.normalized_copy()
        if normalized.idempotency_key:
            idem_key = (
                normalized.tenant_id,
                normalized.meter_key,
                normalized.idempotency_key,
            )
            existing = self._idempotency_index.get(idem_key)
            if existing is not None:
                return existing.normalized_copy()
            self._idempotency_index[idem_key] = normalized
        self._records.append(normalized)
        return normalized.normalized_copy()

    def meter(
        self,
        *,
        tenant_id: str,
        meter_key: str,
        quantity: float,
        window_key: str | None = None,
        recorded_at: datetime | None = None,
        idempotency_key: str | None = None,
        labels: Mapping[str, str] | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> UsageRecord:
        return self.record(
            UsageRecord(
                tenant_id=require_tenant_id(tenant_id),
                meter_key=str(meter_key or "").strip(),
                quantity=float(quantity),
                window_key=window_key,
                recorded_at=recorded_at or utc_now(),
                idempotency_key=None if idempotency_key is None else str(idempotency_key),
                labels={str(k): str(v) for k, v in dict(labels or {}).items()},
                metadata=dict(metadata or {}),
            )
        )

    def total(self, *, tenant_id: str, meter_key: str, window_key: str | None = None) -> float:
        tid = require_tenant_id(tenant_id)
        key = str(meter_key or "").strip()
        if not key:
            raise ValueError("meter_key is required")
        return round(
            sum(
                float(item.quantity)
                for item in self._records
                if item.tenant_id == tid
                and item.meter_key == key
                and (window_key is None or item.window_key == window_key)
            ),
            6,
        )

    def snapshot(self, *, tenant_id: str) -> dict[str, float]:
        tid = require_tenant_id(tenant_id)
        result: dict[str, float] = {}
        for item in self._records:
            if item.tenant_id != tid:
                continue
            result[item.meter_key] = round(result.get(item.meter_key, 0.0) + float(item.quantity), 6)
        return result

    def iter_records(self, *, tenant_id: str | None = None, meter_key: str | None = None) -> tuple[UsageRecord, ...]:
        tid = None if tenant_id is None else require_tenant_id(tenant_id)
        normalized_meter_key = None if meter_key is None else str(meter_key or "").strip()
        return tuple(
            item.normalized_copy()
            for item in self._records
            if (tid is None or item.tenant_id == tid)
            and (normalized_meter_key is None or item.meter_key == normalized_meter_key)
        )

    @staticmethod
    def hourly_window_key(moment: datetime | None = None) -> str:
        value = moment or datetime.now(timezone.utc)
        return value.strftime("%Y%m%d%H")

    @staticmethod
    def daily_window_key(moment: datetime | None = None) -> str:
        value = moment or datetime.now(timezone.utc)
        return value.strftime("%Y%m%d")


__all__ = [
    "CANON_USAGE_METER",
    "InMemoryUsageMeter",
    "UsageMeterContract",
    "UsageRecord",
]
