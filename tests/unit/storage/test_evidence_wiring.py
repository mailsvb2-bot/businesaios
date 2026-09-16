from __future__ import annotations

import pytest

from application.business_autonomy.persistence import business_autonomy_evidence_store_path
from storage import evidence_wiring
from storage.evidence_store import SqliteEvidenceStore
from storage.evidence_wiring import build_canonical_evidence_store, canonical_evidence_store_path


def test_canonical_evidence_wiring_preserves_legacy_business_autonomy_path(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    expected = tmp_path / "runtime" / "business_autonomy_evidence.sqlite3"
    assert canonical_evidence_store_path() == expected
    assert business_autonomy_evidence_store_path() == expected
    store = build_canonical_evidence_store()
    assert isinstance(store, SqliteEvidenceStore)
    assert expected.exists()


def test_canonical_evidence_wiring_allows_isolated_composition_root(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "production"))
    isolated = tmp_path / "isolated"
    assert canonical_evidence_store_path(root_dir=isolated) == isolated / "runtime" / "business_autonomy_evidence.sqlite3"
    assert canonical_evidence_store_path() == tmp_path / "production" / "runtime" / "business_autonomy_evidence.sqlite3"



def test_canonical_evidence_wiring_fails_closed_on_production_sqlite(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    with pytest.raises(RuntimeError, match="PROD_REQUIRES_POSTGRES_STORAGE_BACKEND"):
        build_canonical_evidence_store()


def test_canonical_evidence_wiring_selects_postgres_without_sqlite_fallback(monkeypatch) -> None:
    captured = {}

    class _FakePostgresStore:
        def __init__(self, session_factory):
            captured["factory"] = session_factory

    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://user:pass@example.invalid:5432/baios")
    monkeypatch.setattr(evidence_wiring, "PostgresEvidenceStore", _FakePostgresStore)
    store = build_canonical_evidence_store()
    assert isinstance(store, _FakePostgresStore)
    assert captured["factory"].dsn.endswith("/baios")
    assert captured["factory"].application_name == "businesaios-evidence-store"
