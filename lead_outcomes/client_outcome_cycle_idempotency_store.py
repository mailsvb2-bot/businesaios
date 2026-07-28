from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import RLock
from typing import Any, Mapping

from registry.base_registry import BaseRegistry, RegistryBackend


CANON_CLIENT_OUTCOME_CYCLE_IDEMPOTENCY_STORE = True
CANON_CLIENT_OUTCOME_RESERVE_BEFORE_EFFECT = True
CANON_CLIENT_OUTCOME_IDEMPOTENCY_LEASE_RECOVERY = True
CANON_CLIENT_OUTCOME_IDEMPOTENCY_FENCING = True


def _fingerprint(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
        default=str,
    ).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _lease_ttl_seconds(configured: int | None) -> int:
    raw = configured
    if raw is None:
        value = str(os.getenv('BUSINESAIOS_CLIENT_OUTCOME_IDEMPOTENCY_LEASE_SECONDS', '900') or '900').strip()
        try:
            raw = int(value)
        except ValueError as exc:
            raise RuntimeError('INVALID_BUSINESAIOS_CLIENT_OUTCOME_IDEMPOTENCY_LEASE_SECONDS') from exc
    if int(raw) < 1 or int(raw) > 86_400:
        raise ValueError('lease_ttl_seconds must be between 1 and 86400')
    return int(raw)


def _parse_aware(value: object) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise RuntimeError('client_outcome_idempotency_lease_state_invalid') from exc
    if parsed.tzinfo is None:
        raise RuntimeError('client_outcome_idempotency_lease_state_invalid')
    return parsed


class ClientOutcomeCycleIdempotencyStore(BaseRegistry):
    """Persistent reserve-before-effect owner with lease recovery and fencing."""

    def __init__(
        self,
        *,
        backend: RegistryBackend | None = None,
        lease_ttl_seconds: int | None = None,
    ) -> None:
        super().__init__(kind='client_outcome_cycle_idempotency', backend=backend)
        self._lease_ttl_seconds = _lease_ttl_seconds(lease_ttl_seconds)
        self._state_lock = RLock()

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

    def _compare_and_replace(
        self,
        *,
        key: str,
        expected: Mapping[str, object],
        replacement: Mapping[str, object],
    ) -> bool:
        if self._backend is not None:
            operation = getattr(self._backend, 'compare_and_replace', None)
            if not callable(operation):
                raise RuntimeError('client_outcome_idempotency_atomic_recovery_backend_required')
            return bool(operation(key, dict(expected), dict(replacement)))
        if super().maybe_get(key) != dict(expected):
            return False
        super().register(key, dict(replacement))
        return True

    def _reservation(
        self,
        *,
        now: datetime,
        request_fingerprint: str,
        lease_generation: int,
    ) -> dict[str, object]:
        return {
            'state': 'reserved',
            'request_fingerprint': request_fingerprint,
            'lease_token': uuid.uuid4().hex,
            'lease_generation': int(lease_generation),
            'reserved_at': now.isoformat(),
            'lease_expires_at': (now + timedelta(seconds=self._lease_ttl_seconds)).isoformat(),
            'response': None,
        }

    @staticmethod
    def _acquired(reservation: Mapping[str, object], *, recovered: bool) -> dict[str, Any]:
        return {
            'acquired': True,
            'recovered': recovered,
            'response': None,
            'request_fingerprint': str(reservation['request_fingerprint']),
            'lease_token': str(reservation['lease_token']),
            'lease_generation': int(reservation['lease_generation']),
            'lease_expires_at': str(reservation['lease_expires_at']),
        }

    @staticmethod
    def _replay(existing: Mapping[str, object], request_fingerprint: str) -> dict[str, Any]:
        response = existing.get('response')
        if not isinstance(response, Mapping):
            raise RuntimeError('client_outcome_idempotency_completed_response_missing')
        return {
            'acquired': False,
            'recovered': False,
            'response': dict(response),
            'request_fingerprint': request_fingerprint,
            'lease_token': None,
            'lease_generation': int(existing.get('lease_generation') or 0),
            'lease_expires_at': existing.get('lease_expires_at'),
        }

    def _lease_expired(self, existing: Mapping[str, object], *, now: datetime) -> bool:
        expires_at = existing.get('lease_expires_at')
        if expires_at is None:
            expires_at = _parse_aware(existing.get('reserved_at')) + timedelta(seconds=self._lease_ttl_seconds)
        else:
            expires_at = _parse_aware(expires_at)
        return now >= expires_at

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
        reservation = self._reservation(now=now, request_fingerprint=request_fingerprint, lease_generation=1)
        with self._state_lock:
            try:
                self.register_unique(key, reservation, error_prefix='client_outcome_cycle_idempotency')
                return self._acquired(reservation, recovered=False)
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
                state = str(existing.get('state') or '')
                if state == 'completed':
                    return self._replay(existing, request_fingerprint)
                if state != 'reserved':
                    raise RuntimeError('client_outcome_idempotency_state_invalid')
                if not self._lease_expired(existing, now=now):
                    raise RuntimeError('client_outcome_idempotency_in_progress')

                replacement = self._reservation(
                    now=now,
                    request_fingerprint=request_fingerprint,
                    lease_generation=int(existing.get('lease_generation') or 1) + 1,
                )
                if self._compare_and_replace(key=key, expected=existing, replacement=replacement):
                    return self._acquired(replacement, recovered=True)
                latest = self._row(
                    tenant_id=tenant_id,
                    business_id=business_id,
                    lead_id=lead_id,
                    idempotency_key=idempotency_key,
                )
                if latest is not None and str(latest.get('state') or '') == 'completed':
                    return self._replay(latest, request_fingerprint)
                raise RuntimeError('client_outcome_idempotency_in_progress')

    def complete(
        self,
        *,
        tenant_id: str,
        business_id: str,
        lead_id: str,
        idempotency_key: str,
        lease_token: str,
        now: datetime,
        request_payload: Mapping[str, object],
        response_payload: Mapping[str, object],
    ) -> dict[str, Any]:
        if now.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        token = str(lease_token or '').strip()
        if not token:
            raise ValueError('client_outcome_idempotency_lease_token_required')
        key = self.make_key(
            tenant_id=tenant_id,
            business_id=business_id,
            lead_id=lead_id,
            idempotency_key=idempotency_key,
        )
        request_fingerprint = _fingerprint(request_payload)
        with self._state_lock:
            existing = self._row(
                tenant_id=tenant_id,
                business_id=business_id,
                lead_id=lead_id,
                idempotency_key=idempotency_key,
            )
            if existing is None:
                raise RuntimeError('client_outcome_idempotency_reservation_required')
            if str(existing.get('request_fingerprint') or '') != request_fingerprint:
                raise ValueError('client_outcome_idempotency_payload_collision')
            if str(existing.get('lease_token') or '') != token:
                raise RuntimeError('client_outcome_idempotency_fence_violation')
            state = str(existing.get('state') or '')
            if state == 'completed':
                if dict(existing.get('response') or {}) != dict(response_payload):
                    raise ValueError('client_outcome_idempotency_response_collision')
                return existing
            if state != 'reserved':
                raise RuntimeError('client_outcome_idempotency_state_invalid')

            completed = {
                **existing,
                'state': 'completed',
                'completed_at': now.isoformat(),
                'completed_lease_token': token,
                'response': dict(response_payload),
            }
            if self._compare_and_replace(key=key, expected=existing, replacement=completed):
                return completed
            latest = self._row(
                tenant_id=tenant_id,
                business_id=business_id,
                lead_id=lead_id,
                idempotency_key=idempotency_key,
            )
            if (
                latest is not None
                and str(latest.get('state') or '') == 'completed'
                and str(latest.get('lease_token') or '') == token
                and dict(latest.get('response') or {}) == dict(response_payload)
            ):
                return latest
            raise RuntimeError('client_outcome_idempotency_fence_violation')

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
    'CANON_CLIENT_OUTCOME_IDEMPOTENCY_FENCING',
    'CANON_CLIENT_OUTCOME_IDEMPOTENCY_LEASE_RECOVERY',
    'CANON_CLIENT_OUTCOME_RESERVE_BEFORE_EFFECT',
    'ClientOutcomeCycleIdempotencyService',
    'ClientOutcomeCycleIdempotencyStore',
]
