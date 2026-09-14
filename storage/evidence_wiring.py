from __future__ import annotations

import os
from pathlib import Path

from runtime.wiring import resolve_storage_config
from storage.evidence_store import EvidenceStore, PostgresEvidenceStore, SqliteEvidenceStore
from storage.postgres_session import PostgresSessionFactory
from storage.sqlite_fallback import SqliteSessionFactory

CANON_EVIDENCE_WIRING = True
_LEGACY_CANONICAL_EVIDENCE_RELATIVE_PATH = Path("runtime") / "business_autonomy_evidence.sqlite3"


def canonical_evidence_store_path(*, root_dir: str | Path | None = None) -> Path:
    """Return the one durable Evidence Store path.

    The default deliberately preserves the historical Business Autonomy path so
    existing evidence is not stranded by Phase 3. ``root_dir`` is reserved for
    isolated composition roots such as tests and explicit embedded runtimes.
    """

    if root_dir is not None:
        root = Path(root_dir)
    else:
        root = Path(str(os.getenv("DATA_DIR", "data")).strip() or "data")
    return root / _LEGACY_CANONICAL_EVIDENCE_RELATIVE_PATH


def build_canonical_evidence_store(*, root_dir: str | Path | None = None) -> EvidenceStore:
    storage = resolve_storage_config()
    env = str(storage.env or "").strip().lower()
    backend = str(storage.backend or "").strip().lower()
    if env in {"prod", "production"} and backend != "postgres":
        raise RuntimeError(f"PROD_REQUIRES_POSTGRES_STORAGE_BACKEND:{backend}")
    if backend == "postgres":
        dsn = str(storage.postgres_dsn or "").strip()
        if not dsn:
            raise RuntimeError("POSTGRES_BACKEND_REQUIRES_DSN")
        return PostgresEvidenceStore(
            PostgresSessionFactory(dsn=dsn, application_name="businesaios-evidence-store")
        )
    if backend != "sqlite":
        raise RuntimeError(f"UNSUPPORTED_STORAGE_BACKEND:{backend}")
    return SqliteEvidenceStore(SqliteSessionFactory(canonical_evidence_store_path(root_dir=root_dir)))


__all__ = ["CANON_EVIDENCE_WIRING", "build_canonical_evidence_store", "canonical_evidence_store_path"]
