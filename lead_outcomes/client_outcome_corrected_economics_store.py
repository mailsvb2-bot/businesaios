from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from registry.base_registry import BaseRegistry


CANON_CLIENT_OUTCOME_CORRECTED_ECONOMICS_STORE = True


class ClientOutcomeCorrectedEconomicsStore(BaseRegistry):
    """
    Owner surface for the corrected economic truth of a client-outcome lead.
    Keeps the latest post-dispute / post-reversal commercial economics snapshot.
    """

    def __init__(self) -> None:
        super().__init__(kind='client_outcome_corrected_economics')

    @staticmethod
    def make_key(*, order_id: str, lead_id: str) -> str:
        return f"{str(order_id).strip()}::{str(lead_id).strip()}"

    def get_state(self, *, order_id: str, lead_id: str) -> dict[str, Any] | None:
        key = self.make_key(order_id=order_id, lead_id=lead_id)
        try:
            row = super().get(key)
        except KeyError:
            return None
        return dict(row) if isinstance(row, Mapping) else None

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
class ClientOutcomeCorrectedEconomicsService:
    store: ClientOutcomeCorrectedEconomicsStore

    def record_snapshot(
        self,
        *,
        order_id: str,
        lead_id: str,
        now: datetime,
        corrected_revenue_payload: Mapping[str, object],
        reversal_payload: Mapping[str, object] | None,
        refund_preview: Mapping[str, object] | None,
        refund_request: Mapping[str, object] | None = None,
    ) -> dict[str, Any]:
        economics_status = 'corrected' if reversal_payload is not None else 'uncorrected'
        return self.store.upsert_state(
            order_id=order_id,
            lead_id=lead_id,
            now=now,
            patch={
                'economics_status': economics_status,
                'corrected_revenue': dict(corrected_revenue_payload),
                'reversal': None if reversal_payload is None else dict(reversal_payload),
                'refund_preview': None if refund_preview is None else dict(refund_preview),
                'refund_request': None if refund_request is None else dict(refund_request),
            },
        )

    def get_state(self, *, order_id: str, lead_id: str) -> dict[str, Any] | None:
        return self.store.get_state(order_id=order_id, lead_id=lead_id)
