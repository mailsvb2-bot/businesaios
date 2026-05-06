from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

CANON_SECURITY_DRILL_SCHEDULE_STORE = True

@dataclass(frozen=True)
class SecurityDrillSchedule:
    drill_id: str
    drill_kind: str
    actor: str
    target_entity_id: str
    interval_seconds: int
    next_run_epoch_s: int
    enabled: bool = True
    failure_escalation_kind: str = 'security-drill-failure'
    payload: Mapping[str, Any] | None = None

class SQLiteSecurityDrillScheduleStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self._ensure_schema()

    def put(self, schedule: SecurityDrillSchedule) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO security_drill_schedule(
                    drill_id, drill_kind, actor, target_entity_id, interval_seconds,
                    next_run_epoch_s, enabled, failure_escalation_kind, payload_json
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(schedule.drill_id), str(schedule.drill_kind), str(schedule.actor), str(schedule.target_entity_id),
                    int(schedule.interval_seconds), int(schedule.next_run_epoch_s), 1 if schedule.enabled else 0,
                    str(schedule.failure_escalation_kind),
                    json.dumps(dict(schedule.payload or {}), ensure_ascii=False, sort_keys=True, separators=(',', ':')),
                ),
            )
            conn.commit()

    def due(self, *, now_epoch_s: int | None = None, limit: int = 50) -> list[SecurityDrillSchedule]:
        resolved_now = int(time.time()) if now_epoch_s is None else int(now_epoch_s)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT drill_id, drill_kind, actor, target_entity_id, interval_seconds,
                       next_run_epoch_s, enabled, failure_escalation_kind, payload_json
                FROM security_drill_schedule
                WHERE enabled = 1 AND next_run_epoch_s <= ?
                ORDER BY next_run_epoch_s ASC, drill_id ASC
                LIMIT ?
                """,
                (resolved_now, max(int(limit), 1)),
            ).fetchall()
        return [self._row_to_schedule(row) for row in rows]

    def list_enabled(self) -> list[SecurityDrillSchedule]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT drill_id, drill_kind, actor, target_entity_id, interval_seconds,
                       next_run_epoch_s, enabled, failure_escalation_kind, payload_json
                FROM security_drill_schedule
                WHERE enabled = 1
                ORDER BY drill_id ASC
                """
            ).fetchall()
        return [self._row_to_schedule(row) for row in rows]

    def list_enabled_for_tenant(self, *, tenant_id: str) -> list[SecurityDrillSchedule]:
        tenant_norm = str(tenant_id or '').strip()
        if not tenant_norm:
            raise ValueError('tenant_id is required')
        return [item for item in self.list_enabled() if str((item.payload or {}).get('tenant_id', '')).strip() == tenant_norm]

    def get_for_tenant(self, *, tenant_id: str, drill_id: str) -> SecurityDrillSchedule:
        tenant_norm = str(tenant_id or '').strip()
        if not tenant_norm:
            raise ValueError('tenant_id is required')
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT drill_id, drill_kind, actor, target_entity_id, interval_seconds,
                       next_run_epoch_s, enabled, failure_escalation_kind, payload_json
                FROM security_drill_schedule
                WHERE drill_id = ?
                """,
                (str(drill_id),),
            ).fetchone()
        if row is None:
            raise KeyError(f'unknown drill schedule: {drill_id}')
        schedule = self._row_to_schedule(tuple(row))
        if str((schedule.payload or {}).get('tenant_id', '')).strip() != tenant_norm:
            raise PermissionError('cross-tenant drill schedule access denied')
        return schedule

    def mark_run(self, *, drill_id: str, next_run_epoch_s: int) -> None:
        with self._connect() as conn:
            conn.execute('UPDATE security_drill_schedule SET next_run_epoch_s = ? WHERE drill_id = ?', (int(next_run_epoch_s), str(drill_id)))
            conn.commit()

    def _row_to_schedule(self, row: tuple[Any, ...]) -> SecurityDrillSchedule:
        return SecurityDrillSchedule(
            drill_id=str(row[0]), drill_kind=str(row[1]), actor=str(row[2]), target_entity_id=str(row[3]),
            interval_seconds=int(row[4]), next_run_epoch_s=int(row[5]), enabled=bool(int(row[6])),
            failure_escalation_kind=str(row[7]), payload=json.loads(str(row[8] or '{}')),
        )

    def _ensure_schema(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS security_drill_schedule (
                    drill_id TEXT PRIMARY KEY,
                    drill_kind TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    target_entity_id TEXT NOT NULL,
                    interval_seconds INTEGER NOT NULL,
                    next_run_epoch_s INTEGER NOT NULL,
                    enabled INTEGER NOT NULL,
                    failure_escalation_kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        return conn

__all__ = ['CANON_SECURITY_DRILL_SCHEDULE_STORE', 'SecurityDrillSchedule', 'SQLiteSecurityDrillScheduleStore']
