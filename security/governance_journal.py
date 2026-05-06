from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

CANON_GOVERNANCE_JOURNAL = True

@dataclass(frozen=True)
class GovernanceJournalEvent:
    event_kind: str
    entity_kind: str
    entity_id: str
    payload: Mapping[str, Any]
    related_incident_id: int | None = None
    related_approval_id: str | None = None
    related_drill_kind: str | None = None

class SQLiteGovernanceJournal:
    """Consolidated owner of approval/incident/quarantine/recovery/drill journal events."""
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self._ensure_schema()

    @staticmethod
    def _tenant_match(*, event_payload: Mapping[str, Any], entity_id: str, tenant_id: str) -> bool:
        tenant_norm = str(tenant_id or '').strip()
        if not tenant_norm:
            raise ValueError('tenant_id is required')
        entity_norm = str(entity_id or '')
        payload_tenant = str(dict(event_payload or {}).get('tenant_id', '')).strip()
        return entity_norm.startswith(f'tenant:{tenant_norm}:') or payload_tenant == tenant_norm

    def append(self, event: GovernanceJournalEvent) -> dict[str, Any]:
        now = int(time.time())
        payload_json = json.dumps(dict(event.payload), ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO governance_journal(
                    event_kind, entity_kind, entity_id, payload_json,
                    related_incident_id, related_approval_id, related_drill_kind, created_at_epoch_s
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event.event_kind), str(event.entity_kind), str(event.entity_id), payload_json,
                    None if event.related_incident_id is None else int(event.related_incident_id),
                    None if event.related_approval_id is None else str(event.related_approval_id),
                    None if event.related_drill_kind is None else str(event.related_drill_kind),
                    now,
                ),
            )
            conn.commit()
            return {'journal_id': int(cursor.lastrowid), 'created_at_epoch_s': now}

    def latest(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT journal_id, event_kind, entity_kind, entity_id, payload_json,
                       related_incident_id, related_approval_id, related_drill_kind, created_at_epoch_s
                FROM governance_journal
                ORDER BY journal_id DESC
                LIMIT ?
                """,
                (max(int(limit), 1),),
            ).fetchall()
        return [
            {
                'journal_id': int(row[0]),
                'event_kind': str(row[1]),
                'entity_kind': str(row[2]),
                'entity_id': str(row[3]),
                'payload': json.loads(str(row[4])),
                'related_incident_id': None if row[5] is None else int(row[5]),
                'related_approval_id': None if row[6] is None else str(row[6]),
                'related_drill_kind': None if row[7] is None else str(row[7]),
                'created_at_epoch_s': int(row[8]),
            }
            for row in rows
        ]

    def latest_for_tenant(self, *, tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
        events = self.latest(limit=max(int(limit) * 4, 100))
        filtered = [
            item for item in events
            if self._tenant_match(event_payload=dict(item.get('payload') or {}), entity_id=str(item.get('entity_id', '')), tenant_id=tenant_id)
        ]
        return filtered[:max(int(limit), 1)]

    def latest_entity_timeline(self, *, entity_kind: str, entity_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT journal_id, event_kind, payload_json, related_incident_id,
                       related_approval_id, related_drill_kind, created_at_epoch_s
                FROM governance_journal
                WHERE entity_kind = ? AND entity_id = ?
                ORDER BY journal_id DESC
                LIMIT ?
                """,
                (str(entity_kind), str(entity_id), max(int(limit), 1)),
            ).fetchall()
        return [
            {
                'journal_id': int(row[0]),
                'event_kind': str(row[1]),
                'payload': json.loads(str(row[2])),
                'related_incident_id': None if row[3] is None else int(row[3]),
                'related_approval_id': None if row[4] is None else str(row[4]),
                'related_drill_kind': None if row[5] is None else str(row[5]),
                'created_at_epoch_s': int(row[6]),
            }
            for row in rows
        ]

    def latest_entity_timeline_for_tenant(self, *, tenant_id: str, entity_kind: str, entity_id: str, limit: int = 100) -> list[dict[str, Any]]:
        timeline = self.latest_entity_timeline(entity_kind=entity_kind, entity_id=entity_id, limit=limit)
        if not timeline:
            return []
        if not self._tenant_match(event_payload=dict(timeline[0].get('payload') or {}), entity_id=entity_id, tenant_id=tenant_id):
            raise PermissionError('cross-tenant governance timeline access denied')
        return timeline

    def _ensure_schema(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS governance_journal (
                    journal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_kind TEXT NOT NULL,
                    entity_kind TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    related_incident_id INTEGER NULL,
                    related_approval_id TEXT NULL,
                    related_drill_kind TEXT NULL,
                    created_at_epoch_s INTEGER NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_governance_journal_entity ON governance_journal(entity_kind, entity_id, journal_id DESC)")
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        return conn

__all__ = ['CANON_GOVERNANCE_JOURNAL', 'GovernanceJournalEvent', 'SQLiteGovernanceJournal']
