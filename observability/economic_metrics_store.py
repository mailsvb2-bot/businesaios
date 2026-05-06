from __future__ import annotations

CANON_COMPAT_SHIM = True

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol

CANON_ECONOMIC_METRICS_STORE = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or "").strip()


@dataclass(frozen=True, slots=True)
class EconomicMetricsSnapshotRecord:
    snapshot_id: str
    counters: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'snapshot_id': self.snapshot_id,
            'counters': {str(k): float(v) for k, v in self.counters.items()},
            'metadata': dict(self.metadata),
        }


class EconomicMetricsStore(Protocol):
    def upsert(self, row: EconomicMetricsSnapshotRecord) -> EconomicMetricsSnapshotRecord: ...
    def upsert_payload(self, payload: Mapping[str, Any]) -> EconomicMetricsSnapshotRecord: ...
    def list_rows(self) -> tuple[EconomicMetricsSnapshotRecord, ...]: ...


class NoOpEconomicMetricsStore:
    def upsert(self, row: EconomicMetricsSnapshotRecord) -> EconomicMetricsSnapshotRecord:
        return row

    def upsert_payload(self, payload: Mapping[str, Any]) -> EconomicMetricsSnapshotRecord:
        normalized = _safe_dict(payload)
        metadata = _safe_dict(normalized.get('metadata'))
        quality = _safe_dict(metadata.get('quality'))
        quality.setdefault('corrupted', False)
        quality.setdefault('quarantined', False)
        quality.setdefault('validation_reason', '')
        metadata['quality'] = quality
        return EconomicMetricsSnapshotRecord(
            snapshot_id=_text(normalized.get('snapshot_id') or 'economic-metrics'),
            counters={str(k): float(v) for k, v in _safe_dict(normalized.get('counters')).items()},
            metadata=metadata,
        )

    def list_rows(self) -> tuple[EconomicMetricsSnapshotRecord, ...]:
        return ()


class InMemoryEconomicMetricsStore:
    def __init__(self) -> None:
        self._rows: dict[str, EconomicMetricsSnapshotRecord] = {}
        self._order: list[str] = []

    def upsert(self, row: EconomicMetricsSnapshotRecord) -> EconomicMetricsSnapshotRecord:
        if row.snapshot_id not in self._rows:
            self._order.append(row.snapshot_id)
        self._rows[row.snapshot_id] = row
        return row

    def upsert_payload(self, payload: Mapping[str, Any]) -> EconomicMetricsSnapshotRecord:
        normalized = _safe_dict(payload)
        metadata = _safe_dict(normalized.get('metadata'))
        quality = _safe_dict(metadata.get('quality'))
        quality.setdefault('corrupted', False)
        quality.setdefault('quarantined', False)
        quality.setdefault('validation_reason', '')
        metadata['quality'] = quality
        return self.upsert(EconomicMetricsSnapshotRecord(
            snapshot_id=_text(normalized.get('snapshot_id') or 'economic-metrics'),
            counters={str(k): float(v) for k, v in _safe_dict(normalized.get('counters')).items()},
            metadata=metadata,
        ))

    def list_rows(self) -> tuple[EconomicMetricsSnapshotRecord, ...]:
        return tuple(self._rows[key] for key in self._order if key in self._rows)


class JsonlEconomicMetricsStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def upsert(self, row: EconomicMetricsSnapshotRecord) -> EconomicMetricsSnapshotRecord:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write('\n')
        return row

    def upsert_payload(self, payload: Mapping[str, Any]) -> EconomicMetricsSnapshotRecord:
        normalized = _safe_dict(payload)
        metadata = _safe_dict(normalized.get('metadata'))
        quality = _safe_dict(metadata.get('quality'))
        quality.setdefault('corrupted', False)
        quality.setdefault('quarantined', False)
        quality.setdefault('validation_reason', '')
        metadata['quality'] = quality
        return self.upsert(EconomicMetricsSnapshotRecord(
            snapshot_id=_text(normalized.get('snapshot_id') or 'economic-metrics'),
            counters={str(k): float(v) for k, v in _safe_dict(normalized.get('counters')).items()},
            metadata=metadata,
        ))

    def list_rows(self) -> tuple[EconomicMetricsSnapshotRecord, ...]:
        if not self._path.exists():
            return ()
        rows: list[EconomicMetricsSnapshotRecord] = []
        with self._path.open('r', encoding='utf-8') as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                payload = _safe_dict(json.loads(line))
                rows.append(EconomicMetricsSnapshotRecord(
                    snapshot_id=_text(payload.get('snapshot_id') or 'economic-metrics'),
                    counters={str(k): float(v) for k, v in _safe_dict(payload.get('counters')).items()},
                    metadata=_safe_dict(payload.get('metadata')),
                ))
        dedup: dict[str, EconomicMetricsSnapshotRecord] = {}
        order: list[str] = []
        for row in rows:
            if row.snapshot_id not in dedup:
                order.append(row.snapshot_id)
            dedup[row.snapshot_id] = row
        return tuple(dedup[key] for key in order if key in dedup)


__all__ = [
    'CANON_ECONOMIC_METRICS_STORE',
    'EconomicMetricsSnapshotRecord',
    'EconomicMetricsStore',
    'NoOpEconomicMetricsStore',
    'InMemoryEconomicMetricsStore',
    'JsonlEconomicMetricsStore',
]
