from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from registry.base_registry import BaseRegistry


CANON_CLIENT_OUTCOME_LIFECYCLE_STORE = True


class ClientOutcomeLifecycleStore(BaseRegistry):
    """
    Auditable lifecycle state owner for a client-outcome lead.
    One row per (order_id, lead_id) with append-like stage updates.
    """

    def __init__(self) -> None:
        super().__init__(kind='client_outcome_lifecycle')

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

    def upsert_stage(
        self,
        *,
        order_id: str,
        lead_id: str,
        stage_name: str,
        now: datetime,
        stage_payload: Mapping[str, object],
    ) -> dict[str, Any]:
        if now.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        key = self.make_key(order_id=order_id, lead_id=lead_id)
        current = self.get_state(order_id=order_id, lead_id=lead_id) or {
            'order_id': order_id,
            'lead_id': lead_id,
            'created_at': now.isoformat(),
            'updated_at': now.isoformat(),
            'stages': {},
        }
        stages = dict(current.get('stages') or {})
        stages[str(stage_name)] = {
            'at': now.isoformat(),
            'payload': dict(stage_payload),
        }
        current['stages'] = stages
        current['updated_at'] = now.isoformat()
        self.register(key, current)
        return current


@dataclass(frozen=True, slots=True)
class ClientOutcomeLifecyclePersistenceService:
    store: ClientOutcomeLifecycleStore

    def record_stage(
        self,
        *,
        order_id: str,
        lead_id: str,
        stage_name: str,
        now: datetime,
        payload: Mapping[str, object],
    ) -> dict[str, Any]:
        return self.store.upsert_stage(
            order_id=order_id,
            lead_id=lead_id,
            stage_name=stage_name,
            now=now,
            stage_payload=payload,
        )

    def get_state(self, *, order_id: str, lead_id: str) -> dict[str, Any] | None:
        return self.store.get_state(order_id=order_id, lead_id=lead_id)
