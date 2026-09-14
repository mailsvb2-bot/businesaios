from __future__ import annotations

from pathlib import Path

from runtime.wiring import resolve_storage_config
from storage.audit_store import PostgresAuditStore, SqliteAuditStore
from storage.evidence_wiring import canonical_evidence_store_path
from storage.postgres_session import PostgresSessionFactory
from storage.sqlite_fallback import SqliteSessionFactory

CANON_AUDIT_WIRING = True


def build_canonical_audit_store(*, root_dir: str | Path | None = None):
    storage = resolve_storage_config()
    env = str(storage.env or "").strip().lower()
    backend = str(storage.backend or "").strip().lower()
    if env in {"prod", "production"} and backend != "postgres":
        raise RuntimeError(f"PROD_REQUIRES_POSTGRES_STORAGE_BACKEND:{backend}")
    if backend == "postgres":
        dsn = str(storage.postgres_dsn or "").strip()
        if not dsn:
            raise RuntimeError("POSTGRES_BACKEND_REQUIRES_DSN")
        return PostgresAuditStore(
            PostgresSessionFactory(dsn=dsn, application_name="businesaios-audit-store")
        )
    if backend != "sqlite":
        raise RuntimeError(f"UNSUPPORTED_STORAGE_BACKEND:{backend}")
    return SqliteAuditStore(SqliteSessionFactory(canonical_evidence_store_path(root_dir=root_dir)))


__all__ = ["CANON_AUDIT_WIRING", "build_canonical_audit_store"]
