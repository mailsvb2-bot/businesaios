"""Durable remediation audit trail for queue operations.

This module records operator-facing queue remediation planning and execution.
It is evidence only:
- what remediation hooks were offered
- what hook was explicitly executed
- whether it ran or stayed operator-review only

It must never mutate queue execution state or become a second decision path.
"""

from __future__ import annotations

import importlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import RLock
from runtime.platform.outbox.sqlite_pragmas import configure_sqlite, is_prod_env
from runtime.queue.job_contract import normalize_now
from runtime.queue.queue_remediation_hooks import QueueRemediationExecutionReport, QueueRemediationPlan

sqlite3 = importlib.import_module("sqlite3")
CANON_RUNTIME_QUEUE_REMEDIATION_AUDIT_SQLITE = True

def runtime_queue_remediation_audit_store_path() -> Path:
    explicit = os.getenv('BUSINESAIOS_QUEUE_REMEDIATION_AUDIT_SQLITE_PATH', '').strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv('DATA_DIR', 'data').strip() or 'data'
    return Path(data_dir) / 'runtime' / 'queue_remediation_audit.sqlite3'


@dataclass(frozen=True)
class QueueRemediationPlanAuditEntry:
    tenant_id: str
    queue_name: str
    generated_at: datetime
    hooks: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class QueueRemediationExecutionAuditEntry:
    tenant_id: str
    queue_name: str
    hook_code: str
    executed: bool
    reason: str
    executed_at: datetime
    category: str
    metadata: dict[str, object]


class SqliteQueueRemediationAuditStore:
    def __init__(self, path: str | Path | None = None, *, busy_timeout_ms: int = 5000) -> None:
        self._path = Path(path) if path is not None else runtime_queue_remediation_audit_store_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._busy_timeout_ms = max(100, int(busy_timeout_ms))
        self._lock = RLock()
        self._closed = False
        self._init_schema()

    @property
    def path(self) -> Path:
        return self._path

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def record_plan(self, plan: QueueRemediationPlan) -> QueueRemediationPlanAuditEntry:
        self._ensure_open()
        hooks = tuple(
            {
                'code': hook.code,
                'label': hook.label,
                'description': hook.description,
                'severity': hook.severity,
                'operator_required': hook.operator_required,
                'category': hook.category,
                'runbook_hint': hook.runbook_hint,
                'metadata': dict(hook.metadata),
            }
            for hook in plan.hooks
        )
        entry = QueueRemediationPlanAuditEntry(
            tenant_id=str(plan.tenant_id).strip(),
            queue_name=str(plan.queue_name).strip(),
            generated_at=normalize_now(plan.generated_at),
            hooks=hooks,
        )
        with self._lock, self._connect() as db:
            db.execute('BEGIN IMMEDIATE;')
            db.execute(
                '''
                INSERT INTO runtime_queue_remediation_plan_audit (
                    tenant_id,
                    queue_name,
                    generated_at,
                    hooks_json
                ) VALUES (?, ?, ?, ?)
                ''',
                (
                    entry.tenant_id,
                    entry.queue_name,
                    entry.generated_at.isoformat(),
                    json.dumps(entry.hooks, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            db.commit()
        return entry

    def record_execution(self, report: QueueRemediationExecutionReport) -> QueueRemediationExecutionAuditEntry:
        self._ensure_open()
        entry = QueueRemediationExecutionAuditEntry(
            tenant_id=str(report.tenant_id).strip(),
            queue_name=str(report.queue_name).strip(),
            hook_code=str(report.hook_code).strip(),
            executed=bool(report.executed),
            reason=str(report.reason).strip(),
            executed_at=normalize_now(report.executed_at),
            category=str(report.category).strip() or 'inspection',
            metadata=dict(report.metadata),
        )
        with self._lock, self._connect() as db:
            db.execute('BEGIN IMMEDIATE;')
            db.execute(
                '''
                INSERT INTO runtime_queue_remediation_execution_audit (
                    tenant_id,
                    queue_name,
                    hook_code,
                    executed,
                    reason,
                    executed_at,
                    category,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    entry.tenant_id,
                    entry.queue_name,
                    entry.hook_code,
                    1 if entry.executed else 0,
                    entry.reason,
                    entry.executed_at.isoformat(),
                    entry.category,
                    json.dumps(entry.metadata, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            db.commit()
        return entry

    def list_plan_entries(self, *, tenant_id: str, queue_name: str, limit: int = 50) -> tuple[QueueRemediationPlanAuditEntry, ...]:
        self._ensure_open()
        with self._lock, self._connect() as db:
            rows = db.execute(
                '''
                SELECT tenant_id, queue_name, generated_at, hooks_json
                FROM runtime_queue_remediation_plan_audit
                WHERE tenant_id = ? AND queue_name = ?
                ORDER BY id DESC
                LIMIT ?
                ''',
                (str(tenant_id).strip(), str(queue_name).strip(), max(0, int(limit))),
            ).fetchall()
        return tuple(
            QueueRemediationPlanAuditEntry(
                tenant_id=str(row['tenant_id']),
                queue_name=str(row['queue_name']),
                generated_at=normalize_now(datetime.fromisoformat(str(row['generated_at']))),
                hooks=tuple(dict(item) for item in json.loads(str(row['hooks_json']) or '[]')),
            )
            for row in rows
        )

    def list_execution_entries(self, *, tenant_id: str, queue_name: str, limit: int = 50) -> tuple[QueueRemediationExecutionAuditEntry, ...]:
        self._ensure_open()
        with self._lock, self._connect() as db:
            rows = db.execute(
                '''
                SELECT tenant_id, queue_name, hook_code, executed, reason, executed_at, category, metadata_json
                FROM runtime_queue_remediation_execution_audit
                WHERE tenant_id = ? AND queue_name = ?
                ORDER BY id DESC
                LIMIT ?
                ''',
                (str(tenant_id).strip(), str(queue_name).strip(), max(0, int(limit))),
            ).fetchall()
        return tuple(
            QueueRemediationExecutionAuditEntry(
                tenant_id=str(row['tenant_id']),
                queue_name=str(row['queue_name']),
                hook_code=str(row['hook_code']),
                executed=bool(row['executed']),
                reason=str(row['reason']),
                executed_at=normalize_now(datetime.fromisoformat(str(row['executed_at']))),
                category=str(row['category']),
                metadata=dict(json.loads(str(row['metadata_json']) or '{}')),
            )
            for row in rows
        )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self._path, timeout=max(0.1, self._busy_timeout_ms / 1000.0), check_same_thread=False)
        db.row_factory = sqlite3.Row
        configure_sqlite(db, prod=is_prod_env())
        db.execute(f'PRAGMA busy_timeout={self._busy_timeout_ms};')
        return db

    def _init_schema(self) -> None:
        with self._lock, self._connect() as db:
            db.executescript(
                '''
                CREATE TABLE IF NOT EXISTS runtime_queue_remediation_plan_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    queue_name TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    hooks_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_runtime_queue_remediation_plan_audit_lookup
                    ON runtime_queue_remediation_plan_audit (tenant_id, queue_name, generated_at);

                CREATE TABLE IF NOT EXISTS runtime_queue_remediation_execution_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    queue_name TEXT NOT NULL,
                    hook_code TEXT NOT NULL,
                    executed INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    executed_at TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'inspection',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS ix_runtime_queue_remediation_execution_audit_lookup
                    ON runtime_queue_remediation_execution_audit (tenant_id, queue_name, hook_code, executed_at);
                '''
            )
            columns = {str(row['name']) for row in db.execute("PRAGMA table_info(runtime_queue_remediation_execution_audit)").fetchall()}
            if 'category' not in columns:
                db.execute("ALTER TABLE runtime_queue_remediation_execution_audit ADD COLUMN category TEXT NOT NULL DEFAULT 'inspection'")
            if 'metadata_json' not in columns:
                db.execute("ALTER TABLE runtime_queue_remediation_execution_audit ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")
            db.commit()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError('SqliteQueueRemediationAuditStore is closed')


__all__ = [
    'CANON_RUNTIME_QUEUE_REMEDIATION_AUDIT_SQLITE',
    'QueueRemediationExecutionAuditEntry',
    'QueueRemediationPlanAuditEntry',
    'SqliteQueueRemediationAuditStore',
    'runtime_queue_remediation_audit_store_path',
]
