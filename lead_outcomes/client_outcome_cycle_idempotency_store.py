from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from registry.base_registry import BaseRegistry


CANON_CLIENT_OUTCOME_CYCLE_IDEMPOTENCY_STORE = True


class ClientOutcomeCycleIdempotencyStore(BaseRegistry):
    """Stores deterministic full-cycle responses by idempotency key."""

    def __init__(self) -> None:
        super().__init__(kind='client_outcome_cycle_idempotency')

    @staticmethod
    def make_key(*, tenant_id: str, business_id: str, lead_id: str, idempotency_key: str) -> str:
        return '|'.join([str(tenant_id).strip(), str(business_id).strip(), str(lead_id).strip(), str(idempotency_key).strip()])

    def get_response(self, *, tenant_id: str, business_id: str, lead_id: str, idempotency_key: str) -> dict[str, Any] | None:
        key = self.make_key(tenant_id=tenant_id, business_id=business_id, lead_id=lead_id, idempotency_key=idempotency_key)
        try:
            row = super().get(key)
        except KeyError:
            return None
        return dict(row) if isinstance(row, Mapping) else None

    def save_response(
        self,
        *,
        tenant_id: str,
        business_id: str,
        lead_id: str,
        idempotency_key: str,
        now: datetime,
        response_payload: Mapping[str, object],
    ) -> dict[str, Any]:
        if now.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        key = self.make_key(tenant_id=tenant_id, business_id=business_id, lead_id=lead_id, idempotency_key=idempotency_key)
        payload = {'stored_at': now.isoformat(), 'response': dict(response_payload)}
        self.register(key, payload)
        return payload


@dataclass(frozen=True, slots=True)
class ClientOutcomeCycleIdempotencyService:
    store: ClientOutcomeCycleIdempotencyStore

    def get_response(self, *, tenant_id: str, business_id: str, lead_id: str, idempotency_key: str) -> dict[str, Any] | None:
        return self.store.get_response(tenant_id=tenant_id, business_id=business_id, lead_id=lead_id, idempotency_key=idempotency_key)

    def save_response(self, *, tenant_id: str, business_id: str, lead_id: str, idempotency_key: str, now: datetime, response_payload: Mapping[str, object]) -> dict[str, Any]:
        return self.store.save_response(tenant_id=tenant_id, business_id=business_id, lead_id=lead_id, idempotency_key=idempotency_key, now=now, response_payload=response_payload)
