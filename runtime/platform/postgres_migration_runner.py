from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from runtime.platform.postgres_port import PostgresPort


@dataclass(frozen=True)
class PostgresMigrationResult:
    migration_file: str
    applied: bool


def migration_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "migrations" / "postgres"


def migration_files(base: Path | None = None) -> tuple[Path, ...]:
    root = base or migration_dir()
    if not root.exists():
        return ()
    return tuple(sorted(path for path in root.glob("*.sql") if path.is_file()))


def _ensure_schema_migrations(port: PostgresPort) -> None:
    port.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          migration_id TEXT PRIMARY KEY,
          applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    port.commit()


def _applied_file_migrations(port: PostgresPort) -> set[str]:
    rows = port.fetchall("SELECT migration_id FROM schema_migrations;")
    return {str(row[0]) for row in rows or []}


def apply_postgres_migrations(dsn: str, *, base: Path | None = None) -> tuple[PostgresMigrationResult, ...]:
    files = migration_files(base)
    if not files:
        raise RuntimeError("postgres_migrations_missing")
    results: list[PostgresMigrationResult] = []
    with PostgresPort(dsn, application_name="businesaios-postgres-migrations") as port:
        _ensure_schema_migrations(port)
        applied = _applied_file_migrations(port)
        for path in files:
            file_id = path.stem
            if file_id in applied:
                results.append(PostgresMigrationResult(migration_file=path.name, applied=False))
                continue
            port.execute(path.read_text(encoding="utf-8"))
            port.execute(
                "INSERT INTO schema_migrations (migration_id) VALUES (%s) ON CONFLICT (migration_id) DO NOTHING;",
                (file_id,),
            )
            port.commit()
            applied.add(file_id)
            results.append(PostgresMigrationResult(migration_file=path.name, applied=True))
    return tuple(results)


__all__ = ["PostgresMigrationResult", "apply_postgres_migrations", "migration_dir", "migration_files"]
