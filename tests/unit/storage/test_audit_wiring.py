from __future__ import annotations

import pytest

from storage import audit_wiring
from storage.audit_store import SqliteAuditStore
from storage.audit_wiring import build_canonical_audit_store
from storage.evidence_wiring import canonical_evidence_store_path


def test_canonical_audit_wiring_shares_canonical_sqlite_database(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    store = build_canonical_audit_store()
    assert isinstance(store, SqliteAuditStore)
    assert canonical_evidence_store_path() == tmp_path / "runtime" / "business_autonomy_evidence.sqlite3"
    assert canonical_evidence_store_path().exists()


def test_canonical_audit_wiring_fails_closed_on_production_sqlite(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="PROD_REQUIRES_POSTGRES_STORAGE_BACKEND"):
        build_canonical_audit_store()


def test_canonical_audit_wiring_selects_postgres(monkeypatch) -> None:
    captured = {}

    class _FakePostgresStore:
        def __init__(self, session_factory):
            captured["factory"] = session_factory

    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://user:pass@example.invalid:5432/baios")
    monkeypatch.setattr(audit_wiring, "PostgresAuditStore", _FakePostgresStore)
    store = build_canonical_audit_store()
    assert isinstance(store, _FakePostgresStore)
    assert captured["factory"].dsn.endswith("/baios")
    assert captured["factory"].application_name == "businesaios-audit-store"
