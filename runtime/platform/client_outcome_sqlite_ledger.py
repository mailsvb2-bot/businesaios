from __future__ import annotations

import time
from collections.abc import Mapping
from datetime import datetime

from billing.ledger_event import LedgerEntry, LedgerPosting
from contracts.tenant_identity import require_tenant_id
from runtime.platform.client_outcome_sqlite_core import _SQLiteOwner, _json_dumps, _json_loads


class SQLiteClientOutcomeLedgerStore:
    def __init__(self, *, owner: _SQLiteOwner) -> None:
        self._owner = owner

    @staticmethod
    def _posting_payload(posting: LedgerPosting) -> dict[str, object]:
        return {
            'posting_id': posting.posting_id,
            'tenant_id': posting.tenant_id,
            'reference_type': posting.reference_type,
            'reference_id': posting.reference_id,
            'metadata': dict(posting.metadata),
            'entries': [
                {
                    'tenant_id': entry.tenant_id,
                    'entry_id': entry.entry_id,
                    'account_code': entry.account_code,
                    'side': entry.side,
                    'amount_minor': entry.amount_minor,
                    'currency': entry.currency,
                    'reference_type': entry.reference_type,
                    'reference_id': entry.reference_id,
                    'booked_at': entry.booked_at.isoformat(),
                    'metadata': dict(entry.metadata),
                }
                for entry in posting.entries
            ],
        }

    @staticmethod
    def _posting_from_payload(payload: Mapping[str, object]) -> LedgerPosting:
        entries = tuple(
            LedgerEntry(
                tenant_id=str(item['tenant_id']),
                entry_id=str(item['entry_id']),
                account_code=str(item['account_code']),
                side=str(item['side']),
                amount_minor=int(item['amount_minor']),
                currency=str(item['currency']),
                reference_type=str(item['reference_type']),
                reference_id=str(item['reference_id']),
                booked_at=datetime.fromisoformat(str(item['booked_at'])),
                metadata=dict(item.get('metadata') or {}),
            )
            for item in list(payload.get('entries') or [])
        )
        return LedgerPosting(
            posting_id=str(payload['posting_id']),
            tenant_id=str(payload['tenant_id']),
            reference_type=str(payload['reference_type']),
            reference_id=str(payload['reference_id']),
            entries=entries,
            metadata=dict(payload.get('metadata') or {}),
        )

    def append(self, posting: LedgerPosting) -> LedgerPosting:
        posting.validate()
        payload = self._posting_payload(posting)
        encoded = _json_dumps(payload)
        with self._owner._lock, self._owner._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute(
                'SELECT payload_json FROM client_outcome_ledger_postings WHERE tenant_id=? AND posting_id=?',
                (posting.tenant_id, posting.posting_id),
            ).fetchone()
            if row is not None:
                existing = self._posting_from_payload(dict(_json_loads(str(row[0]))))
                conn.rollback()
                if existing != posting:
                    raise ValueError('posting_id collision for different ledger posting')
                return existing
            conn.execute(
                '''
                INSERT INTO client_outcome_ledger_postings(tenant_id, posting_id, payload_json, created_at_epoch_ms)
                VALUES (?, ?, ?, ?)
                ''',
                (posting.tenant_id, posting.posting_id, encoded, int(time.time() * 1000)),
            )
            conn.commit()
        return posting

    def list_postings(self, *, tenant_id: str) -> tuple[LedgerPosting, ...]:
        tid = require_tenant_id(tenant_id)
        with self._owner._lock, self._owner._connect() as conn:
            rows = conn.execute(
                'SELECT payload_json FROM client_outcome_ledger_postings WHERE tenant_id=? ORDER BY created_at_epoch_ms, posting_id',
                (tid,),
            ).fetchall()
        return tuple(self._posting_from_payload(dict(_json_loads(str(row[0])))) for row in rows)

    def total_for_account(self, *, tenant_id: str, account_code: str, side: str | None = None) -> int:
        code = str(account_code or '').strip()
        if not code:
            raise ValueError('account_code is required')
        normalized_side = None if side is None else str(side).strip().lower()
        if normalized_side is not None and normalized_side not in {'debit', 'credit'}:
            raise ValueError('side must be debit or credit')
        total = 0
        for posting in self.list_postings(tenant_id=tenant_id):
            for entry in posting.entries:
                if entry.account_code != code:
                    continue
                if normalized_side is not None and entry.side.lower() != normalized_side:
                    continue
                total += int(entry.amount_minor)
        return total


__all__ = ['SQLiteClientOutcomeLedgerStore']
