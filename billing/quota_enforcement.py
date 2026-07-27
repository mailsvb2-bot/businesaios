from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping

from billing.money import legacy_float, quantity_decimal
from billing.quota_policy import EffectiveQuotaPolicy, QuotaPolicyResolver
from billing.usage_meter import UsageMeterContract
from core.tenancy.normalization import require_tenant_id
from observability.tenant_metrics_registry import TenantMetricsRegistry
from tenancy.tenant_quota_guard import TenantQuotaGuard


CANON_QUOTA_ENFORCEMENT = True


@dataclass(frozen=True)
class QuotaEnforcementDecision:
    tenant_id: str
    dimension: str
    requested: float
    allowed: bool
    used: float
    limit: float | None
    remaining: float | None
    reason: str
    hard_stop: bool
    meter_key: str | None = None
    metered: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)


class QuotaEnforcer:
    """Commercial wrapper around the canonical tenant quota guard.

    Quota quantities are decimal-exact. Floats are materialized only for the
    established DTO and metrics boundaries.
    """

    def __init__(
        self,
        *,
        tenant_quota_guard: TenantQuotaGuard,
        quota_policy: QuotaPolicyResolver,
        usage_meter: UsageMeterContract | None = None,
        metrics: TenantMetricsRegistry | None = None,
    ) -> None:
        self._tenant_quota_guard = tenant_quota_guard
        self._quota_policy = quota_policy
        self._usage_meter = usage_meter
        self._metrics = metrics

    def check(
        self,
        *,
        tenant_id: str,
        dimension: str,
        amount: float = 1.0,
        meter_key: str | None = None,
    ) -> QuotaEnforcementDecision:
        tid = require_tenant_id(tenant_id)
        dim = str(dimension or "").strip()
        if not dim:
            raise ValueError("dimension is required")
        requested = quantity_decimal(amount, name="amount")

        policy = self._quota_policy.resolve(tenant_id=tid)
        guard_verdict = self._tenant_quota_guard.check(
            tenant_id=tid,
            dimension=dim,
            amount=0.0,
        )
        decision = self._check_decision(
            tenant_id=tid,
            dimension=dim,
            requested=requested,
            meter_key=meter_key,
            policy=policy,
            used=quantity_decimal(guard_verdict.used, name="used"),
            extra_metadata={
                "guard_limit_materialized": guard_verdict.limit is not None,
            },
        )
        self._emit_metrics(decision)
        return decision

    def consume(
        self,
        *,
        tenant_id: str,
        dimension: str,
        amount: float = 1.0,
        meter_key: str | None = None,
        idempotency_key: str | None = None,
        labels: Mapping[str, str] | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> QuotaEnforcementDecision:
        tid = require_tenant_id(tenant_id)
        dim = str(dimension or "").strip()
        if not dim:
            raise ValueError("dimension is required")
        requested = quantity_decimal(amount, name="amount")

        policy = self._quota_policy.resolve(tenant_id=tid)
        guard_used = self._tenant_quota_guard.check(
            tenant_id=tid,
            dimension=dim,
            amount=0.0,
        ).used
        preflight = self._check_decision(
            tenant_id=tid,
            dimension=dim,
            requested=requested,
            meter_key=meter_key,
            policy=policy,
            used=quantity_decimal(guard_used, name="used"),
            extra_metadata={
                "guard_limit_materialized": True,
                **dict(metadata or {}),
            },
        )
        if not preflight.allowed:
            self._emit_metrics(preflight)
            return preflight

        guard_verdict = self._tenant_quota_guard.consume(
            tenant_id=tid,
            dimension=dim,
            amount=legacy_float(requested, name="requested"),
        )
        metered = False
        if self._usage_meter is not None and meter_key:
            self._usage_meter.record(
                record=self._build_usage_record(
                    tenant_id=tid,
                    meter_key=str(meter_key),
                    quantity=requested,
                    dimension=dim,
                    idempotency_key=idempotency_key,
                    labels=labels,
                    metadata=metadata,
                )
            )
            metered = True

        decision = self._consumed_decision(
            tenant_id=tid,
            dimension=dim,
            requested=requested,
            meter_key=meter_key,
            policy=policy,
            used=quantity_decimal(guard_verdict.used, name="used"),
            metered=metered,
            extra_metadata={
                "guard_limit_materialized": guard_verdict.limit is not None,
                **dict(metadata or {}),
            },
        )
        self._emit_metrics(decision)
        return decision

    def _check_decision(
        self,
        *,
        tenant_id: str,
        dimension: str,
        requested: Decimal,
        meter_key: str | None,
        policy: EffectiveQuotaPolicy,
        used: Decimal,
        extra_metadata: Mapping[str, object] | None = None,
    ) -> QuotaEnforcementDecision:
        raw_limit = policy.limit_for(dimension)
        limit = (
            None
            if raw_limit is None
            else quantity_decimal(raw_limit, name="limit")
        )
        hard_stop = policy.hard_stop_for(dimension)
        remaining = None if limit is None else max(Decimal("0"), limit - used)
        allowed = True
        reason = "ok"
        if limit is not None and requested > remaining:
            if hard_stop or not policy.allow_overage:
                allowed = False
                reason = "quota exceeded"
            else:
                reason = "overage allowed"
        return self._make_decision(
            tenant_id=tenant_id,
            dimension=dimension,
            requested=requested,
            allowed=allowed,
            used=used,
            limit=limit,
            remaining=remaining,
            reason=reason,
            hard_stop=hard_stop,
            meter_key=meter_key,
            metered=False,
            policy=policy,
            overage_amount=Decimal("0"),
            extra_metadata=extra_metadata,
        )

    def _consumed_decision(
        self,
        *,
        tenant_id: str,
        dimension: str,
        requested: Decimal,
        meter_key: str | None,
        policy: EffectiveQuotaPolicy,
        used: Decimal,
        metered: bool,
        extra_metadata: Mapping[str, object] | None = None,
    ) -> QuotaEnforcementDecision:
        raw_limit = policy.limit_for(dimension)
        limit = (
            None
            if raw_limit is None
            else quantity_decimal(raw_limit, name="limit")
        )
        hard_stop = policy.hard_stop_for(dimension)
        remaining = None if limit is None else max(Decimal("0"), limit - used)
        overage_amount = (
            Decimal("0")
            if limit is None
            else max(Decimal("0"), used - limit)
        )
        reason = "consumed"
        if overage_amount > 0:
            reason = (
                "overage allowed"
                if policy.allow_overage and not hard_stop
                else "quota exceeded"
            )
        return self._make_decision(
            tenant_id=tenant_id,
            dimension=dimension,
            requested=requested,
            allowed=True,
            used=used,
            limit=limit,
            remaining=remaining,
            reason=reason,
            hard_stop=hard_stop,
            meter_key=meter_key,
            metered=metered,
            policy=policy,
            overage_amount=overage_amount,
            extra_metadata=extra_metadata,
        )

    def _make_decision(
        self,
        *,
        tenant_id: str,
        dimension: str,
        requested: Decimal,
        allowed: bool,
        used: Decimal,
        limit: Decimal | None,
        remaining: Decimal | None,
        reason: str,
        hard_stop: bool,
        meter_key: str | None,
        metered: bool,
        policy: EffectiveQuotaPolicy,
        overage_amount: Decimal,
        extra_metadata: Mapping[str, object] | None = None,
    ) -> QuotaEnforcementDecision:
        return QuotaEnforcementDecision(
            tenant_id=tenant_id,
            dimension=dimension,
            requested=legacy_float(requested, name="requested"),
            allowed=allowed,
            used=legacy_float(used, name="used"),
            limit=(
                None
                if limit is None
                else legacy_float(limit, name="limit")
            ),
            remaining=(
                None
                if remaining is None
                else legacy_float(remaining, name="remaining")
            ),
            reason=str(reason),
            hard_stop=hard_stop,
            meter_key=None if meter_key is None else str(meter_key),
            metered=metered,
            metadata={
                "plan_id": policy.plan_id,
                "billing_mode": policy.billing_mode.value,
                "allow_overage": policy.allow_overage,
                "invoice_enabled": policy.invoice_enabled,
                "policy_metadata": dict(policy.metadata),
                "overage_amount": legacy_float(
                    overage_amount,
                    name="overage_amount",
                ),
                **dict(extra_metadata or {}),
            },
        )

    def _build_usage_record(
        self,
        *,
        tenant_id: str,
        meter_key: str,
        quantity: Decimal,
        dimension: str,
        idempotency_key: str | None,
        labels: Mapping[str, str] | None,
        metadata: Mapping[str, object] | None,
    ):
        from billing.usage_meter import UsageRecord

        return UsageRecord(
            tenant_id=tenant_id,
            meter_key=meter_key,
            quantity=legacy_float(quantity, name="quantity"),
            idempotency_key=idempotency_key,
            labels={str(k): str(v) for k, v in dict(labels or {}).items()},
            metadata={"dimension": dimension, **dict(metadata or {})},
        )

    def _emit_metrics(self, decision: QuotaEnforcementDecision) -> None:
        if self._metrics is None:
            return
        labels = {
            "dimension": decision.dimension,
            "allowed": "true" if decision.allowed else "false",
            "hard_stop": "true" if decision.hard_stop else "false",
            "meter_key": "" if decision.meter_key is None else decision.meter_key,
            "metered": "true" if decision.metered else "false",
        }
        self._metrics.inc(
            tenant_id=decision.tenant_id,
            metric_name="billing.quota.requests",
            amount=1.0,
            labels=labels,
        )
        self._metrics.set_gauge(
            tenant_id=decision.tenant_id,
            metric_name=f"billing.quota.used.{decision.dimension}",
            value=decision.used,
            labels=labels,
        )
        if decision.limit is not None:
            self._metrics.set_gauge(
                tenant_id=decision.tenant_id,
                metric_name=f"billing.quota.remaining.{decision.dimension}",
                value=0.0 if decision.remaining is None else decision.remaining,
                labels=labels,
            )


__all__ = [
    "CANON_QUOTA_ENFORCEMENT",
    "QuotaEnforcementDecision",
    "QuotaEnforcer",
]
