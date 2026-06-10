from __future__ import annotations

from typing import Protocol

from billing.ledger_event import LedgerPosting
from core.tenancy.normalization import require_tenant_id

CANON_BILLING_LEDGER_STORE = True


class LedgerStoreContract(Protocol):
    def append(self, posting: LedgerPosting) -> LedgerPosting: ...
    def list_postings(self, *, tenant_id: str) -> tuple[LedgerPosting, ...]: ...
    def total_for_account(self, *, tenant_id: str, account_code: str, side: str | None = None) -> int: ...


class InMemoryLedgerStore(LedgerStoreContract):
    def __init__(self) -> None:
        self._postings: dict[str, list[LedgerPosting]] = {}
        self._posting_index: dict[tuple[str, str], LedgerPosting] = {}

    def append(self, posting: LedgerPosting) -> LedgerPosting:
        posting.validate()
        key = (posting.tenant_id, posting.posting_id)
        existing = self._posting_index.get(key)
        if existing is not None:
            if existing != posting:
                raise ValueError('posting_id collision for different ledger posting')
            return existing
        self._postings.setdefault(posting.tenant_id, []).append(posting)
        self._posting_index[key] = posting
        return posting

    def list_postings(self, *, tenant_id: str) -> tuple[LedgerPosting, ...]:
        tid = require_tenant_id(tenant_id)
        return tuple(self._postings.get(tid, ()))

    def total_for_account(self, *, tenant_id: str, account_code: str, side: str | None = None) -> int:
        tid = require_tenant_id(tenant_id)
        code = str(account_code or '').strip()
        if not code:
            raise ValueError('account_code is required')
        normalized_side = None if side is None else str(side).strip().lower()
        if normalized_side is not None and normalized_side not in {'debit', 'credit'}:
            raise ValueError('side must be debit or credit')
        total = 0
        for posting in self._postings.get(tid, ()):
            for entry in posting.entries:
                if entry.account_code != code:
                    continue
                if normalized_side is not None and entry.side.lower() != normalized_side:
                    continue
                total += int(entry.amount_minor)
        return total


__all__ = ['CANON_BILLING_LEDGER_STORE', 'InMemoryLedgerStore', 'LedgerStoreContract']
