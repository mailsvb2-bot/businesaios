from __future__ import annotations

from compatibility.safety_storage_exports import resolve_safety_storage_export

CANON_SAFETY_SQLITE_MIGRATIONS = True


def __getattr__(name: str):
    return resolve_safety_storage_export("migrations", name)


__all__ = [
    "CANON_PLATFORM_SAFETY_SQLITE_MIGRATIONS",  # noqa: F822 - provided lazily by module __getattr__
    "CANON_SAFETY_SQLITE_MIGRATIONS",
    "MigrationStep",  # noqa: F822 - provided lazily by module __getattr__
    "SafetySqliteMigrator",  # noqa: F822 - provided lazily by module __getattr__
    "SchemaMigrationPlan",  # noqa: F822 - provided lazily by module __getattr__
]
