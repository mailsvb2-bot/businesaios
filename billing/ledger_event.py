from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping

from core.tenancy.normalization import require_tenant_id


CANON_BILLING_LEDGER_EVENT = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class LedgerEntry:
    tenant_id: str
    entry_id: str
    account_code: str
    side: str
    amount_minor: int
    currency: str
    reference_type: str
    reference_id: str
    booked_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.entry_id or '').strip():
            raise ValueError('entry_id is required')
        if not str(self.account_code or '').strip():
            raise ValueError('account_code is required')
        if str(self.side).strip().lower() not in {'debit', 'credit'}:
            raise ValueError('side must be debit or credit')
        if int(self.amount_minor) < 0:
            raise ValueError('amount_minor must be >= 0')
        if not str(self.currency or '').strip():
            raise ValueError('currency is required')
        if not str(self.reference_type or '').strip():
            raise ValueError('reference_type is required')
        if not str(self.reference_id or '').strip():
            raise ValueError('reference_id is required')
        if self.booked_at.tzinfo is None:
            raise ValueError('booked_at must be timezone-aware')


@dataclass(frozen=True)
class LedgerPosting:
    posting_id: str
    tenant_id: str
    reference_type: str
    reference_id: str
    entries: tuple[LedgerEntry, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.posting_id or '').strip():
            raise ValueError('posting_id is required')
        if not str(self.reference_type or '').strip():
            raise ValueError('reference_type is required')
        if not str(self.reference_id or '').strip():
            raise ValueError('reference_id is required')
        if len(self.entries) < 2:
            raise ValueError('posting must contain at least two entries')
        debit_total = 0
        credit_total = 0
        currency = None
        seen_entry_ids: set[str] = set()
        for entry in self.entries:
            entry.validate()
            if entry.tenant_id != self.tenant_id:
                raise ValueError('all entries must belong to same tenant')
            if entry.reference_type != self.reference_type or entry.reference_id != self.reference_id:
                raise ValueError('entry reference must match posting reference')
            if entry.entry_id in seen_entry_ids:
                raise ValueError('entry_id must be unique within posting')
            seen_entry_ids.add(entry.entry_id)
            if currency is None:
                currency = entry.currency.upper()
            elif currency != entry.currency.upper():
                raise ValueError('posting must use a single currency')
            if entry.side.lower() == 'debit':
                debit_total += int(entry.amount_minor)
            else:
                credit_total += int(entry.amount_minor)
        if debit_total != credit_total:
            raise ValueError('ledger posting must be balanced')


__all__ = ['CANON_BILLING_LEDGER_EVENT', 'LedgerEntry', 'LedgerPosting', 'utc_now']
