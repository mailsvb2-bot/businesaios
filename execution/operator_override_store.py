from __future__ import annotations

"""Canonical persistence surface for operator overrides.

This module stores operator-override state snapshots only.
It must not contain approval or decision logic.
"""

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import os

from core.tenancy.normalization import require_tenant_id
from execution.operator_override_contract import (
    OperatorOverrideDecision,
    OperatorOverrideRecord,
    OperatorOverrideRequest,
    OperatorOverrideStatus,
    OperatorOverrideStoreContract,
)
from governance.persistence_codec import atomic_write_json, from_dataclass, read_json_or_default, to_jsonable
from governance.persistence_paths import operator_override_store_path


CANON_OPERATOR_OVERRIDE_STORE = True


def _expire_record_if_needed(record: OperatorOverrideRecord | None) -> tuple[OperatorOverrideRecord | None, bool]:
    if record is None:
        return None, False
    if record.is_terminal:
        return record, False
    expires_at = record.request.expires_at
    if expires_at is None:
        return record, False
    if datetime.now(timezone.utc) <= expires_at.astimezone(timezone.utc):
        return record, False
    return replace(record, status=OperatorOverrideStatus.EXPIRED, final_reason='expired'), True


class InMemoryOperatorOverrideStore(OperatorOverrideStoreContract):
    def __init__(self) -> None:
        self._items: dict[str, OperatorOverrideRecord] = {}

    def _normalize_items(self) -> None:
        for override_id, record in list(self._items.items()):
            normalized, expired = _expire_record_if_needed(record)
            if normalized is not None and expired:
                self._items[override_id] = normalized

    def create(self, request: OperatorOverrideRequest) -> OperatorOverrideRecord:
        request.validate()
        if request.override_id in self._items:
            raise ValueError(f'operator override already exists: {request.override_id}')
        record = OperatorOverrideRecord(request=request, status=OperatorOverrideStatus.REQUESTED)
        self._items[request.override_id] = record
        return record

    def get(self, override_id: str) -> OperatorOverrideRecord | None:
        key = str(override_id or '').strip()
        record, changed = _expire_record_if_needed(self._items.get(key))
        if record is not None and changed:
            self._items[key] = record
        return record

    def save(self, record: OperatorOverrideRecord) -> OperatorOverrideRecord:
        record.request.validate()
        self._items[record.request.override_id] = replace(record)
        return record

    def list_open(self, *, tenant_id: str) -> tuple[OperatorOverrideRecord, ...]:
        return self.list_for_tenant(tenant_id=tenant_id, include_terminal=False)

    def list_for_tenant(self, *, tenant_id: str, include_terminal: bool = True) -> tuple[OperatorOverrideRecord, ...]:
        tid = require_tenant_id(tenant_id)
        self._normalize_items()
        items = [
            record
            for record in self._items.values()
            if record.request.tenant_id == tid and (include_terminal or not record.is_terminal)
        ]
        items.sort(key=lambda item: item.request.requested_at)
        return tuple(items)


class PersistentOperatorOverrideStore(OperatorOverrideStoreContract):
    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else operator_override_store_path()
        self._items: dict[str, OperatorOverrideRecord] = {}
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def _normalize_items(self) -> bool:
        changed = False
        for override_id, record in list(self._items.items()):
            normalized, expired = _expire_record_if_needed(record)
            if normalized is not None and expired:
                self._items[override_id] = normalized
                changed = True
        return changed

    def create(self, request: OperatorOverrideRequest) -> OperatorOverrideRecord:
        request.validate()
        if request.override_id in self._items:
            raise ValueError(f'operator override already exists: {request.override_id}')
        record = OperatorOverrideRecord(request=request, status=OperatorOverrideStatus.REQUESTED)
        self._items[request.override_id] = record
        self._flush()
        return record

    def get(self, override_id: str) -> OperatorOverrideRecord | None:
        key = str(override_id or '').strip()
        record, changed = _expire_record_if_needed(self._items.get(key))
        if record is not None and changed:
            self._items[key] = record
            self._flush()
        return record

    def save(self, record: OperatorOverrideRecord) -> OperatorOverrideRecord:
        record.request.validate()
        self._items[record.request.override_id] = replace(record)
        self._flush()
        return record

    def list_open(self, *, tenant_id: str) -> tuple[OperatorOverrideRecord, ...]:
        return self.list_for_tenant(tenant_id=tenant_id, include_terminal=False)

    def list_for_tenant(self, *, tenant_id: str, include_terminal: bool = True) -> tuple[OperatorOverrideRecord, ...]:
        tid = require_tenant_id(tenant_id)
        if self._normalize_items():
            self._flush()
        items = [
            record
            for record in self._items.values()
            if record.request.tenant_id == tid and (include_terminal or not record.is_terminal)
        ]
        items.sort(key=lambda item: item.request.requested_at)
        return tuple(items)

    def _load(self) -> None:
        raw = read_json_or_default(self._path, default={'records': []})
        records = raw.get('records', []) if isinstance(raw, dict) else []
        loaded: dict[str, OperatorOverrideRecord] = {}
        for item in records:
            record = self._record_from_payload(item)
            loaded[record.request.override_id] = record
        self._items = loaded

    def _flush(self) -> None:
        atomic_write_json(
            self._path,
            {'records': [self._record_to_payload(item) for item in self._items.values()]},
        )

    @staticmethod
    def _record_to_payload(record: OperatorOverrideRecord) -> dict[str, object]:
        return {
            'request': to_jsonable(record.request),
            'status': record.status.value,
            'decision': to_jsonable(record.decision) if record.decision is not None else None,
            'final_reason': record.final_reason,
            'consumed_at': to_jsonable(record.consumed_at),
            'consumed_by_execution_id': record.consumed_by_execution_id,
        }

    @staticmethod
    def _record_from_payload(payload: dict[str, object]) -> OperatorOverrideRecord:
        request = from_dataclass(OperatorOverrideRequest, dict(payload.get('request', {})))
        raw_decision = payload.get('decision')
        decision = from_dataclass(OperatorOverrideDecision, raw_decision) if isinstance(raw_decision, dict) else None
        return OperatorOverrideRecord(
            request=request,
            status=OperatorOverrideStatus(payload.get('status', OperatorOverrideStatus.REQUESTED.value)),
            decision=decision,
            final_reason=payload.get('final_reason'),
            consumed_at=(datetime.fromisoformat(payload['consumed_at']) if payload.get('consumed_at') else None),
            consumed_by_execution_id=payload.get('consumed_by_execution_id'),
        )


def build_default_operator_override_store() -> OperatorOverrideStoreContract:
    mode = os.getenv('BUSINESAIOS_OPERATOR_OVERRIDE_STORE_BACKEND', 'file').strip().lower()
    if mode == 'memory':
        return InMemoryOperatorOverrideStore()
    return PersistentOperatorOverrideStore()


__all__ = [
    'CANON_OPERATOR_OVERRIDE_STORE',
    'InMemoryOperatorOverrideStore',
    'PersistentOperatorOverrideStore',
    'build_default_operator_override_store',
]
