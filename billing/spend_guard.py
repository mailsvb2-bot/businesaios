from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from billing.commercial_cycle_contract import SpendGuardVerdict
from billing.ledger_store import LedgerStoreContract
from core.tenancy.normalization import require_tenant_id
from observability.tenant_metrics_registry import TenantMetricsRegistry

CANON_BILLING_SPEND_GUARD = True


@dataclass(frozen=True)
class SpendLimitPolicy:
    tenant_id: str
    currency: str = 'USD'
    cycle_limit_minor: int | None = None
    hard_stop: bool = True
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if self.cycle_limit_minor is not None and int(self.cycle_limit_minor) < 0:
            raise ValueError('cycle_limit_minor must be >= 0')
        if not str(self.currency or '').strip():
            raise ValueError('currency is required')


class SpendGuard:
    def __init__(self, *, ledger_store: LedgerStoreContract, metrics: TenantMetricsRegistry | None = None) -> None:
        self._ledger_store = ledger_store
        self._metrics = metrics

    def check(self, *, policy: SpendLimitPolicy, pending_minor: int, revenue_account: str = 'billing.accounts.revenue') -> SpendGuardVerdict:
        policy.validate()
        delta_minor = int(pending_minor)
        if delta_minor < 0:
            raise ValueError('pending_minor must be >= 0')
        revenue_currencies = self._account_currencies(tenant_id=policy.tenant_id, account_code=revenue_account)
        policy_currency = str(policy.currency).strip().upper()
        if revenue_currencies and revenue_currencies != {policy_currency}:
            verdict = SpendGuardVerdict(
                tenant_id=policy.tenant_id,
                allowed=False,
                projected_minor=0,
                limit_minor=None if policy.cycle_limit_minor is None else int(policy.cycle_limit_minor),
                remaining_minor=None,
                reason='mixed_currency_ledger',
                metadata={'observed_currencies': sorted(revenue_currencies), 'policy_currency': policy_currency, **dict(policy.metadata)},
            )
            verdict.validate()
            return verdict
        observed_minor = self._ledger_store.total_for_account(tenant_id=policy.tenant_id, account_code=revenue_account, side='credit')
        projected_total = observed_minor + delta_minor
        limit_minor = None if policy.cycle_limit_minor is None else int(policy.cycle_limit_minor)
        remaining_after_pending = None if limit_minor is None else max(0, limit_minor - projected_total)
        allowed = limit_minor is None or projected_total <= limit_minor or not policy.hard_stop
        reason = 'ok'
        if limit_minor is not None and projected_total > limit_minor:
            reason = 'spend_limit_soft_exceeded' if not policy.hard_stop else 'spend_limit_exceeded'
        verdict = SpendGuardVerdict(
            tenant_id=policy.tenant_id,
            allowed=allowed,
            projected_minor=projected_total,
            limit_minor=limit_minor,
            remaining_minor=remaining_after_pending,
            reason=reason,
            metadata={'observed_minor': observed_minor, 'pending_minor': delta_minor, 'currency': policy_currency, **dict(policy.metadata)},
        )
        verdict.validate()
        if self._metrics is not None:
            self._metrics.set_gauge(tenant_id=policy.tenant_id, metric_name='billing_spend_projected_minor', value=float(projected_total), labels={'reason': reason})
        return verdict

    def _account_currencies(self, *, tenant_id: str, account_code: str) -> set[str]:
        currencies: set[str] = set()
        for posting in self._ledger_store.list_postings(tenant_id=tenant_id):
            for entry in posting.entries:
                if entry.account_code == account_code:
                    currencies.add(str(entry.currency).strip().upper())
        return currencies


__all__ = ['CANON_BILLING_SPEND_GUARD', 'SpendGuard', 'SpendLimitPolicy']
