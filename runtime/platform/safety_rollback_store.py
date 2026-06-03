from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from sqlite3 import Connection
from collections.abc import Iterator

from core.safety.controls.rollback_engine.models import (
    RollbackAction,
    RollbackExecutionState,
    RollbackPlan,
    RollbackReceipt,
    RollbackReconciliationState,
)
from runtime.platform.safety_sqlite_migrations import SafetySqliteMigrator, SchemaMigrationPlan

CANON_PLATFORM_SAFETY_ROLLBACK_STORE = True
SCHEMA_VERSION = 5


class PlatformSqliteRollbackPlanStore:
    def __init__(self, *, sqlite_path: str) -> None:
        self._path = str(sqlite_path).strip()
        if not self._path:
            raise ValueError('sqlite_path is required')
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[Connection]:
        conn = sqlite3.connect(self._path)
        conn.execute('PRAGMA journal_mode = WAL')
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        plan = SchemaMigrationPlan(
            component='rollback_plans',
            target_version=SCHEMA_VERSION,
            steps=(self._migrate_v1, self._migrate_v2, self._migrate_v3, self._migrate_v4, self._migrate_v5),
        )
        with self._connect() as conn:
            SafetySqliteMigrator().apply(conn, plan)

    @staticmethod
    def _migrate_v1(conn: Connection) -> None:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS safety_rollback_plans (
                tenant_id TEXT NOT NULL,
                action_id TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                PRIMARY KEY (tenant_id, action_id)
            )
        ''')

    @staticmethod
    def _migrate_v2(conn: Connection) -> None:
        cols = {str(row[1]) for row in conn.execute('PRAGMA table_info(safety_rollback_plans)').fetchall()}
        if 'execution_state' not in cols:
            conn.execute("ALTER TABLE safety_rollback_plans ADD COLUMN execution_state TEXT NOT NULL DEFAULT 'planned'")
        if 'confirmation_token' not in cols:
            conn.execute("ALTER TABLE safety_rollback_plans ADD COLUMN confirmation_token TEXT NOT NULL DEFAULT ''")

    @staticmethod
    def _migrate_v3(conn: Connection) -> None:
        cols = {str(row[1]) for row in conn.execute('PRAGMA table_info(safety_rollback_plans)').fetchall()}
        if 'receipts_json' not in cols:
            conn.execute("ALTER TABLE safety_rollback_plans ADD COLUMN receipts_json TEXT NOT NULL DEFAULT '[]'")
        if 'reconciliation_state' not in cols:
            conn.execute("ALTER TABLE safety_rollback_plans ADD COLUMN reconciliation_state TEXT NOT NULL DEFAULT 'pending'")
        if 'reconciliation_error' not in cols:
            conn.execute("ALTER TABLE safety_rollback_plans ADD COLUMN reconciliation_error TEXT NOT NULL DEFAULT ''")

    @staticmethod
    def _migrate_v4(conn: Connection) -> None:
        cols = {str(row[1]) for row in conn.execute('PRAGMA table_info(safety_rollback_plans)').fetchall()}
        if 'version' not in cols:
            conn.execute("ALTER TABLE safety_rollback_plans ADD COLUMN version INTEGER NOT NULL DEFAULT 0")
        if 'lease_owner' not in cols:
            conn.execute("ALTER TABLE safety_rollback_plans ADD COLUMN lease_owner TEXT NOT NULL DEFAULT ''")

    @staticmethod
    def _migrate_v5(conn: Connection) -> None:
        cols = {str(row[1]) for row in conn.execute('PRAGMA table_info(safety_rollback_plans)').fetchall()}
        if 'fencing_token' not in cols:
            conn.execute("ALTER TABLE safety_rollback_plans ADD COLUMN fencing_token INTEGER NOT NULL DEFAULT 0")

    def put(self, *, tenant_id: str, action_id: str, plan: RollbackPlan) -> RollbackPlan:
        tenant_key = str(tenant_id).strip() or 'unknown'
        action_key = str(action_id).strip()
        if not action_key:
            raise ValueError('action_id is required')
        next_version = max(1, int(plan.version or 0))
        with self._connect() as conn:
            conn.execute(
                '''
                INSERT INTO safety_rollback_plans(tenant_id, action_id, plan_json, execution_state, confirmation_token, receipts_json, reconciliation_state, reconciliation_error, version, lease_owner, fencing_token)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, action_id) DO UPDATE SET plan_json = excluded.plan_json, execution_state = excluded.execution_state, confirmation_token = excluded.confirmation_token, receipts_json = excluded.receipts_json, reconciliation_state = excluded.reconciliation_state, reconciliation_error = excluded.reconciliation_error, version = excluded.version, lease_owner = excluded.lease_owner, fencing_token = excluded.fencing_token
                ''',
                (
                    tenant_key,
                    action_key,
                    json.dumps(_serialize_plan(plan), sort_keys=True),
                    str(plan.execution_state.value if hasattr(plan.execution_state, 'value') else plan.execution_state),
                    str(plan.confirmation_token or ''),
                    json.dumps([asdict(item) for item in plan.receipts], sort_keys=True),
                    str(plan.reconciliation_state.value if hasattr(plan.reconciliation_state, 'value') else plan.reconciliation_state),
                    str(plan.reconciliation_error or ''),
                    next_version,
                    str(plan.lease_owner or ''),
                    int(plan.fencing_token or 0),
                ),
            )
        return RollbackPlan(**{**plan.__dict__, 'version': next_version})

    def get(self, *, tenant_id: str, action_id: str) -> RollbackPlan | None:
        tenant_key = str(tenant_id).strip() or 'unknown'
        action_key = str(action_id).strip()
        if not action_key:
            raise ValueError('action_id is required')
        with self._connect() as conn:
            row = conn.execute(
                'SELECT plan_json, execution_state, confirmation_token, receipts_json, reconciliation_state, reconciliation_error, version, lease_owner, fencing_token FROM safety_rollback_plans WHERE tenant_id = ? AND action_id = ?',
                (tenant_key, action_key),
            ).fetchone()
        if row is None:
            return None
        return _deserialize_plan(
            json.loads(str(row[0]) or '{}'),
            execution_state=str(row[1] or 'planned'),
            confirmation_token=str(row[2] or ''),
            receipts=json.loads(str(row[3]) or '[]'),
            reconciliation_state=str(row[4] or 'pending'),
            reconciliation_error=str(row[5] or ''),
            version=int(row[6] or 0),
            lease_owner=str(row[7] or ''),
            fencing_token=int(row[8] or 0),
        )

    def compare_and_set(self, *, tenant_id: str, action_id: str, expected_version: int, plan: RollbackPlan) -> RollbackPlan:
        tenant_key = str(tenant_id).strip() or 'unknown'
        action_key = str(action_id).strip()
        next_version = int(expected_version) + 1
        current = self.get(tenant_id=tenant_id, action_id=action_id)
        if current and current.lease_owner and plan.lease_owner and current.lease_owner != plan.lease_owner and int(plan.fencing_token or 0) < int(current.fencing_token or 0):
            raise RuntimeError('rollback_plan_stale_fencing_token')
        next_fencing_token = max(int(plan.fencing_token or 0), int((current.fencing_token if current else 0) or 0))
        with self._connect() as conn:
            updated = conn.execute(
                '''
                UPDATE safety_rollback_plans SET plan_json = ?, execution_state = ?, confirmation_token = ?, receipts_json = ?, reconciliation_state = ?, reconciliation_error = ?, version = ?, lease_owner = ?, fencing_token = ? WHERE tenant_id = ? AND action_id = ? AND version = ?
                ''',
                (
                    json.dumps(_serialize_plan(plan), sort_keys=True),
                    str(plan.execution_state.value if hasattr(plan.execution_state, 'value') else plan.execution_state),
                    str(plan.confirmation_token or ''),
                    json.dumps([asdict(item) for item in plan.receipts], sort_keys=True),
                    str(plan.reconciliation_state.value if hasattr(plan.reconciliation_state, 'value') else plan.reconciliation_state),
                    str(plan.reconciliation_error or ''),
                    next_version,
                    str(plan.lease_owner or ''),
                    next_fencing_token,
                    tenant_key,
                    action_key,
                    int(expected_version),
                ),
            ).rowcount
            if updated == 0:
                raise RuntimeError('rollback_plan_version_conflict')
        return RollbackPlan(**{**plan.__dict__, 'version': next_version, 'fencing_token': next_fencing_token})

    def acquire_lease(self, *, tenant_id: str, action_id: str, owner: str) -> RollbackPlan | None:
        current = self.get(tenant_id=tenant_id, action_id=action_id)
        if current is None:
            return None
        return self.compare_and_set(
            tenant_id=tenant_id,
            action_id=action_id,
            expected_version=int(current.version),
            plan=RollbackPlan(**{**current.__dict__, 'lease_owner': str(owner), 'fencing_token': int(current.fencing_token) + 1}),
        )

    def update_state(self, *, tenant_id: str, action_id: str, state: RollbackExecutionState) -> RollbackPlan | None:
        plan = self.get(tenant_id=tenant_id, action_id=action_id)
        if plan is None:
            return None
        return self.compare_and_set(
            tenant_id=tenant_id,
            action_id=action_id,
            expected_version=int(plan.version),
            plan=RollbackPlan(**{**plan.__dict__, 'execution_state': state}),
        )

    def append_receipt(self, *, tenant_id: str, action_id: str, receipt: RollbackReceipt) -> RollbackPlan | None:
        plan = self.get(tenant_id=tenant_id, action_id=action_id)
        if plan is None:
            return None
        return self.compare_and_set(
            tenant_id=tenant_id,
            action_id=action_id,
            expected_version=int(plan.version),
            plan=RollbackPlan(**{**plan.__dict__, 'receipts': tuple([*plan.receipts, receipt])}),
        )

    def update_reconciliation(self, *, tenant_id: str, action_id: str, state: RollbackReconciliationState, error: str = '') -> RollbackPlan | None:
        plan = self.get(tenant_id=tenant_id, action_id=action_id)
        if plan is None:
            return None
        return self.compare_and_set(
            tenant_id=tenant_id,
            action_id=action_id,
            expected_version=int(plan.version),
            plan=RollbackPlan(**{**plan.__dict__, 'reconciliation_state': state, 'reconciliation_error': str(error or '')}),
        )


def _serialize_plan(plan: RollbackPlan) -> dict[str, object]:
    return {
        'source_action': str(plan.source_action),
        'steps': [{'action': str(item.action), 'payload': dict(item.payload)} for item in plan.steps],
        'version': int(plan.version or 0),
        'lease_owner': str(plan.lease_owner or ''),
        'fencing_token': int(plan.fencing_token or 0),
    }


def _deserialize_plan(
    data: dict[str, object],
    *,
    execution_state: str,
    confirmation_token: str,
    receipts: list[dict[str, object]],
    reconciliation_state: str,
    reconciliation_error: str,
    version: int = 0,
    lease_owner: str = '',
    fencing_token: int = 0,
) -> RollbackPlan:
    return RollbackPlan(
        source_action=str(data.get('source_action') or ''),
        steps=tuple(RollbackAction(action=str(item.get('action') or ''), payload=dict(item.get('payload') or {})) for item in list(data.get('steps') or [])),
        execution_state=RollbackExecutionState(str(execution_state or 'planned')),
        confirmation_token=str(confirmation_token or ''),
        receipts=tuple(
            RollbackReceipt(
                step_index=int(item.get('step_index') or 0),
                action=str(item.get('action') or ''),
                status=str(item.get('status') or ''),
                details=dict(item.get('details') or {}),
            )
            for item in list(receipts or [])
        ),
        reconciliation_state=RollbackReconciliationState(str(reconciliation_state or 'pending')),
        reconciliation_error=str(reconciliation_error or ''),
        version=int(version or data.get('version') or 0),
        lease_owner=str(lease_owner or data.get('lease_owner') or ''),
        fencing_token=int(fencing_token or data.get('fencing_token') or 0),
    )


__all__ = ['CANON_PLATFORM_SAFETY_ROLLBACK_STORE', 'PlatformSqliteRollbackPlanStore', 'SCHEMA_VERSION']
