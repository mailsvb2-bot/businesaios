"""Single compatibility catalog for historical core safety-storage exports.

Concrete SQLite persistence belongs to ``runtime.platform``.  Historical
``core.safety.controls.*`` import paths delegate here so they remain stable
without making core depend on the runtime composition layer or defining shadow
adapter classes.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

CANON_SAFETY_STORAGE_COMPAT_EXPORT_CATALOG = True

_SURFACES: dict[str, tuple[str, dict[str, str]]] = {
    "runaway_loop": (
        "runtime.platform.safety_runaway_loop_store",
        {
            "CANON_PLATFORM_SAFETY_RUNAWAY_LOOP_STORE": "CANON_PLATFORM_SAFETY_RUNAWAY_LOOP_STORE",
            "SCHEMA_VERSION": "SCHEMA_VERSION",
            "SqliteRunawayLoopStore": "PlatformSqliteRunawayLoopStore",
        },
    ),
    "budget_ledger": (
        "runtime.platform.safety_action_budget_ledger",
        {
            "CANON_PLATFORM_SAFETY_ACTION_BUDGET_LEDGER": "CANON_PLATFORM_SAFETY_ACTION_BUDGET_LEDGER",
            "SCHEMA_VERSION": "SCHEMA_VERSION",
            "SqliteActionBudgetLedger": "PlatformSqliteActionBudgetLedger",
        },
    ),
    "approval": (
        "runtime.platform.safety_approval_repository",
        {
            "CANON_PLATFORM_SAFETY_APPROVAL_REPOSITORY": "CANON_PLATFORM_SAFETY_APPROVAL_REPOSITORY",
            "SCHEMA_VERSION": "SCHEMA_VERSION",
            "SqliteApprovalRepository": "PlatformSqliteApprovalRepository",
        },
    ),
    "circuit_breaker": (
        "runtime.platform.safety_circuit_breaker_store",
        {
            "CANON_PLATFORM_SAFETY_CIRCUIT_BREAKER_STORE": "CANON_PLATFORM_SAFETY_CIRCUIT_BREAKER_STORE",
            "SCHEMA_VERSION": "SCHEMA_VERSION",
            "SqliteCircuitBreakerStore": "PlatformSqliteCircuitBreakerStore",
        },
    ),
    "rollback": (
        "runtime.platform.safety_rollback_store",
        {
            "CANON_PLATFORM_SAFETY_ROLLBACK_STORE": "CANON_PLATFORM_SAFETY_ROLLBACK_STORE",
            "SCHEMA_VERSION": "SCHEMA_VERSION",
            "SqliteRollbackPlanStore": "PlatformSqliteRollbackPlanStore",
        },
    ),
    "migrations": (
        "runtime.platform.safety_sqlite_migrations",
        {
            "CANON_PLATFORM_SAFETY_SQLITE_MIGRATIONS": "CANON_PLATFORM_SAFETY_SQLITE_MIGRATIONS",
            "MigrationStep": "MigrationStep",
            "SafetySqliteMigrator": "SafetySqliteMigrator",
            "SchemaMigrationPlan": "SchemaMigrationPlan",
        },
    ),
}


def resolve_safety_storage_export(surface: str, name: str) -> Any:
    try:
        module_name, exports = _SURFACES[str(surface)]
        target_name = exports[str(name)]
    except KeyError as exc:
        raise AttributeError(name) from exc
    return getattr(import_module(module_name), target_name)


__all__ = [
    "CANON_SAFETY_STORAGE_COMPAT_EXPORT_CATALOG",
    "resolve_safety_storage_export",
]
