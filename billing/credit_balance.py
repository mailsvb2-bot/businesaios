from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping

from core.tenancy.normalization import require_tenant_id

CANON_BILLING_CREDIT_BALANCE = True


@dataclass(frozen=True)
class CreditBalance:
    tenant_id: str
    currency: str
    available_minor: int = 0
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.currency or '').strip():
            raise ValueError('currency is required')
        if int(self.available_minor) < 0:
            raise ValueError('available_minor must be >= 0')

    def normalized_copy(self) -> 'CreditBalance':
        self.validate()
        return replace(self, currency=str(self.currency).strip().upper(), metadata=dict(self.metadata), available_minor=int(self.available_minor))


class InMemoryCreditBalanceStore:
    def __init__(self) -> None:
        self._balances: dict[tuple[str, str], CreditBalance] = {}

    def get(self, *, tenant_id: str, currency: str) -> CreditBalance:
        tid = require_tenant_id(tenant_id)
        curr = str(currency or '').strip().upper()
        if not curr:
            raise ValueError('currency is required')
        existing = self._balances.get((tid, curr))
        if existing is None:
            return CreditBalance(tenant_id=tid, currency=curr)
        return existing.normalized_copy()

    def add(self, *, tenant_id: str, currency: str, amount_minor: int, metadata: Mapping[str, object] | None = None) -> CreditBalance:
        delta = int(amount_minor)
        if delta < 0:
            raise ValueError('amount_minor must be >= 0')
        current = self.get(tenant_id=tenant_id, currency=currency)
        updated = CreditBalance(
            tenant_id=current.tenant_id,
            currency=current.currency,
            available_minor=current.available_minor + delta,
            metadata={**dict(current.metadata), **dict(metadata or {})},
        ).normalized_copy()
        self._balances[(updated.tenant_id, updated.currency)] = updated
        return updated.normalized_copy()

    def consume(self, *, tenant_id: str, currency: str, amount_minor: int, metadata: Mapping[str, object] | None = None) -> CreditBalance:
        requested = int(amount_minor)
        if requested < 0:
            raise ValueError('amount_minor must be >= 0')
        current = self.get(tenant_id=tenant_id, currency=currency)
        if requested > current.available_minor:
            raise ValueError('insufficient credit balance')
        updated = CreditBalance(
            tenant_id=current.tenant_id,
            currency=current.currency,
            available_minor=current.available_minor - requested,
            metadata={**dict(current.metadata), **dict(metadata or {})},
        ).normalized_copy()
        self._balances[(updated.tenant_id, updated.currency)] = updated
        return updated.normalized_copy()


__all__ = ['CANON_BILLING_CREDIT_BALANCE', 'CreditBalance', 'InMemoryCreditBalanceStore']
