from __future__ import annotations

"""Canonical backend-oriented idempotency primitives.

This module centralizes idempotency state transitions while keeping storage pluggable.
It is infra-only and does not introduce a second decision center.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Any, Callable, Iterable, Mapping

from reliability.idempotency_contract import (
    CANON_IDEMPOTENCY_CONTRACT,
    IdempotencyDecision,
    IdempotencyKey,
    IdempotencyRecord,
    IdempotencyResolution,
    IdempotencyState,
    IdempotencyStore,
    utc_now,
)

CANON_IDEMPOTENCY_BACKEND = True


def _merge_metadata(
    base: Mapping[str, Any] | None,
    patch: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(base or {})
    if patch:
        merged.update(dict(patch))
    return merged


@dataclass(frozen=True)
class BackendMutationResult:
    stored_record: IdempotencyRecord
    previous_record: IdempotencyRecord | None
    created: bool
    revision: int | None = None


class IdempotencyBackend(ABC):
    @abstractmethod
    def load(self, *, key: IdempotencyKey) -> IdempotencyRecord | None:
        raise NotImplementedError

    @abstractmethod
    def mutate(
        self,
        *,
        key: IdempotencyKey,
        mutator: Callable[[IdempotencyRecord | None], IdempotencyRecord],
    ) -> BackendMutationResult:
        raise NotImplementedError

    @abstractmethod
    def scan_non_terminal(self) -> Iterable[IdempotencyRecord]:
        raise NotImplementedError

    def close(self) -> None:
        return None

    def compact(self) -> None:
        return None


class BaseBackendIdempotencyStore(IdempotencyStore):
    def __init__(self, *, backend: IdempotencyBackend) -> None:
        self._backend = backend
        self._lock = RLock()

    @property
    def backend(self) -> IdempotencyBackend:
        return self._backend

    def close(self) -> None:
        self._backend.close()

    def compact(self) -> None:
        self._backend.compact()

    def reserve(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        lease_ttl_seconds: int = 300,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyDecision:
        key.validate()
        owner = str(owner_id or '').strip()
        if not owner:
            raise ValueError('owner_id is required')
        moment = now or utc_now()

        def _mutate(existing: IdempotencyRecord | None) -> IdempotencyRecord:
            if existing is None:
                created = IdempotencyRecord(
                    idempotency_key=key,
                    state=IdempotencyState.STARTED,
                    first_seen_at=moment,
                    updated_at=moment,
                    owner_id=owner,
                    attempt_count=0,
                    metadata=_merge_metadata(None, metadata_patch),
                )
                created.validate()
                reserved = created.as_reserved(
                    owner_id=owner,
                    lease_ttl_seconds=lease_ttl_seconds,
                    now=moment,
                    increment_attempt=True,
                    metadata_patch=metadata_patch,
                )
                reserved.validate()
                return reserved

            if not existing.idempotency_key.same_scope(key):
                return existing
            if existing.state is IdempotencyState.COMPLETED:
                return existing
            if existing.state is IdempotencyState.FAILED:
                return existing
            if existing.has_live_lease(now=moment):
                return existing

            expired = existing.mark_expired(now=moment, metadata_patch=metadata_patch)
            expired.validate()
            renewed = expired.as_reserved(
                owner_id=owner,
                lease_ttl_seconds=lease_ttl_seconds,
                now=moment,
                increment_attempt=True,
                metadata_patch=metadata_patch,
            )
            renewed.validate()
            return renewed

        with self._lock:
            result = self._backend.mutate(key=key, mutator=_mutate)
            record = result.stored_record

        previous = result.previous_record
        accepted_by_transition = bool(result.created) or (
            previous is not None
            and previous.idempotency_key.same_scope(key)
            and previous.state not in {IdempotencyState.COMPLETED, IdempotencyState.FAILED}
            and not previous.has_live_lease(now=moment)
        )

        if not record.idempotency_key.same_scope(key):
            return IdempotencyDecision(
                resolution=IdempotencyResolution.REJECTED_SCOPE_MISMATCH,
                record=record,
            )
        if record.state is IdempotencyState.COMPLETED:
            return IdempotencyDecision(
                resolution=IdempotencyResolution.REPLAY_COMPLETED,
                record=record,
                replay_result_ref=record.result_ref,
                replay_result_digest=record.result_digest,
            )
        if record.state is IdempotencyState.FAILED:
            return IdempotencyDecision(
                resolution=IdempotencyResolution.REJECTED_TERMINAL_FAILED,
                record=record,
            )
        if (not accepted_by_transition) and record.state is IdempotencyState.IN_PROGRESS and record.has_live_lease(now=moment):
            return IdempotencyDecision(
                resolution=IdempotencyResolution.REJECTED_IN_PROGRESS,
                record=record,
            )
        return IdempotencyDecision(
            resolution=IdempotencyResolution.ACCEPTED,
            record=record,
        )

    def get(self, *, key: IdempotencyKey) -> IdempotencyRecord | None:
        key.validate()
        return self._backend.load(key=key)

    def renew_lease(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        lease_ttl_seconds: int = 300,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyRecord:
        key.validate()
        owner = str(owner_id or '').strip()
        if not owner:
            raise ValueError('owner_id is required')
        moment = now or utc_now()

        def _mutate(existing: IdempotencyRecord | None) -> IdempotencyRecord:
            record = self._require_owned_non_terminal(existing=existing, key=key, owner_id=owner)
            renewed = record.as_reserved(
                owner_id=owner,
                lease_ttl_seconds=lease_ttl_seconds,
                now=moment,
                increment_attempt=False,
                metadata_patch=metadata_patch,
            )
            renewed.validate()
            return renewed

        with self._lock:
            return self._backend.mutate(key=key, mutator=_mutate).stored_record

    def mark_completed(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        result_ref: str | None = None,
        result_digest: str | None = None,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyRecord:
        key.validate()
        owner = str(owner_id or '').strip()
        if not owner:
            raise ValueError('owner_id is required')
        moment = now or utc_now()

        def _mutate(existing: IdempotencyRecord | None) -> IdempotencyRecord:
            record = self._require_owned_non_terminal(existing=existing, key=key, owner_id=owner)
            completed = record.mark_completed(
                owner_id=owner,
                result_ref=result_ref,
                result_digest=result_digest,
                now=moment,
                metadata_patch=metadata_patch,
            )
            completed.validate()
            return completed

        with self._lock:
            return self._backend.mutate(key=key, mutator=_mutate).stored_record

    def mark_failed(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        reason: str | None = None,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyRecord:
        key.validate()
        owner = str(owner_id or '').strip()
        if not owner:
            raise ValueError('owner_id is required')
        moment = now or utc_now()

        def _mutate(existing: IdempotencyRecord | None) -> IdempotencyRecord:
            record = self._require_owned_non_terminal(existing=existing, key=key, owner_id=owner)
            failed = record.mark_failed(
                owner_id=owner,
                reason=reason,
                now=moment,
                metadata_patch=metadata_patch,
            )
            failed.validate()
            return failed

        with self._lock:
            return self._backend.mutate(key=key, mutator=_mutate).stored_record

    def expire_stale(self, *, now: datetime | None = None, metadata_patch: Mapping[str, Any] | None = None) -> int:
        moment = now or utc_now()
        changed = 0
        for record in list(self._backend.scan_non_terminal()):
            if record.state in {IdempotencyState.COMPLETED, IdempotencyState.FAILED, IdempotencyState.EXPIRED}:
                continue
            if record.has_live_lease(now=moment):
                continue

            def _mutate(existing: IdempotencyRecord | None) -> IdempotencyRecord:
                if existing is None:
                    raise KeyError(f'idempotency key not found: {record.idempotency_key.as_tuple()}')
                if existing.state in {IdempotencyState.COMPLETED, IdempotencyState.FAILED, IdempotencyState.EXPIRED}:
                    return existing
                if existing.has_live_lease(now=moment):
                    return existing
                expired = existing.mark_expired(now=moment, metadata_patch=metadata_patch)
                expired.validate()
                return expired

            mutated = self._backend.mutate(key=record.idempotency_key, mutator=_mutate).stored_record
            if mutated.state is IdempotencyState.EXPIRED:
                changed += 1
        return changed

    @staticmethod
    def _require_owned_non_terminal(*, existing: IdempotencyRecord | None, key: IdempotencyKey, owner_id: str) -> IdempotencyRecord:
        if existing is None:
            raise KeyError(f'idempotency key not found: {key.as_tuple()}')
        if not existing.idempotency_key.same_scope(key):
            raise PermissionError('idempotency scope mismatch')
        if str(existing.owner_id or '') != str(owner_id):
            raise PermissionError('owner mismatch for idempotency record')
        if existing.is_terminal():
            raise RuntimeError(f'idempotency record is terminal: {existing.state.value}')
        return existing


__all__ = [
    'BackendMutationResult',
    'BaseBackendIdempotencyStore',
    'CANON_IDEMPOTENCY_BACKEND',
    'CANON_IDEMPOTENCY_CONTRACT',
    'IdempotencyBackend',
]
