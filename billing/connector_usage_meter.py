from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from billing.plan_contract import BillingMeterKey
from billing.quota_enforcement import QuotaEnforcementDecision, QuotaEnforcer
from billing.usage_meter import UsageMeterContract, UsageRecord
from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_quota_guard import QuotaDimension

CANON_CONNECTOR_USAGE_METER = True


@dataclass(frozen=True)
class ConnectorUsageRecord:
    tenant_id: str
    connector_id: str
    operation: str
    quantity: float = 1.0
    idempotency_key: str | None = None
    labels: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.connector_id or "").strip():
            raise ValueError("connector_id is required")
        if not str(self.operation or "").strip():
            raise ValueError("operation is required")
        if float(self.quantity) < 0:
            raise ValueError("quantity must be >= 0")


class ConnectorUsageMeter:
    """Thin commercial metering adapter for connector operations.

    Important invariants:
    - if `quota_enforcer` is present, it is the only component allowed to both
      consume quota and meter the successful event
    - idempotent repeats must be returned from the usage meter before any new
      quota consumption is attempted
    """

    def __init__(
        self,
        *,
        usage_meter: UsageMeterContract,
        quota_enforcer: QuotaEnforcer | None = None,
    ) -> None:
        self._usage_meter = usage_meter
        self._quota_enforcer = quota_enforcer

    def record(self, record: ConnectorUsageRecord) -> UsageRecord:
        record.validate()
        existing = self._find_existing(record)
        if existing is not None:
            return existing

        labels = {
            "connector_id": record.connector_id,
            "operation": record.operation,
            **{str(k): str(v) for k, v in dict(record.labels).items()},
        }
        metadata = {
            "connector_id": record.connector_id,
            "operation": record.operation,
            **dict(record.metadata),
        }
        if self._quota_enforcer is not None:
            decision = self._quota_enforcer.consume(
                tenant_id=record.tenant_id,
                dimension=QuotaDimension.CONNECTOR_CALLS_PER_HOUR.value,
                amount=float(record.quantity),
                meter_key=BillingMeterKey.CONNECTOR_CALLS,
                idempotency_key=record.idempotency_key,
                labels=labels,
                metadata=metadata,
            )
            if not decision.allowed:
                raise PermissionError(
                    f"connector quota exceeded for tenant={record.tenant_id} connector={record.connector_id}: {decision.reason}"
                )
            refreshed = self._find_existing(record)
            if refreshed is not None:
                return refreshed

        return self._usage_meter.record(
            UsageRecord(
                tenant_id=record.tenant_id,
                meter_key=BillingMeterKey.CONNECTOR_CALLS,
                quantity=float(record.quantity),
                idempotency_key=record.idempotency_key,
                labels=labels,
                metadata=metadata,
            )
        )

    def preflight(
        self,
        *,
        tenant_id: str,
        connector_id: str,
        quantity: float = 1.0,
    ) -> QuotaEnforcementDecision | None:
        if self._quota_enforcer is None:
            return None
        return self._quota_enforcer.check(
            tenant_id=tenant_id,
            dimension=QuotaDimension.CONNECTOR_CALLS_PER_HOUR.value,
            amount=float(quantity),
            meter_key=BillingMeterKey.CONNECTOR_CALLS,
        )

    def _find_existing(self, record: ConnectorUsageRecord) -> UsageRecord | None:
        if not record.idempotency_key:
            return None
        for item in reversed(
            tuple(
                self._usage_meter.iter_records(
                    tenant_id=record.tenant_id,
                    meter_key=BillingMeterKey.CONNECTOR_CALLS,
                )
            )
        ):
            if item.idempotency_key == record.idempotency_key:
                return item
        return None


__all__ = [
    "CANON_CONNECTOR_USAGE_METER",
    "ConnectorUsageMeter",
    "ConnectorUsageRecord",
]
