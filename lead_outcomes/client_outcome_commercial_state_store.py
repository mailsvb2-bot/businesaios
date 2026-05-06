from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from registry.base_registry import BaseRegistry


CANON_CLIENT_OUTCOME_COMMERCIAL_STATE_STORE = True


class ClientOutcomeCommercialStateStore(BaseRegistry):
    """
    Owner read/write surface for commercial truth of a client-outcome lead.
    One row per (order_id, lead_id). This complements lifecycle history with
    normalized current-state snapshots for verification/billing/dispute/reversal/economics.
    """

    def __init__(self) -> None:
        super().__init__(kind='client_outcome_commercial_state')

    @staticmethod
    def make_key(*, order_id: str, lead_id: str) -> str:
        return f'{str(order_id).strip()}::{str(lead_id).strip()}'

    def get_state(self, *, order_id: str, lead_id: str) -> dict[str, Any] | None:
        key = self.make_key(order_id=order_id, lead_id=lead_id)
        try:
            row = super().get(key)
        except KeyError:
            return None
        return dict(row) if isinstance(row, Mapping) else None


    def get_latest_order_state(self, *, order_id: str) -> dict[str, Any] | None:
        order_prefix = f'{str(order_id).strip()}::'
        latest: dict[str, Any] | None = None
        latest_updated_at = ''
        for key, row in getattr(self, '_items', {}).items():
            if not str(key).startswith(order_prefix):
                continue
            payload = dict(row) if isinstance(row, Mapping) else None
            if not payload:
                continue
            updated_at = str(payload.get('updated_at') or '')
            if latest is None or updated_at > latest_updated_at:
                latest = payload
                latest_updated_at = updated_at
        return latest

    def upsert_state(
        self,
        *,
        order_id: str,
        lead_id: str,
        now: datetime,
        patch: Mapping[str, object],
    ) -> dict[str, Any]:
        if now.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        key = self.make_key(order_id=order_id, lead_id=lead_id)
        current = self.get_state(order_id=order_id, lead_id=lead_id) or {
            'order_id': order_id,
            'lead_id': lead_id,
            'created_at': now.isoformat(),
            'updated_at': now.isoformat(),
        }
        for name, value in dict(patch).items():
            current[str(name)] = value
        current['updated_at'] = now.isoformat()
        self.register(key, current)
        return current


@dataclass(frozen=True, slots=True)
class ClientOutcomeCommercialStateService:
    store: ClientOutcomeCommercialStateStore

    def record_selected_execution(
        self,
        *,
        order_id: str,
        lead_id: str,
        now: datetime,
        order_payload: Mapping[str, object],
        execution_payload: Mapping[str, object],
    ) -> dict[str, Any]:
        return self.store.upsert_state(
            order_id=order_id,
            lead_id=lead_id,
            now=now,
            patch={
                'order': dict(order_payload),
                'execution': dict(execution_payload),
                'commercial_status': 'executed',
            },
        )

    def record_verification(
        self,
        *,
        order_id: str,
        lead_id: str,
        now: datetime,
        payload: Mapping[str, object],
    ) -> dict[str, Any]:
        commercial_status = 'verified' if bool(payload.get('verified')) else 'verification_rejected'
        return self.store.upsert_state(
            order_id=order_id,
            lead_id=lead_id,
            now=now,
            patch={
                'verification': dict(payload),
                'commercial_status': commercial_status,
            },
        )

    def record_billing(
        self,
        *,
        order_id: str,
        lead_id: str,
        now: datetime,
        billable_record: Mapping[str, object] | None,
        revenue_payload: Mapping[str, object],
    ) -> dict[str, Any]:
        return self.store.upsert_state(
            order_id=order_id,
            lead_id=lead_id,
            now=now,
            patch={
                'billable_record': None if billable_record is None else dict(billable_record),
                'revenue_before_reversal': dict(revenue_payload),
                'commercial_status': 'billed',
            },
        )

    def record_dispute(
        self,
        *,
        order_id: str,
        lead_id: str,
        now: datetime,
        dispute_payload: Mapping[str, object],
    ) -> dict[str, Any]:
        return self.store.upsert_state(
            order_id=order_id,
            lead_id=lead_id,
            now=now,
            patch={
                'dispute': dict(dispute_payload),
                'commercial_status': 'disputed',
            },
        )

    def record_reversal(
        self,
        *,
        order_id: str,
        lead_id: str,
        now: datetime,
        reversal_payload: Mapping[str, object] | None,
        corrected_revenue_payload: Mapping[str, object],
        admin_summary_payload: Mapping[str, object],
    ) -> dict[str, Any]:
        status = 'closed'
        if reversal_payload is not None:
            status = 'partial_reversed' if bool(reversal_payload.get('partial_reversal')) else 'reversed'
        return self.store.upsert_state(
            order_id=order_id,
            lead_id=lead_id,
            now=now,
            patch={
                'reversal': None if reversal_payload is None else dict(reversal_payload),
                'revenue_after_reversal': dict(corrected_revenue_payload),
                'admin_summary': dict(admin_summary_payload),
                'commercial_status': status,
            },
        )

    def get_state(self, *, order_id: str, lead_id: str) -> dict[str, Any] | None:
        return self.store.get_state(order_id=order_id, lead_id=lead_id)

    def get_latest_order_state(self, *, order_id: str) -> dict[str, Any] | None:
        return self.store.get_latest_order_state(order_id=order_id)
