from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROD_ENV = ROOT / ".env.example.prod"


def test_production_env_uses_canonical_storage_name() -> None:
    text = PROD_ENV.read_text(encoding="utf-8")
    assert "STORAGE" + "_BACKEND=postgres" in text
    assert "METRO" + "_DB_ENGINE" not in text
    assert "STORAGE" + "_DB_ENGINE" not in text


def test_production_env_requires_release_proof_flags() -> None:
    text = PROD_ENV.read_text(encoding="utf-8")
    required_names = (
        "POSTGRES_RUNTIME_ENABLED=1",
        "POSTGRES_EVENT_STORE_ENABLED=1",
        "RUN_MIGRATIONS_BEFORE_START=1",
        "POSTGRES_APPLY_MIGRATIONS=1",
        "POSTGRES_LIVE_PROOF_REQUIRED=1",
        "POSTGRES_BACKUP_EVIDENCE_OK=0",
        "POSTGRES_BACKUP_EVIDENCE_PATH=",
        "CONTAINER_RUNTIME_PROOF_REQUIRED=1",
        "CONTAINER_RUNTIME_EVIDENCE_REQUIRED=1",
        "REAL_RUNTIME_BOOT_EVIDENCE_REQUIRED=1",
        "PRODUCTION_BOOT_PROOF_REQUIRED=1",
        "BAIOS_REQUIRE_TRANSITIVE_DEPENDENCY_LOCK=1",
    )
    for name in required_names:
        assert name in text
