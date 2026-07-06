from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

CANON_PLATFORM_SAFETY_SQLITE_MIGRATIONS = True

MigrationStep = Callable[[sqlite3.Connection], None]


@dataclass(frozen=True)
class SchemaMigrationPlan:
    component: str
    target_version: int
    steps: tuple[MigrationStep, ...]


class SafetySqliteMigrator:
    def apply(self, conn: sqlite3.Connection, plan: SchemaMigrationPlan) -> int:
        conn.execute(
            'CREATE TABLE IF NOT EXISTS safety_schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL)'
        )
        row = conn.execute('SELECT version FROM safety_schema_version WHERE component = ?', (plan.component,)).fetchone()
        current = int(row[0]) if row is not None else 0
        if current > int(plan.target_version):
            raise RuntimeError(f'unsupported {plan.component} schema version downgrade: {current} > {plan.target_version}')
        if current == 0:
            conn.execute(
                'INSERT OR IGNORE INTO safety_schema_version(component, version) VALUES (?, ?)',
                (plan.component, 0),
            )
        for version in range(current + 1, int(plan.target_version) + 1):
            step = plan.steps[version - 1]
            step(conn)
            conn.execute('UPDATE safety_schema_version SET version = ? WHERE component = ?', (version, plan.component))
        return int(plan.target_version)


__all__ = ['CANON_PLATFORM_SAFETY_SQLITE_MIGRATIONS', 'MigrationStep', 'SafetySqliteMigrator', 'SchemaMigrationPlan']
