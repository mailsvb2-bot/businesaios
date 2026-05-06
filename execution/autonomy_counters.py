from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
import json


CANON_AUTONOMY_COUNTERS = True
_DEFAULT_RETENTION_HOURS = 24 * 7


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _text(value: object) -> str:
    return str(value or '').strip()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: object) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    normalized = text.replace('Z', '+00:00')
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class PersistentAutonomyCounters:
    actions_hour: int = 0
    actions_day: int = 0
    outbound_total: int = 0
    irreversible_total: int = 0
    budget_change_total: float = 0.0
    publication_total: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            'actions_hour': int(self.actions_hour),
            'actions_day': int(self.actions_day),
            'outbound_total': int(self.outbound_total),
            'irreversible_total': int(self.irreversible_total),
            'budget_change_total': float(self.budget_change_total),
            'publication_total': int(self.publication_total),
        }


class FileAutonomyCounterStore:
    def __init__(self, *, root_dir: Path, retention_hours: int = _DEFAULT_RETENTION_HOURS) -> None:
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._retention_hours = max(24, int(retention_hours))

    def _path(self, *, tenant_id: str, business_id: str) -> Path:
        key = f'{tenant_id}__{business_id}'.replace('/', '_').replace('\\', '_')
        return self._root_dir / f'{key}.json'

    def _load_payload(self, *, tenant_id: str, business_id: str) -> dict[str, Any]:
        path = self._path(tenant_id=tenant_id, business_id=business_id)
        if not path.exists():
            return {'records': []}
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            return {'records': []}
        payload = _safe_dict(data)
        records = payload.get('records')
        if not isinstance(records, list):
            legacy = PersistentAutonomyCounters(
                actions_hour=max(0, _safe_int(payload.get('actions_hour'))),
                actions_day=max(0, _safe_int(payload.get('actions_day'))),
                outbound_total=max(0, _safe_int(payload.get('outbound_total'))),
                irreversible_total=max(0, _safe_int(payload.get('irreversible_total'))),
                budget_change_total=max(0.0, _safe_float(payload.get('budget_change_total'))),
                publication_total=max(0, _safe_int(payload.get('publication_total'))),
            )
            now = _utcnow().isoformat()
            records = [{**legacy.to_dict(), 'recorded_at': now, 'action_id': 'legacy-counter-import'}]
        return {'records': self._prune_records(records)}

    def _save_payload(self, *, tenant_id: str, business_id: str, payload: dict[str, Any]) -> None:
        self._path(tenant_id=tenant_id, business_id=business_id).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

    def _prune_records(self, records: list[object]) -> list[dict[str, Any]]:
        cutoff = _utcnow() - timedelta(hours=self._retention_hours)
        pruned: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in records:
            item = _safe_dict(raw)
            recorded_at = _parse_dt(item.get('recorded_at')) or _utcnow()
            if recorded_at < cutoff:
                continue
            dedupe_key = _text(item.get('action_id')) or _text(item.get('decision_id')) or '|'.join([
                _text(item.get('run_id')),
                _text(item.get('status')),
                _text(item.get('step_index')),
                recorded_at.isoformat(),
            ])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            pruned.append({
                'action_id': _text(item.get('action_id')) or None,
                'decision_id': _text(item.get('decision_id')) or None,
                'run_id': _text(item.get('run_id')) or None,
                'status': _text(item.get('status')) or None,
                'executed': bool(item.get('executed', True)),
                'verified': bool(item.get('verified', False)),
                'outbound_count': max(0, _safe_int(item.get('outbound_count'))),
                'irreversible_count': max(0, _safe_int(item.get('irreversible_count'))),
                'budget_change_amount': max(0.0, _safe_float(item.get('budget_change_amount'))),
                'publication_count': max(0, _safe_int(item.get('publication_count'))),
                'recorded_at': recorded_at.isoformat(),
                'step_index': item.get('step_index') if item.get('step_index') is None else _safe_int(item.get('step_index')),
            })
        pruned.sort(key=lambda item: _text(item.get('recorded_at')), reverse=True)
        return pruned

    def load(self, *, tenant_id: str, business_id: str) -> PersistentAutonomyCounters:
        payload = self._load_payload(tenant_id=tenant_id, business_id=business_id)
        records = list(payload.get('records') or [])
        now = _utcnow()
        hour_cutoff = now - timedelta(hours=1)
        day_cutoff = now - timedelta(days=1)
        hour_records = [item for item in records if (_parse_dt(item.get('recorded_at')) or now) >= hour_cutoff]
        day_records = [item for item in records if (_parse_dt(item.get('recorded_at')) or now) >= day_cutoff]
        return PersistentAutonomyCounters(
            actions_hour=len(hour_records),
            actions_day=len(day_records),
            outbound_total=sum(max(0, _safe_int(item.get('outbound_count'))) for item in day_records),
            irreversible_total=sum(max(0, _safe_int(item.get('irreversible_count'))) for item in day_records),
            budget_change_total=sum(max(0.0, _safe_float(item.get('budget_change_amount'))) for item in day_records),
            publication_total=sum(max(0, _safe_int(item.get('publication_count'))) for item in day_records),
        )

    def save(self, *, tenant_id: str, business_id: str, counters: PersistentAutonomyCounters) -> None:
        now = _utcnow().isoformat()
        payload = {
            'records': [{
                'action_id': 'manual-counter-snapshot',
                'decision_id': None,
                'run_id': None,
                'status': 'snapshot',
                'executed': True,
                'verified': True,
                'outbound_count': max(0, int(counters.outbound_total)),
                'irreversible_count': max(0, int(counters.irreversible_total)),
                'budget_change_amount': max(0.0, float(counters.budget_change_total)),
                'publication_count': max(0, int(counters.publication_total)),
                'recorded_at': now,
                'step_index': None,
            }] * max(1, int(counters.actions_day))
        }
        self._save_payload(tenant_id=tenant_id, business_id=business_id, payload={'records': self._prune_records(payload['records'])})

    def record_step(self, *, tenant_id: str, business_id: str, recent_action: Mapping[str, Any]) -> PersistentAutonomyCounters:
        item = _safe_dict(recent_action)
        if 'executed' in item and not bool(item.get('executed', False)):
            return self.load(tenant_id=tenant_id, business_id=business_id)
        payload = self._load_payload(tenant_id=tenant_id, business_id=business_id)
        records = list(payload.get('records') or [])
        records.insert(0, {
            'action_id': _text(item.get('action_id')) or None,
            'decision_id': _text(item.get('decision_id')) or None,
            'run_id': _text(item.get('run_id')) or None,
            'status': _text(item.get('status')) or None,
            'executed': bool(item.get('executed', True)),
            'verified': bool(item.get('verified', False)),
            'outbound_count': max(0, _safe_int(item.get('outbound_count'))),
            'irreversible_count': max(0, _safe_int(item.get('irreversible_count'))),
            'budget_change_amount': max(0.0, _safe_float(item.get('budget_change_amount'))),
            'publication_count': max(0, _safe_int(item.get('publication_count'))),
            'recorded_at': _text(item.get('recorded_at')) or _utcnow().isoformat(),
            'step_index': item.get('step_index') if item.get('step_index') is None else _safe_int(item.get('step_index')),
        })
        self._save_payload(tenant_id=tenant_id, business_id=business_id, payload={'records': self._prune_records(records)})
        return self.load(tenant_id=tenant_id, business_id=business_id)


class AutonomyCounterResolver:
    def __init__(self, *, store: FileAutonomyCounterStore | None = None) -> None:
        self._store = store

    @staticmethod
    def _from_recent_actions(recent_actions: list[dict[str, Any]]) -> PersistentAutonomyCounters:
        executed = [dict(item) for item in recent_actions if bool(dict(item).get('executed', False))]
        return PersistentAutonomyCounters(
            actions_hour=len(executed),
            actions_day=len(executed),
            outbound_total=sum(max(0, _safe_int(item.get('outbound_count'))) for item in executed),
            irreversible_total=sum(max(0, _safe_int(item.get('irreversible_count'))) for item in executed),
            budget_change_total=sum(max(0.0, _safe_float(item.get('budget_change_amount'))) for item in executed),
            publication_total=sum(max(0, _safe_int(item.get('publication_count'))) for item in executed),
        )

    def resolve(self, *, tenant_id: str, business_id: str, event_log: Any | None, recent_actions: list[dict[str, Any]] | None, action_type: str) -> PersistentAutonomyCounters:
        del action_type
        recent = list(recent_actions or [])
        from_recent = self._from_recent_actions(recent)
        persisted = self._store.load(tenant_id=tenant_id, business_id=business_id) if self._store is not None else PersistentAutonomyCounters()
        hour_events = 0
        day_events = 0
        count_recent = getattr(event_log, 'count_recent', None)
        if callable(count_recent):
            try:
                hour_events = max(0, int(count_recent(tenant_id=str(tenant_id), action='*', period='hour')))
                day_events = max(0, int(count_recent(tenant_id=str(tenant_id), action='*', period='day')))
            except Exception:
                hour_events = 0
                day_events = 0
        return PersistentAutonomyCounters(
            actions_hour=max(from_recent.actions_hour, persisted.actions_hour, hour_events),
            actions_day=max(from_recent.actions_day, persisted.actions_day, day_events),
            outbound_total=max(from_recent.outbound_total, persisted.outbound_total),
            irreversible_total=max(from_recent.irreversible_total, persisted.irreversible_total),
            budget_change_total=max(from_recent.budget_change_total, persisted.budget_change_total),
            publication_total=max(from_recent.publication_total, persisted.publication_total),
        )


__all__ = [
    'AutonomyCounterResolver',
    'CANON_AUTONOMY_COUNTERS',
    'FileAutonomyCounterStore',
    'PersistentAutonomyCounters',
]
