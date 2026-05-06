import importlib

import pytest


def _build_system():
    m = importlib.import_module("main")
    return m.build_system()


def test_prod_requires_postgres_backend(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("RUN_MODE", "telegram")
    monkeypatch.setenv("TENANT_ID", "default")
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.delenv("POSTGRES_DSN", raising=False)

    with pytest.raises(RuntimeError) as e:
        _build_system()
    assert "PROD_REQUIRES_POSTGRES_STORAGE_BACKEND" in str(e.value)


def test_prod_requires_postgres_dsn(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("RUN_MODE", "telegram")
    monkeypatch.setenv("TENANT_ID", "default")
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    monkeypatch.delenv("POSTGRES_DSN", raising=False)

    with pytest.raises(RuntimeError) as e:
        _build_system()
    assert "PROD_REQUIRES_POSTGRES_DSN" in str(e.value)
