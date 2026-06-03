from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from collections.abc import Mapping

CANON_REPLAY_SAFE_ROI_HISTORY = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return bool(value)


def _text(value: object) -> str:
    return str(value or '').strip()


@dataclass(frozen=True, slots=True)
class ROIHistoryRecord:
    event_id: str
    channel: str
    action_type: str
    expected_roi: float
    realized_revenue: float
    approved_budget: float
    requested_budget: float
    verified: bool
    snapshot_id: str = ''
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'event_id': self.event_id,
            'channel': self.channel,
            'action_type': self.action_type,
            'expected_roi': float(self.expected_roi),
            'realized_revenue': float(self.realized_revenue),
            'approved_budget': float(self.approved_budget),
            'requested_budget': float(self.requested_budget),
            'verified': bool(self.verified),
            'snapshot_id': self.snapshot_id,
            'metadata': dict(self.metadata),
        }


class ROIHistoryStore(Protocol):
    @property
    def path(self) -> Path: ...

    def upsert(self, row: ROIHistoryRecord) -> ROIHistoryRecord: ...
    def upsert_payload(self, payload: Mapping[str, Any]) -> ROIHistoryRecord: ...
    def list_rows(self) -> tuple[ROIHistoryRecord, ...]: ...


class ReplaySafeROIHistoryBuilder:
    def build(
        self,
        *,
        event_id: str,
        economic_feedback: Mapping[str, Any] | None,
        policy_snapshot: Mapping[str, Any] | None = None,
    ) -> ROIHistoryRecord:
        feedback = _safe_dict(economic_feedback)
        snapshot = _safe_dict(policy_snapshot)
        return ROIHistoryRecord(
            event_id=_text(event_id),
            channel=_text(feedback.get('channel') or snapshot.get('channel') or 'default'),
            action_type=_text(feedback.get('action_type') or snapshot.get('action_type') or 'unknown'),
            expected_roi=_safe_float(feedback.get('expected_roi'), default=_safe_float(snapshot.get('expected_roi'))),
            realized_revenue=_safe_float(feedback.get('realized_revenue')),
            approved_budget=_safe_float(feedback.get('approved_budget'), default=_safe_float(snapshot.get('approved_budget'))),
            requested_budget=_safe_float(feedback.get('requested_budget'), default=_safe_float(snapshot.get('requested_budget'))),
            verified=_safe_bool(feedback.get('verified')),
            snapshot_id=_text(snapshot.get('snapshot_id')),
            metadata={
                'owner': 'execution.replay_safe_roi_history',
                'efficiency_label': _text(feedback.get('efficiency_label')),
            },
        )


class NoOpROIHistoryStore:
    def upsert(self, row: ROIHistoryRecord) -> ROIHistoryRecord:
        return row

    def upsert_payload(self, payload: Mapping[str, Any]) -> ROIHistoryRecord:
        data = _safe_dict(payload)
        data.setdefault('metadata', {})
        data['metadata']['replay_anchor'] = str(_safe_dict(data.get('metadata')).get('replay_anchor') or data.get('event_id') or '')
        data['metadata']['replay_epoch'] = str(_safe_dict(data.get('metadata')).get('replay_epoch') or '')
        return ROIHistoryRecord(
            event_id=_text(data.get('event_id') or 'roi-history'),
            channel=_text(data.get('channel') or 'default'),
            action_type=_text(data.get('action_type') or 'unknown'),
            expected_roi=_safe_float(data.get('expected_roi')),
            realized_revenue=_safe_float(data.get('realized_revenue')),
            approved_budget=_safe_float(data.get('approved_budget')),
            requested_budget=_safe_float(data.get('requested_budget')),
            verified=_safe_bool(data.get('verified')),
            snapshot_id=_text(data.get('snapshot_id')),
            metadata=_safe_dict(data.get('metadata')),
        )

    def list_rows(self) -> tuple[ROIHistoryRecord, ...]:
        return ()


class InMemoryROIHistoryStore:
    def __init__(self) -> None:
        self._rows: dict[str, ROIHistoryRecord] = {}
        self._order: list[str] = []

    def upsert(self, row: ROIHistoryRecord) -> ROIHistoryRecord:
        if row.event_id not in self._rows:
            self._order.append(row.event_id)
        self._rows[row.event_id] = row
        return row

    def upsert_payload(self, payload: Mapping[str, Any]) -> ROIHistoryRecord:
        data = _safe_dict(payload)
        row = ROIHistoryRecord(
            event_id=_text(data.get('event_id') or 'roi-history'),
            channel=_text(data.get('channel') or 'default'),
            action_type=_text(data.get('action_type') or 'unknown'),
            expected_roi=_safe_float(data.get('expected_roi')),
            realized_revenue=_safe_float(data.get('realized_revenue')),
            approved_budget=_safe_float(data.get('approved_budget')),
            requested_budget=_safe_float(data.get('requested_budget')),
            verified=_safe_bool(data.get('verified')),
            snapshot_id=_text(data.get('snapshot_id')),
            metadata=_safe_dict(data.get('metadata')),
        )
        return self.upsert(row)

    def list_rows(self) -> tuple[ROIHistoryRecord, ...]:
        return tuple(self._rows[key] for key in self._order if key in self._rows)


class JsonlROIHistoryStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def upsert(self, row: ROIHistoryRecord) -> ROIHistoryRecord:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write('\n')
        return row

    def upsert_payload(self, payload: Mapping[str, Any]) -> ROIHistoryRecord:
        row = NoOpROIHistoryStore().upsert_payload(payload)
        return self.upsert(row)

    def list_rows(self) -> tuple[ROIHistoryRecord, ...]:
        if not self._path.exists():
            return ()
        rows: list[ROIHistoryRecord] = []
        with self._path.open('r', encoding='utf-8') as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                payload = _safe_dict(json.loads(line))
                rows.append(NoOpROIHistoryStore().upsert_payload(payload))
        dedup: dict[str, ROIHistoryRecord] = {}
        order: list[str] = []
        for row in rows:
            if row.event_id not in dedup:
                order.append(row.event_id)
            dedup[row.event_id] = row
        return tuple(dedup[key] for key in order if key in dedup)


__all__ = [
    'CANON_REPLAY_SAFE_ROI_HISTORY',
    'ROIHistoryRecord',
    'ROIHistoryStore',
    'ReplaySafeROIHistoryBuilder',
    'NoOpROIHistoryStore',
    'InMemoryROIHistoryStore',
    'JsonlROIHistoryStore',
]
