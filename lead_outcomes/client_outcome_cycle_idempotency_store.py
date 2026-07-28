from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from registry.base_registry import BaseRegistry, RegistryBackend


CANON_CLIENT_OUTCOME_CYCLE_IDEMPOTENCY_STORE = True
CANON_CLIENT_OUTCOME_RESERVE_BEFORE_EFFECT = True


def _fingerprint(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
        default=str,
    ).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


class ClientOutcomeCycleIdempotencyStore(BaseRegistry):
    """Persistent reserve-before-effect owner for the full commercial cycle."""

    def __init__(self, *, backend: RegistryBackend | None = None) -> None:
        super().__init__(kind='client_outcome_cycle_idempotency', backend=backend)

    @staticmethod
    def make_key(*, tenant_id: str, business_id: str, lead_id: str, idempotency_key: str) -> str:
        return '|'.join([
            str(tenant_id).strip(),
            str(business_id).strip(),
            str(lead_id).strip(),
            str(idempotency_key).strip(),
        ])

    def _row(self, *, tenant_id: str, business_id: str, lead_id: str, idempotency_key: str) -> dict[str, Any] | None:
        key = self.make_key(
            tenant_id=tenant_id,
            business_id=business_id,
            lead_id=lead_id,
            idempotency_key=idempotency_key,
        )
        try:
            row = super().get(key)
        except KeyError:
            return None
        return dict(row) if isinstance(row, Mapping) else None

    def reserve(
        self,
        *,
        tenant_id: str,
        business_id: str,
        lead_id: str,
        idempotency_key: str,
        now: datetime,
        request_payload: Mapping[str, object],
    ) -> dict[str, Any]:
        if now.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        key = self.make_key(
            tenant_id=tenant_id,
            business_id=business_id,
            lead_id=lead_id,
            idempotency_key=idempotency_key,
        )
        request_fingerprint = _fingerprint(request_payload)
        reservation = {
            'state': 'reserved',
            'request_fingerprint': request_fingerprint,
            'reserved_at': now.isoformat(),
            'response': None,
        }
        try:
            self.register_unique(key, reservation, error_prefix='client_outcome_cycle_idempotency')
            return {'acquired': True, 'response': None, 'request_fingerprint': request_fingerprint}
        except ValueError:
            existing = self._row(
                tenant_id=tenant_id,
                business_id=business_id,
                lead_id=lead_id,
                idempotency_key=idempotency_key,
            )
            if existing is None:
                raise RuntimeError('client_outcome_idempotency_reservation_lost')
            if str(existing.get('request_fingerprint') or '') != request_fingerprint:
                raise ValueError('client_outcome_idempotency_payload_collision')
            if str(existing.get('state') or '') == 'completed' and isinstance(existing.get('response'), Mapping):
                return {
                    'acquired': False,
                    'response': dict(existing['response']),
                    'request_fingerprint': request_fingerprint,
                }
            raise RuntimeError('client_outcome_idempotency_in_progress')

    def complete(
        self,
        *,
        tenant_id: str,
        business_id: str,
        lead_id: str,
        idempotency_key: str,
        now: datetime,
        request_payload: Mapping[str, object],
        response_payload: Mapping[str, object],
    ) -> dict[str, Any]:
        if now.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        key = self.make_key(
            tenant_id=tenant_id,
            business_id=business_id,
            lead_id=lead_id,
            idempotency_key=idempotency_key,
        )
        existing = self._row(
            tenant_id=tenant_id,
            business_id=business_id,
            lead_id=lead_id,
            idempotency_key=idempotency_key,
        )
        request_fingerprint = _fingerprint(request_payload)
        if existing is None:
            raise RuntimeError('client_outcome_idempotency_reservation_required')
        if str(existing.get('request_fingerprint') or '') != request_fingerprint:
            raise ValueError('client_outcome_idempotency_payload_collision')
        if str(existing.get('state') or '') == 'completed':
            prior = dict(existing.get('response') or {})
            if prior != dict(response_payload):
                raise ValueError('client_outcome_idempotency_response_collision')
            return existing
        completed = {
            **existing,
            'state': 'completed',
            'completed_at': now.isoformat(),
            'response': dict(response_payload),
        }
        self.register(key, completed)
        return completed

    def get_response(self, *, tenant_id: str, business_id: str, lead_id: str, idempotency_key: str) -> dict[str, Any] | None:
        row = self._row(
            tenant_id=tenant_id,
            business_id=business_id,
            lead_id=lead_id,
            idempotency_key=idempotency_key,
        )
        if row is None or str(row.get('state') or '') != 'completed':
            return None
        return row


@dataclass(frozen=True, slots=True)
class ClientOutcomeCycleIdempotencyService:
    store: ClientOutcomeCycleIdempotencyStore

    def reserve(self, **kwargs: object) -> dict[str, Any]:
        return self.store.reserve(**kwargs)  # type: ignore[arg-type]

    def complete(self, **kwargs: object) -> dict[str, Any]:
        return self.store.complete(**kwargs)  # type: ignore[arg-type]

    def get_response(self, **kwargs: object) -> dict[str, Any] | None:
        return self.store.get_response(**kwargs)  # type: ignore[arg-type]


__all__ = [
    'CANON_CLIENT_OUTCOME_CYCLE_IDEMPOTENCY_STORE',
    'CANON_CLIENT_OUTCOME_RESERVE_BEFORE_EFFECT',
    'ClientOutcomeCycleIdempotencyService',
    'ClientOutcomeCycleIdempotencyStore',
]
