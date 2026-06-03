from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from collections.abc import Mapping

CANON_ECONOMIC_MEMORY_STORE = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or '').strip()


@dataclass(frozen=True, slots=True)
class EconomicMemoryRecord:
    event_id: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {'event_id': self.event_id, **dict(self.payload)}


class EconomicMemoryStore(Protocol):
    @property
    def path(self) -> Path: ...

    def upsert(self, row: EconomicMemoryRecord) -> EconomicMemoryRecord: ...
    def upsert_payload(self, payload: Mapping[str, Any]) -> EconomicMemoryRecord: ...
    def list_rows(self) -> tuple[EconomicMemoryRecord, ...]: ...


class NoOpEconomicMemoryStore:
    def upsert(self, row: EconomicMemoryRecord) -> EconomicMemoryRecord:
        return row

    def upsert_payload(self, payload: Mapping[str, Any]) -> EconomicMemoryRecord:
        data = dict(payload)
        data.setdefault('metadata', {})
        data['metadata']['replay_anchor'] = str(_safe_dict(data.get('metadata')).get('replay_anchor') or data.get('event_id') or '')
        return EconomicMemoryRecord(event_id=_text(data.get('event_id') or data.get('memory_key') or 'economic-memory'), payload=data)

    def list_rows(self) -> tuple[EconomicMemoryRecord, ...]:
        return ()


class InMemoryEconomicMemoryStore:
    def __init__(self) -> None:
        self._rows: dict[str, EconomicMemoryRecord] = {}
        self._order: list[str] = []

    def upsert(self, row: EconomicMemoryRecord) -> EconomicMemoryRecord:
        if row.event_id not in self._rows:
            self._order.append(row.event_id)
        self._rows[row.event_id] = row
        return row

    def upsert_payload(self, payload: Mapping[str, Any]) -> EconomicMemoryRecord:
        data = dict(payload)
        data.setdefault('metadata', {})
        data['metadata']['replay_anchor'] = str(_safe_dict(data.get('metadata')).get('replay_anchor') or data.get('event_id') or '')
        event_id = _text(data.get('event_id') or data.get('memory_key') or 'economic-memory')
        return self.upsert(EconomicMemoryRecord(event_id=event_id, payload=data))

    def list_rows(self) -> tuple[EconomicMemoryRecord, ...]:
        return tuple(self._rows[key] for key in self._order if key in self._rows)


class JsonlEconomicMemoryStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def upsert(self, row: EconomicMemoryRecord) -> EconomicMemoryRecord:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write('\n')
        return row

    def upsert_payload(self, payload: Mapping[str, Any]) -> EconomicMemoryRecord:
        data = dict(payload)
        data.setdefault('metadata', {})
        data['metadata']['replay_anchor'] = str(_safe_dict(data.get('metadata')).get('replay_anchor') or data.get('event_id') or '')
        event_id = _text(data.get('event_id') or data.get('memory_key') or 'economic-memory')
        return self.upsert(EconomicMemoryRecord(event_id=event_id, payload=data))

    def list_rows(self) -> tuple[EconomicMemoryRecord, ...]:
        if not self._path.exists():
            return ()
        rows: list[EconomicMemoryRecord] = []
        with self._path.open('r', encoding='utf-8') as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                payload = _safe_dict(json.loads(line))
                rows.append(EconomicMemoryRecord(event_id=_text(payload.get('event_id') or payload.get('memory_key') or 'economic-memory'), payload=payload))
        dedup: dict[str, EconomicMemoryRecord] = {}
        order: list[str] = []
        for row in rows:
            if row.event_id not in dedup:
                order.append(row.event_id)
            dedup[row.event_id] = row
        return tuple(dedup[key] for key in order if key in dedup)


__all__ = [
    'CANON_ECONOMIC_MEMORY_STORE',
    'EconomicMemoryRecord',
    'EconomicMemoryStore',
    'NoOpEconomicMemoryStore',
    'InMemoryEconomicMemoryStore',
    'JsonlEconomicMemoryStore',
]
