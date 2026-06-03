from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from collections.abc import Mapping

from reliability.idempotency_contract import IdempotencyDecision, IdempotencyKey, IdempotencyResolution
from reliability.idempotency_scope import build_headless_scope
from reliability.idempotency_sqlite_backend import SQLiteIdempotencyStore


CANON_HEADLESS_IDEMPOTENCY_GUARD = True


def build_headless_request_fingerprint(*, payload: dict[str, Any]) -> str:
    raw = json.dumps(dict(payload or {}), ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class IdempotencyClaim:
    accepted: bool
    resolution: str
    key: IdempotencyKey
    metadata: dict[str, Any]


@dataclass
class FileIdempotencyGuard:
    root_dir: Path
    tenant_id: str = 'headless'
    namespace: str = 'headless'
    operation: str = 'goal_request'
    owner_id: str = 'headless-file-guard'
    db_filename: str = 'idempotency_records.sqlite3'

    def __post_init__(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._store = SQLiteIdempotencyStore(self.root_dir / self.db_filename)

    def claim(self, *, key: str, payload: Mapping[str, Any] | None = None) -> bool:
        return self.claim_details(key=key, payload=payload).accepted

    def claim_details(self, *, key: str, payload: Mapping[str, Any] | None = None) -> IdempotencyClaim:
        idem = self._build_key(key=key, payload=payload)
        decision = self._store.reserve(
            key=idem,
            owner_id=self.owner_id,
            metadata_patch={'guard': 'file_idempotency_guard', 'claimed_at': _utc_now_iso()},
        )
        metadata = self._metadata_payload(idem=idem, decision=decision)
        self._metadata_path(idem).write_text(json.dumps(metadata, ensure_ascii=False, sort_keys=True), encoding='utf-8')
        accepted = decision.resolution is IdempotencyResolution.ACCEPTED
        if accepted:
            self._lock_path(idem).write_text('claimed', encoding='utf-8')
        return IdempotencyClaim(accepted=accepted, resolution=decision.resolution.value, key=idem, metadata=metadata)

    def mark_completed(self, *, key: str, result_ref: str | None = None, result_digest: str | None = None, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        idem = self._build_key(key=key, payload=payload)
        record = self._store.mark_completed(
            key=idem,
            owner_id=self.owner_id,
            result_ref=result_ref,
            result_digest=result_digest,
            metadata_patch={'guard': 'file_idempotency_guard', 'completed_at': _utc_now_iso()},
        )
        payload_dict = self._record_payload(record=record, resolution=IdempotencyResolution.REPLAY_COMPLETED.value)
        self._metadata_path(idem).write_text(json.dumps(payload_dict, ensure_ascii=False, sort_keys=True), encoding='utf-8')
        return payload_dict

    def has(self, *, key: str, payload: Mapping[str, Any] | None = None) -> bool:
        idem = self._build_key(key=key, payload=payload)
        record = self._store.get(key=idem)
        return record is not None or self._lock_path(idem).exists() or self._metadata_path(idem).exists()

    def metadata(self, *, key: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
        idem = self._build_key(key=key, payload=payload)
        path = self._metadata_path(idem)
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
        record = self._store.get(key=idem)
        if record is None:
            return None
        return self._record_payload(record=record, resolution=None)

    def close(self) -> None:
        close_fn = getattr(self._store, 'close', None)
        if callable(close_fn):
            close_fn()

    def _record_payload(self, *, record, resolution: str | None) -> dict[str, Any]:
        payload_dict = {
            'tenant_id': record.idempotency_key.tenant_id,
            'namespace': record.idempotency_key.namespace,
            'operation': record.idempotency_key.operation,
            'key': record.idempotency_key.key,
            'scope_hash': record.idempotency_key.scope_hash,
            'state': record.state.value,
            'attempt_count': int(record.attempt_count),
            'owner_id': record.owner_id,
            'first_seen_at': record.first_seen_at.isoformat(),
            'updated_at': record.updated_at.isoformat(),
            'lease_expires_at': record.lease_expires_at.isoformat() if record.lease_expires_at is not None else None,
            'completed_at': record.completed_at.isoformat() if record.completed_at is not None else None,
            'result_ref': record.result_ref,
            'result_digest': record.result_digest,
            'failure_reason': record.failure_reason,
        }
        if resolution is not None:
            payload_dict['resolution'] = resolution
        return payload_dict

    def _metadata_payload(self, *, idem: IdempotencyKey, decision: IdempotencyDecision) -> dict[str, Any]:
        record = decision.record
        payload = self._record_payload(record=record, resolution=decision.resolution.value)
        payload.update({
            'tenant_id': idem.tenant_id,
            'namespace': idem.namespace,
            'operation': idem.operation,
            'key': idem.key,
            'scope_hash': idem.scope_hash,
            'claimed_at': _utc_now_iso(),
        })
        return payload

    def _build_key(self, *, key: str, payload: Mapping[str, Any] | None = None) -> IdempotencyKey:
        normalized = str(key or '').strip()
        idem = build_headless_scope(
            tenant_id=str(self.tenant_id or 'headless'),
            namespace=str(self.namespace or 'headless'),
            operation=str(self.operation or 'goal_request'),
            raw_key=normalized,
            payload={'idempotency_key': normalized, **dict(payload or {})},
        )
        idem.validate()
        return idem

    def _slug(self, idem: IdempotencyKey) -> str:
        return hashlib.sha256('::'.join(idem.as_tuple() + (idem.scope_hash,)).encode('utf-8')).hexdigest()

    def _lock_path(self, idem: IdempotencyKey) -> Path:
        return self.root_dir / f'{self._slug(idem)}.lock'

    def _metadata_path(self, idem: IdempotencyKey) -> Path:
        return self.root_dir / f'{self._slug(idem)}.json'


__all__ = [
    'CANON_HEADLESS_IDEMPOTENCY_GUARD',
    'FileIdempotencyGuard',
    'IdempotencyClaim',
    'build_headless_request_fingerprint',
]
