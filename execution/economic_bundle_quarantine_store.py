from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Protocol
from collections.abc import Mapping

CANON_ECONOMIC_BUNDLE_QUARANTINE_STORE = True

ALLOWED_ARTIFACT_STATUSES = ('new', 'quarantined', 'reviewed', 'released', 'denied')


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or '').strip()


@dataclass(frozen=True, slots=True)
class EconomicQuarantinedBundleRecord:
    artifact_id: str
    artifact_digest: str
    reason: str
    payload_preview: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = 'quarantined'
    retry_count: int = 0
    retry_allowed: bool = True
    poisoned: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            'artifact_id': self.artifact_id,
            'artifact_digest': self.artifact_digest,
            'reason': self.reason,
            'payload_preview': dict(self.payload_preview),
            'metadata': dict(self.metadata),
            'status': self.status,
            'retry_count': int(self.retry_count),
            'retry_allowed': bool(self.retry_allowed),
            'poisoned': bool(self.poisoned),
        }


class EconomicBundleQuarantineStore(Protocol):
    def append(self, row: EconomicQuarantinedBundleRecord) -> EconomicQuarantinedBundleRecord: ...
    def list_rows(self) -> tuple[EconomicQuarantinedBundleRecord, ...]: ...
    def record(self, row: object) -> EconomicQuarantinedBundleRecord: ...
    def is_digest_denied(self, artifact_digest: str) -> bool: ...
    def transition_status(self, *, artifact_digest: str, status: str, poisoned: bool | None = None) -> EconomicQuarantinedBundleRecord | None: ...


class NoOpEconomicBundleQuarantineStore:
    def append(self, row: EconomicQuarantinedBundleRecord) -> EconomicQuarantinedBundleRecord:
        return row

    def record(self, row: object) -> EconomicQuarantinedBundleRecord:
        return self.append(_normalize_record(row, existing=()))

    def list_rows(self) -> tuple[EconomicQuarantinedBundleRecord, ...]:
        return ()

    def is_digest_denied(self, artifact_digest: str) -> bool:
        return False

    def transition_status(self, *, artifact_digest: str, status: str, poisoned: bool | None = None) -> EconomicQuarantinedBundleRecord | None:
        return None


class InMemoryEconomicBundleQuarantineStore:
    def __init__(self) -> None:
        self._rows: list[EconomicQuarantinedBundleRecord] = []

    def append(self, row: EconomicQuarantinedBundleRecord) -> EconomicQuarantinedBundleRecord:
        self._rows.append(row)
        return row

    def record(self, row: object) -> EconomicQuarantinedBundleRecord:
        normalized = _normalize_record(row, existing=self._rows)
        return self.append(normalized)

    def list_rows(self) -> tuple[EconomicQuarantinedBundleRecord, ...]:
        return tuple(self._rows)

    def is_digest_denied(self, artifact_digest: str) -> bool:
        digest = _text(artifact_digest)
        if not digest:
            return False
        return any(row.artifact_digest == digest and (row.status == 'denied' or row.poisoned) for row in self._rows)

    def transition_status(self, *, artifact_digest: str, status: str, poisoned: bool | None = None) -> EconomicQuarantinedBundleRecord | None:
        normalized_status = _text(status).lower()
        if normalized_status not in ALLOWED_ARTIFACT_STATUSES:
            raise ValueError(f'unsupported quarantine status: {status}')
        digest = _text(artifact_digest)
        for row in reversed(self._rows):
            if row.artifact_digest == digest:
                updated = replace(
                    row,
                    status=normalized_status,
                    poisoned=row.poisoned if poisoned is None else bool(poisoned),
                    retry_allowed=normalized_status not in {'denied', 'released'},
                )
                self._rows.append(updated)
                return updated
        return None


class JsonlEconomicBundleQuarantineStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, row: EconomicQuarantinedBundleRecord) -> EconomicQuarantinedBundleRecord:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write('\n')
        return row

    def record(self, row: object) -> EconomicQuarantinedBundleRecord:
        normalized = _normalize_record(row, existing=self.list_rows())
        return self.append(normalized)

    def list_rows(self) -> tuple[EconomicQuarantinedBundleRecord, ...]:
        if not self._path.exists():
            return ()
        rows: list[EconomicQuarantinedBundleRecord] = []
        with self._path.open('r', encoding='utf-8') as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                payload = _safe_dict(json.loads(line))
                rows.append(
                    EconomicQuarantinedBundleRecord(
                        artifact_id=_text(payload.get('artifact_id')),
                        artifact_digest=_text(payload.get('artifact_digest')),
                        reason=_text(payload.get('reason')),
                        payload_preview=_safe_dict(payload.get('payload_preview')),
                        metadata=_safe_dict(payload.get('metadata')),
                        status=_text(payload.get('status')) or 'quarantined',
                        retry_count=int(payload.get('retry_count') or 0),
                        retry_allowed=bool(payload.get('retry_allowed', True)),
                        poisoned=bool(payload.get('poisoned', False)),
                    )
                )
        return tuple(rows)

    def is_digest_denied(self, artifact_digest: str) -> bool:
        digest = _text(artifact_digest)
        if not digest:
            return False
        return any(row.artifact_digest == digest and (row.status == 'denied' or row.poisoned) for row in self.list_rows())

    def transition_status(self, *, artifact_digest: str, status: str, poisoned: bool | None = None) -> EconomicQuarantinedBundleRecord | None:
        normalized_status = _text(status).lower()
        if normalized_status not in ALLOWED_ARTIFACT_STATUSES:
            raise ValueError(f'unsupported quarantine status: {status}')
        digest = _text(artifact_digest)
        for row in reversed(self.list_rows()):
            if row.artifact_digest == digest:
                updated = replace(
                    row,
                    status=normalized_status,
                    poisoned=row.poisoned if poisoned is None else bool(poisoned),
                    retry_allowed=normalized_status not in {'denied', 'released'},
                )
                return self.append(updated)
        return None


def _normalize_record(row: object, *, existing: tuple[EconomicQuarantinedBundleRecord, ...] | list[EconomicQuarantinedBundleRecord]) -> EconomicQuarantinedBundleRecord:
    if isinstance(row, EconomicQuarantinedBundleRecord):
        return row
    payload = _safe_dict(getattr(row, 'to_dict', lambda: {})()) if hasattr(row, 'to_dict') else _safe_dict(row)
    artifact_id = _text(payload.get('bundle_path') or payload.get('artifact_id'))
    artifact_digest = _text(payload.get('artifact_digest') or _safe_dict(payload.get('metadata')).get('artifact_digest'))
    reason = _text(payload.get('reason')) or 'economic_bundle_quarantined'
    prior_retries = max((item.retry_count for item in existing if item.artifact_digest and item.artifact_digest == artifact_digest), default=-1)
    poisoned = 'poisoned' in reason.lower() or bool(payload.get('poisoned'))
    retry_allowed = not poisoned and prior_retries < 2
    return EconomicQuarantinedBundleRecord(
        artifact_id=artifact_id,
        artifact_digest=artifact_digest,
        reason=reason,
        payload_preview=_safe_dict(payload.get('payload_preview') or payload.get('scope')),
        metadata=_safe_dict(payload.get('metadata')),
        status='quarantined',
        retry_count=prior_retries + 1,
        retry_allowed=retry_allowed,
        poisoned=poisoned,
    )


__all__ = [
    'ALLOWED_ARTIFACT_STATUSES',
    'CANON_ECONOMIC_BUNDLE_QUARANTINE_STORE',
    'EconomicQuarantinedBundleRecord',
    'EconomicBundleQuarantineStore',
    'NoOpEconomicBundleQuarantineStore',
    'InMemoryEconomicBundleQuarantineStore',
    'JsonlEconomicBundleQuarantineStore',
]
