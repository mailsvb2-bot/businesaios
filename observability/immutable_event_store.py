from __future__ import annotations

"""Immutable append-only event store with tamper-evident hash chain."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from core.utils.hash_chain import GENESIS, entry_hash


CANON_IMMUTABLE_EVENT_STORE = True


@dataclass(frozen=True)
class ImmutableEventRecord:
    sequence_no: int
    event_id: str
    tenant_id: str
    event_type: str
    emitted_at: str
    payload: Mapping[str, Any]
    previous_hash: str
    record_hash: str


class ImmutableEventStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.touch()

    @property
    def path(self) -> Path:
        return self._path

    def append(
        self,
        *,
        event_id: str,
        tenant_id: str,
        event_type: str,
        emitted_at: str,
        payload: Mapping[str, Any],
    ) -> ImmutableEventRecord:
        event_id_text = str(event_id or '').strip()
        if not event_id_text:
            raise ValueError('event_id is required')
        tenant_id_text = require_tenant_id(tenant_id)
        event_type_text = str(event_type or '').strip()
        if not event_type_text:
            raise ValueError('event_type is required')
        emitted_at_text = str(emitted_at or '').strip()
        if not emitted_at_text:
            raise ValueError('emitted_at is required')
        existing = self.read_events()
        if any(item.event_id == event_id_text for item in existing):
            raise ValueError('duplicate event_id')
        sequence_no = len(existing) + 1
        previous_hash = existing[-1].record_hash if existing else GENESIS
        canonical_payload = self._canonical_payload(payload)
        record_hash = entry_hash(
            prev_hash=previous_hash,
            fields={
                'sequence_no': sequence_no,
                'event_id': event_id_text,
                'tenant_id': tenant_id_text,
                'event_type': event_type_text,
                'emitted_at': emitted_at_text,
                'payload': canonical_payload,
            },
        )
        row = {
            'sequence_no': sequence_no,
            'event_id': event_id_text,
            'tenant_id': tenant_id_text,
            'event_type': event_type_text,
            'emitted_at': emitted_at_text,
            'payload': canonical_payload,
            'previous_hash': previous_hash,
            'record_hash': record_hash,
        }
        with self._path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        return ImmutableEventRecord(**row)

    def read_events(self) -> tuple[ImmutableEventRecord, ...]:
        records: list[ImmutableEventRecord] = []
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.touch()
        with self._path.open('r', encoding='utf-8') as handle:
            for line_no, line in enumerate(handle, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    raw = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise ValueError(f'malformed line {line_no}') from exc
                records.append(ImmutableEventRecord(**raw))
        return tuple(records)

    def validate_chain(self) -> None:
        previous_hash = GENESIS
        seen_ids: set[str] = set()
        expected_sequence_no = 1
        for item in self.read_events():
            if item.sequence_no != expected_sequence_no:
                raise ValueError('sequence_no mismatch')
            if item.previous_hash != previous_hash:
                raise ValueError('previous_hash mismatch')
            if item.event_id in seen_ids:
                raise ValueError('duplicate event_id in chain')
            expected_hash = entry_hash(
                prev_hash=item.previous_hash,
                fields={
                    'sequence_no': item.sequence_no,
                    'event_id': item.event_id,
                    'tenant_id': item.tenant_id,
                    'event_type': item.event_type,
                    'emitted_at': item.emitted_at,
                    'payload': self._canonical_payload(item.payload),
                },
            )
            if item.record_hash != expected_hash:
                raise ValueError('record_hash mismatch')
            seen_ids.add(item.event_id)
            previous_hash = item.record_hash
            expected_sequence_no += 1

    def compact_copy(self, destination: str | Path) -> Path:
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('w', encoding='utf-8') as handle:
            for item in self.read_events():
                handle.write(json.dumps(item.__dict__, ensure_ascii=False, sort_keys=True))
                handle.write('\n')
        clone = ImmutableEventStore(target)
        clone.validate_chain()
        return target

    @staticmethod
    def _canonical_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return json.loads(json.dumps(dict(payload or {}), ensure_ascii=False, sort_keys=True, default=str))


__all__ = [
    'CANON_IMMUTABLE_EVENT_STORE',
    'ImmutableEventRecord',
    'ImmutableEventStore',
]
