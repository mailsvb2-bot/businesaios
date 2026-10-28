from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from billing.commercial_cycle_contract import SpendGuardVerdict, require_commercial_int
from billing.ledger_store import LedgerStoreContract
from core.tenancy.normalization import require_tenant_id
from observability.tenant_metrics_registry import TenantMetricsRegistry

CANON_BILLING_SPEND_GUARD = True


@dataclass(frozen=True)
class SpendLimitPolicy:
    tenant_id: str
    currency: str = "USD"
    cycle_limit_minor: int | None = None
    hard_stop: bool = True
    metadata: Mapping[str, object] = field(default_factory=dict)
    cycle_started_at: datetime | None = None

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if self.cycle_limit_minor is not None:
            require_commercial_int(
                "cycle_limit_minor",
                self.cycle_limit_minor,
                minimum=0,
            )
        if not isinstance(self.hard_stop, bool):
            raise ValueError("hard_stop must be a boolean")
        if not str(self.currency or "").strip():
            raise ValueError("currency is required")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be a mapping")
        if self.cycle_started_at is not None and self.cycle_started_at.tzinfo is None:
            raise ValueError('cycle_started_at must be timezone-aware')


class SpendGuard:
    def __init__(
        self,
        *,
        ledger_store: LedgerStoreContract,
        metrics: TenantMetricsRegistry | None = None,
    ) -> None:
        self._ledger_store = ledger_store
        self._metrics = metrics

    def check(
        self,
        *,
        policy: SpendLimitPolicy,
        pending_minor: int,
        revenue_account: str = "billing.accounts.revenue",
        now: datetime | None = None,
    ) -> SpendGuardVerdict:
        policy.validate()
        moment = now or datetime.now(UTC)
        if moment.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        cycle_start = policy.cycle_started_at or moment.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        delta_minor = require_commercial_int(
            "pending_minor",
            pending_minor,
            minimum=0,
        )
        revenue_currencies, observed_minor = self._cycle_revenue(
            tenant_id=policy.tenant_id, account_code=revenue_account,
            cycle_started_at=cycle_start,
        )
        policy_currency = str(policy.currency).strip().upper()
        if revenue_currencies and revenue_currencies != {policy_currency}:
            verdict = SpendGuardVerdict(
                tenant_id=policy.tenant_id,
                allowed=False,
                projected_minor=0,
                limit_minor=policy.cycle_limit_minor,
                remaining_minor=None,
                reason="mixed_currency_ledger",
                metadata={
                    "observed_currencies": sorted(revenue_currencies),
                    "policy_currency": policy_currency,
                    **dict(policy.metadata),
                },
            )
            verdict.validate()
            return verdict
        projected_total = observed_minor + delta_minor
        limit_minor = policy.cycle_limit_minor
        remaining_after_pending = None if limit_minor is None else max(0, limit_minor - projected_total)
        allowed = limit_minor is None or projected_total <= limit_minor or not policy.hard_stop
        reason = "ok"
        if limit_minor is not None and projected_total > limit_minor:
            reason = "spend_limit_soft_exceeded" if not policy.hard_stop else "spend_limit_exceeded"
        verdict = SpendGuardVerdict(
            tenant_id=policy.tenant_id,
            allowed=allowed,
            projected_minor=projected_total,
            limit_minor=limit_minor,
            remaining_minor=remaining_after_pending,
            reason=reason,
            metadata={
                "observed_minor": observed_minor,
                "pending_minor": delta_minor,
                "cycle_started_at": cycle_start.isoformat(),
                "currency": policy_currency,
                **dict(policy.metadata),
            },
        )
        verdict.validate()
        if self._metrics is not None:
            self._metrics.set_gauge(
                tenant_id=policy.tenant_id,
                metric_name="billing_spend_projected_minor",
                value=float(projected_total),
                labels={"reason": reason},
            )
        return verdict

    def _cycle_revenue(self, *, tenant_id: str, account_code: str, cycle_started_at: datetime) -> tuple[set[str], int]:
        currencies: set[str] = set()
        total = 0
        for posting in self._ledger_store.list_postings(tenant_id=tenant_id):
            for entry in posting.entries:
                if entry.account_code != account_code:
                    continue
                currencies.add(str(entry.currency).strip().upper())
                if str(entry.side).strip().lower() != 'credit':
                    continue
                booked_at = getattr(entry, 'booked_at', None)
                # Unknown timestamps count conservatively.
                if isinstance(booked_at, datetime) and booked_at.tzinfo is not None and booked_at < cycle_started_at:
                    continue
                total += require_commercial_int('amount_minor', entry.amount_minor, minimum=0)
        return currencies, require_commercial_int('observed_minor', total, minimum=0)


__all__ = ["CANON_BILLING_SPEND_GUARD", "SpendGuard", "SpendLimitPolicy"]
