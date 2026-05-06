from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from compliance.economic_forensics_contract import EconomicForensicsEvent

CANON_ECONOMIC_FORENSICS_STORE = True


class EconomicForensicsStore(Protocol):
    def append(self, row: EconomicForensicsEvent) -> EconomicForensicsEvent: ...
    def list_rows(self) -> tuple[EconomicForensicsEvent, ...]: ...


class NoOpEconomicForensicsStore:
    def append(self, row: EconomicForensicsEvent) -> EconomicForensicsEvent:
        return row

    def list_rows(self) -> tuple[EconomicForensicsEvent, ...]:
        return ()


class InMemoryEconomicForensicsStore:
    def __init__(self) -> None:
        self._rows: list[EconomicForensicsEvent] = []

    def append(self, row: EconomicForensicsEvent) -> EconomicForensicsEvent:
        self._rows.append(row)
        return row

    def list_rows(self) -> tuple[EconomicForensicsEvent, ...]:
        return tuple(self._rows)


class JsonlEconomicForensicsStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, row: EconomicForensicsEvent) -> EconomicForensicsEvent:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write('\n')
        return row

    def list_rows(self) -> tuple[EconomicForensicsEvent, ...]:
        if not self._path.exists():
            return ()
        rows: list[EconomicForensicsEvent] = []
        with self._path.open('r', encoding='utf-8') as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                rows.append(EconomicForensicsEvent(
                    event_id=str(payload.get('event_id') or ''),
                    event_type=str(payload.get('event_type') or ''),
                    severity=str(payload.get('severity') or 'info'),
                    artifact_id=str(payload.get('artifact_id') or ''),
                    artifact_digest=str(payload.get('artifact_digest') or ''),
                    tenant_id=str(payload.get('tenant_id') or ''),
                    business_id=str(payload.get('business_id') or ''),
                    schema_version=str(payload.get('schema_version') or ''),
                    payload=dict(payload.get('payload') or {}),
                    tags=tuple(str(x) for x in (payload.get('tags') or ())),
                    metadata=dict(payload.get('metadata') or {}),
                ))
        return tuple(rows)


__all__ = [
    'CANON_ECONOMIC_FORENSICS_STORE',
    'EconomicForensicsStore',
    'NoOpEconomicForensicsStore',
    'InMemoryEconomicForensicsStore',
    'JsonlEconomicForensicsStore',
]
