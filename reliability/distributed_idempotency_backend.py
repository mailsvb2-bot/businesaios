from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any, Callable, Mapping, Protocol
import json

from reliability.idempotency_contract import (
    IdempotencyDecision,
    IdempotencyKey,
    IdempotencyRecord,
    IdempotencyResolution,
    IdempotencyState,
    IdempotencyStore,
    utc_now,
)


CANON_DISTRIBUTED_IDEMPOTENCY_BACKEND = True


def _json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest_payload(payload: Mapping[str, Any] | None) -> str | None:
    if not payload:
        return None
    return sha256(_json_text(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DistributedIdempotencyLease:
    holder_id: str
    fencing_token: int
    expires_at: datetime


class DistributedCompareAndSwapPort(Protocol):
    def create_if_absent(self, *, key: str, payload: Mapping[str, Any], ttl_seconds: int | None = None) -> bool: ...
    def read(self, *, key: str) -> Mapping[str, Any] | None: ...
    def compare_and_swap(self, *, key: str, expected_version: int, payload: Mapping[str, Any], ttl_seconds: int | None = None) -> bool: ...


class DistributedSequencePort(Protocol):
    def next_value(self, *, namespace: str) -> int: ...


class DistributedIdempotencyStore(IdempotencyStore):
    def __init__(
        self,
        *,
        cas: DistributedCompareAndSwapPort,
        sequence: DistributedSequencePort,
        key_prefix: str = "idempotency/records",
    ) -> None:
        self._cas = cas
        self._sequence = sequence
        self._key_prefix = str(key_prefix).strip("/")

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
        if not str(owner_id or "").strip():
            raise ValueError("owner_id is required")
        moment = now or utc_now()
        storage_key = self._storage_key(key)
        base_record = IdempotencyRecord(
            idempotency_key=key,
            state=IdempotencyState.STARTED,
            first_seen_at=moment,
            updated_at=moment,
            metadata=dict(metadata_patch or {}),
        ).as_reserved(
            owner_id=owner_id,
            lease_ttl_seconds=lease_ttl_seconds,
            now=moment,
            increment_attempt=True,
            metadata_patch=metadata_patch,
        )
        lease = self._new_lease(base_record)
        created = self._cas.create_if_absent(
            key=storage_key,
            payload=self._to_storage_payload(base_record, version=1, distributed_lease=lease),
            ttl_seconds=max(lease_ttl_seconds * 4, 60),
        )
        if created:
            return IdempotencyDecision(IdempotencyResolution.ACCEPTED, base_record)
        current_payload = self._read_storage_payload(storage_key)
        current = self._from_storage_payload(current_payload)
        current_version = int(current_payload.get("version") or 0)
        if current.idempotency_key.as_tuple() != key.as_tuple():
            raise ValueError("idempotency key tuple mismatch")
        if current.idempotency_key.scope_hash != key.scope_hash:
            return IdempotencyDecision(IdempotencyResolution.REJECTED_SCOPE_MISMATCH, current)
        if current.state is IdempotencyState.COMPLETED:
            return IdempotencyDecision(IdempotencyResolution.REPLAY_COMPLETED, current, current.result_ref, current.result_digest)
        if current.state is IdempotencyState.FAILED:
            return IdempotencyDecision(IdempotencyResolution.REJECTED_TERMINAL_FAILED, current)
        if current.has_live_lease(now=moment):
            return IdempotencyDecision(IdempotencyResolution.REJECTED_IN_PROGRESS, current)
        reserved = current.as_reserved(
            owner_id=owner_id,
            lease_ttl_seconds=lease_ttl_seconds,
            now=moment,
            increment_attempt=True,
            metadata_patch=metadata_patch,
        )
        lease = self._new_lease(reserved)
        updated = self._cas.compare_and_swap(
            key=storage_key,
            expected_version=current_version,
            payload=self._to_storage_payload(reserved, version=current_version + 1, distributed_lease=lease),
            ttl_seconds=max(lease_ttl_seconds * 4, 60),
        )
        if not updated:
            latest_payload = self._read_storage_payload(storage_key)
            latest = self._from_storage_payload(latest_payload)
            if latest.state is IdempotencyState.COMPLETED:
                return IdempotencyDecision(IdempotencyResolution.REPLAY_COMPLETED, latest, latest.result_ref, latest.result_digest)
            return IdempotencyDecision(IdempotencyResolution.REJECTED_IN_PROGRESS, latest)
        return IdempotencyDecision(IdempotencyResolution.ACCEPTED, reserved)

    def get(self, *, key: IdempotencyKey) -> IdempotencyRecord | None:
        payload = self._cas.read(key=self._storage_key(key))
        return None if payload is None else self._from_storage_payload(payload)

    def renew_lease(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        lease_ttl_seconds: int = 300,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyRecord:
        return self._mutate_active(
            key=key,
            owner_id=owner_id,
            now=now,
            ttl_seconds=lease_ttl_seconds,
            metadata_patch=metadata_patch,
            mutator=lambda current, moment: current.as_reserved(
                owner_id=owner_id,
                lease_ttl_seconds=lease_ttl_seconds,
                now=moment,
                increment_attempt=False,
                metadata_patch=metadata_patch,
            ),
            require_state={IdempotencyState.STARTED, IdempotencyState.IN_PROGRESS, IdempotencyState.EXPIRED},
        )

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
        return self._mutate_active(
            key=key,
            owner_id=owner_id,
            now=now,
            ttl_seconds=3600,
            metadata_patch=metadata_patch,
            mutator=lambda current, moment: current.mark_completed(
                owner_id=owner_id,
                result_ref=result_ref,
                result_digest=result_digest,
                now=moment,
                metadata_patch=metadata_patch,
            ),
            require_state={IdempotencyState.STARTED, IdempotencyState.IN_PROGRESS, IdempotencyState.EXPIRED},
        )

    def mark_failed(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        reason: str | None = None,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyRecord:
        return self._mutate_active(
            key=key,
            owner_id=owner_id,
            now=now,
            ttl_seconds=3600,
            metadata_patch=metadata_patch,
            mutator=lambda current, moment: current.mark_failed(
                owner_id=owner_id,
                reason=reason,
                now=moment,
                metadata_patch=metadata_patch,
            ),
            require_state={IdempotencyState.STARTED, IdempotencyState.IN_PROGRESS, IdempotencyState.EXPIRED},
        )

    def expire_stale(self, *, now: datetime | None = None, metadata_patch: Mapping[str, Any] | None = None) -> int:
        return 0

    def _mutate_active(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        now: datetime | None,
        ttl_seconds: int,
        metadata_patch: Mapping[str, Any] | None,
        mutator: Callable[[IdempotencyRecord, datetime], IdempotencyRecord],
        require_state: set[IdempotencyState],
    ) -> IdempotencyRecord:
        moment = now or utc_now()
        storage_key = self._storage_key(key)
        payload = self._read_storage_payload(storage_key)
        current = self._from_storage_payload(payload)
        if current.state not in require_state:
            raise ValueError(f"unsupported idempotency state: {current.state.value}")
        if str(current.owner_id or "") != str(owner_id):
            raise ValueError("idempotency owner mismatch")
        next_record = mutator(current, moment)
        version = int(payload.get("version") or 0)
        lease = None if next_record.state in {IdempotencyState.COMPLETED, IdempotencyState.FAILED} else self._new_lease(next_record)
        ok = self._cas.compare_and_swap(
            key=storage_key,
            expected_version=version,
            payload=self._to_storage_payload(next_record, version=version + 1, distributed_lease=lease),
            ttl_seconds=max(ttl_seconds * 4, 60),
        )
        if not ok:
            raise RuntimeError("idempotency compare-and-swap conflict")
        return next_record

    def _new_lease(self, record: IdempotencyRecord) -> DistributedIdempotencyLease | None:
        if record.owner_id is None or record.lease_expires_at is None:
            return None
        token = self._sequence.next_value(namespace=f"idempotency_fence:{record.idempotency_key.tenant_id}")
        return DistributedIdempotencyLease(
            holder_id=str(record.owner_id),
            fencing_token=int(token),
            expires_at=record.lease_expires_at,
        )

    def _storage_key(self, key: IdempotencyKey) -> str:
        tenant_id, namespace, operation, raw_key = key.as_tuple()
        return f"{self._key_prefix}/{tenant_id}/{namespace}/{operation}/{raw_key}"

    def _read_storage_payload(self, storage_key: str) -> Mapping[str, Any]:
        payload = self._cas.read(key=storage_key)
        if payload is None:
            raise KeyError(f"idempotency record missing: {storage_key}")
        return payload

    def _to_storage_payload(
        self,
        record: IdempotencyRecord,
        *,
        version: int,
        distributed_lease: DistributedIdempotencyLease | None,
    ) -> dict[str, Any]:
        payload = {
            "version": int(version),
            "tenant_id": record.idempotency_key.tenant_id,
            "namespace": record.idempotency_key.namespace,
            "operation": record.idempotency_key.operation,
            "key": record.idempotency_key.key,
            "scope_hash": record.idempotency_key.scope_hash,
            "state": record.state.value,
            "first_seen_at": record.first_seen_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "lease_expires_at": None if record.lease_expires_at is None else record.lease_expires_at.isoformat(),
            "completed_at": None if record.completed_at is None else record.completed_at.isoformat(),
            "owner_id": record.owner_id,
            "attempt_count": int(record.attempt_count),
            "result_ref": record.result_ref,
            "result_digest": record.result_digest,
            "failure_reason": record.failure_reason,
            "metadata": dict(record.metadata),
        }
        if distributed_lease is not None:
            payload["distributed_lease"] = {
                "holder_id": distributed_lease.holder_id,
                "fencing_token": int(distributed_lease.fencing_token),
                "expires_at": distributed_lease.expires_at.isoformat(),
            }
        return payload

    @staticmethod
    def _from_storage_payload(payload: Mapping[str, Any]) -> IdempotencyRecord:
        record = IdempotencyRecord(
            idempotency_key=IdempotencyKey(
                tenant_id=str(payload["tenant_id"]),
                namespace=str(payload["namespace"]),
                operation=str(payload["operation"]),
                key=str(payload["key"]),
                scope_hash=str(payload.get("scope_hash") or ""),
            ),
            state=IdempotencyState(str(payload["state"])),
            first_seen_at=datetime.fromisoformat(str(payload["first_seen_at"])),
            updated_at=datetime.fromisoformat(str(payload["updated_at"])),
            lease_expires_at=None if payload.get("lease_expires_at") in (None, "") else datetime.fromisoformat(str(payload["lease_expires_at"])),
            completed_at=None if payload.get("completed_at") in (None, "") else datetime.fromisoformat(str(payload["completed_at"])),
            owner_id=None if payload.get("owner_id") in (None, "") else str(payload.get("owner_id")),
            attempt_count=max(0, int(payload.get("attempt_count") or 0)),
            result_ref=None if payload.get("result_ref") in (None, "") else str(payload.get("result_ref")),
            result_digest=None if payload.get("result_digest") in (None, "") else str(payload.get("result_digest")),
            failure_reason=None if payload.get("failure_reason") in (None, "") else str(payload.get("failure_reason")),
            metadata=dict(payload.get("metadata") or {}),
        )
        record.validate()
        return record


__all__ = [
    "CANON_DISTRIBUTED_IDEMPOTENCY_BACKEND",
    "DistributedCompareAndSwapPort",
    "DistributedIdempotencyLease",
    "DistributedIdempotencyStore",
    "DistributedSequencePort",
    "_digest_payload",
]
