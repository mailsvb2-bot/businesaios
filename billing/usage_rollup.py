from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable, Mapping

from billing.usage_meter import UsageRecord
from core.finance.money import legacy_float, quantity_decimal
from core.tenancy.normalization import require_tenant_id


CANON_BILLING_USAGE_ROLLUP = True


def _utc_date_key(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("observed_at must be timezone-aware")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d")


@dataclass(frozen=True)
class UsageRollup:
    tenant_id: str
    meter_key: str
    window_key: str
    quantity: float
    labels: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized = quantity_decimal(self.quantity, name="quantity")
        object.__setattr__(self, "quantity", legacy_float(normalized, name="quantity"))

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.meter_key or "").strip():
            raise ValueError("meter_key is required")
        if not str(self.window_key or "").strip():
            raise ValueError("window_key is required")
        quantity_decimal(self.quantity, name="quantity")


class UsageRollupBuilder:
    def build_daily(self, records: Iterable[UsageRecord]) -> tuple[UsageRollup, ...]:
        buckets: dict[tuple[str, str, str], Decimal] = {}
        labels_by_bucket: dict[tuple[str, str, str], dict[str, str]] = {}
        for record in records:
            record.validate()
            observed_at = getattr(record, "recorded_at", None)
            if observed_at is None:
                raise ValueError("UsageRecord must expose recorded_at for rollup")
            window_key = _utc_date_key(observed_at)
            key = (record.tenant_id, record.meter_key, window_key)
            buckets[key] = buckets.get(key, Decimal("0")) + quantity_decimal(
                record.quantity,
                name="record_quantity",
            )
            labels_by_bucket.setdefault(key, {}).update(
                {str(k): str(v) for k, v in record.labels.items()}
            )
        result: list[UsageRollup] = []
        for (tenant_id, meter_key, window_key), quantity in sorted(buckets.items()):
            item = UsageRollup(
                tenant_id=tenant_id,
                meter_key=meter_key,
                window_key=window_key,
                quantity=legacy_float(
                    quantity_decimal(quantity, name="rollup_quantity"),
                    name="rollup_quantity",
                ),
                labels=labels_by_bucket.get(
                    (tenant_id, meter_key, window_key),
                    {},
                ),
            )
            item.validate()
            result.append(item)
        return tuple(result)


__all__ = ["CANON_BILLING_USAGE_ROLLUP", "UsageRollup", "UsageRollupBuilder"]
