from __future__ import annotations

from pathlib import Path


def test_staging_postgres_provisioner_is_secret_safe() -> None:
    text = Path("scripts/staging/provision_postgres_staging.sh").read_text(encoding="utf-8")

    assert text.startswith("#!/usr/bin/env bash")
    assert "openssl rand" in text
    assert "BAIOS_STAGING_DB_PASSWORD" in text
    assert "chmod 600" in text
    assert "SELECT 1" in text
    assert "run_staging_runtime_proof.sh" in text
    assert "PASSWORD@" not in text


def test_staging_postgres_provisioner_validates_identifiers() -> None:
    text = Path("scripts/staging/provision_postgres_staging.sh").read_text(encoding="utf-8")

    assert "invalid DB_NAME" in text
    assert "invalid DB_USER" in text
    assert "CREATE ROLE" in text
    assert "CREATE DATABASE" in text
    assert "ALTER DATABASE" in text


def test_staging_secret_files_are_gitignored() -> None:
    text = Path(".gitignore").read_text(encoding="utf-8")

    assert ".env.*.local" in text
    assert "secrets/local/" in text
    assert "*.secret" in text
    assert "*.secrets" in text
