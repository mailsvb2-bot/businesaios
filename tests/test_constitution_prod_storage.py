from __future__ import annotations

import importlib

import pytest


def test_prod_requires_postgres_storage(monkeypatch):
    # Ring Spec: prod requires Postgres durable storage; SQLite is dev-only.
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("DECISION_SIGNING_SECRET", "prod-secret-nondefault")
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.delenv("POSTGRES_DSN", raising=False)

    main = importlib.import_module("main")
    with pytest.raises(RuntimeError) as e:
        _ = main.build_system()
    assert "PROD_REQUIRES_POSTGRES_STORAGE_BACKEND" in str(e.value)
