from __future__ import annotations

"""Postgres-backed queue remediation audit store.

This module persists remediation audit evidence only:
- generated remediation plans
- remediation execution reports

It must remain strictly operational and must never mutate queue execution state
or introduce a second decision path.
"""

from dataclasses import dataclass
from datetime import datetime
import json

from runtime.platform.postgres_port import PostgresPort
from runtime.queue.job_contract import normalize_now
from runtime.queue.queue_remediation_audit_sqlite import (
    QueueRemediationExecutionAuditEntry,
    QueueRemediationPlanAuditEntry,
)
from runtime.queue.queue_remediation_hooks import QueueRemediationExecutionReport, QueueRemediationPlan

CANON_RUNTIME_QUEUE_REMEDIATION_AUDIT_POSTGRES = True

@dataclass
class PostgresQueueRemediationAuditStore:
    dsn: str
    application_name: str = 'businesaios-queue-remediation-audit'

    def __post_init__(self) -> None:
        self._port: PostgresPort | None = None

    def __enter__(self) -> 'PostgresQueueRemediationAuditStore':
        self._port = PostgresPort(self.dsn, application_name=self.application_name).__enter__()
        self._init_schema()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self._port is not None
        self._port.__exit__(exc_type, exc, tb)
        self._port = None

    def record_plan(self, plan: QueueRemediationPlan) -> QueueRemediationPlanAuditEntry:
        port = self._require_port()
        entry = QueueRemediationPlanAuditEntry(
            tenant_id=str(plan.tenant_id).strip(),
            queue_name=str(plan.queue_name).strip(),
            generated_at=normalize_now(plan.generated_at),
            hooks=tuple(
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
            ),
        )
        port.execute(
            """
            INSERT INTO runtime_queue_remediation_plan_audit (
                tenant_id,
                queue_name,
                generated_at,
                hooks_json
            ) VALUES (%s, %s, %s, %s);
            """,
            (entry.tenant_id, entry.queue_name, entry.generated_at.isoformat(), json.dumps(entry.hooks, ensure_ascii=False, separators=(',', ':'))),
        )
        port.commit()
        return entry

    def record_execution(self, report: QueueRemediationExecutionReport) -> QueueRemediationExecutionAuditEntry:
        port = self._require_port()
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
        port.execute(
            """
            INSERT INTO runtime_queue_remediation_execution_audit (
                tenant_id,
                queue_name,
                hook_code,
                executed,
                reason,
                executed_at,
                category,
                metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (entry.tenant_id, entry.queue_name, entry.hook_code, entry.executed, entry.reason, entry.executed_at.isoformat(), entry.category, json.dumps(entry.metadata, ensure_ascii=False, separators=(',', ':'))),
        )
        port.commit()
        return entry

    def list_plan_entries(self, *, tenant_id: str, queue_name: str, limit: int = 50) -> tuple[QueueRemediationPlanAuditEntry, ...]:
        rows = self._require_port().fetchall(
            "SELECT tenant_id, queue_name, generated_at, hooks_json FROM runtime_queue_remediation_plan_audit WHERE tenant_id = %s AND queue_name = %s ORDER BY id DESC LIMIT %s;",
            (str(tenant_id).strip(), str(queue_name).strip(), max(0, int(limit))),
        )
        return tuple(
            QueueRemediationPlanAuditEntry(
                tenant_id=str(row[0]), queue_name=str(row[1]), generated_at=normalize_now(datetime.fromisoformat(str(row[2]))), hooks=tuple(dict(item) for item in json.loads(str(row[3]) or '[]'))
            )
            for row in rows
        )

    def list_execution_entries(self, *, tenant_id: str, queue_name: str, limit: int = 50) -> tuple[QueueRemediationExecutionAuditEntry, ...]:
        rows = self._require_port().fetchall(
            "SELECT tenant_id, queue_name, hook_code, executed, reason, executed_at, category, metadata_json FROM runtime_queue_remediation_execution_audit WHERE tenant_id = %s AND queue_name = %s ORDER BY id DESC LIMIT %s;",
            (str(tenant_id).strip(), str(queue_name).strip(), max(0, int(limit))),
        )
        return tuple(
            QueueRemediationExecutionAuditEntry(
                tenant_id=str(row[0]), queue_name=str(row[1]), hook_code=str(row[2]), executed=bool(row[3]), reason=str(row[4]), executed_at=normalize_now(datetime.fromisoformat(str(row[5]))), category=str(row[6]), metadata=dict(json.loads(str(row[7]) or '{}'))
            )
            for row in rows
        )

    def _init_schema(self) -> None:
        port = self._require_port()
        port.execute("CREATE TABLE IF NOT EXISTS runtime_queue_remediation_plan_audit (id BIGSERIAL PRIMARY KEY, tenant_id TEXT NOT NULL, queue_name TEXT NOT NULL, generated_at TEXT NOT NULL, hooks_json TEXT NOT NULL);")
        port.execute("CREATE INDEX IF NOT EXISTS ix_runtime_queue_remediation_plan_audit_lookup ON runtime_queue_remediation_plan_audit (tenant_id, queue_name, generated_at);")
        port.execute("CREATE TABLE IF NOT EXISTS runtime_queue_remediation_execution_audit (id BIGSERIAL PRIMARY KEY, tenant_id TEXT NOT NULL, queue_name TEXT NOT NULL, hook_code TEXT NOT NULL, executed BOOLEAN NOT NULL, reason TEXT NOT NULL, executed_at TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'inspection', metadata_json TEXT NOT NULL DEFAULT '{}');")
        port.execute("CREATE INDEX IF NOT EXISTS ix_runtime_queue_remediation_execution_audit_lookup ON runtime_queue_remediation_execution_audit (tenant_id, queue_name, hook_code, executed_at);")
        port.commit()

    def _require_port(self) -> PostgresPort:
        if self._port is None:
            raise RuntimeError('PostgresQueueRemediationAuditStore is not open')
        return self._port

__all__ = ['CANON_RUNTIME_QUEUE_REMEDIATION_AUDIT_POSTGRES', 'PostgresQueueRemediationAuditStore']
