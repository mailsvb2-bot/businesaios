from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.production_boot_contract import ProductionBootProbe, assert_production_boot_ready, evaluate_production_boot
from scripts.ci.step_production_boot import run as run_production_boot


def test_ci_profile_is_advisory_only_not_production_ready(monkeypatch) -> None:
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_RUNTIME_ENABLED", raising=False)
    probe = ProductionBootProbe.from_env({"ENV": "ci", "APP_PROFILE": "api"})

    report = evaluate_production_boot(probe)

    assert report["status"] == "advisory_only"
    assert report["production_profile"] is False
    assert report["production_boot_contract_satisfied"] is False
    assert report["claims_production_ready"] is False
    assert "non_production_profile_advisory_only" in report["warnings"]


def test_production_without_postgres_is_blocked() -> None:
    probe = ProductionBootProbe.from_env({"ENV": "production", "APP_PROFILE": "api"})

    report = evaluate_production_boot(probe)

    assert report["status"] == "blocked"
    assert report["production_profile"] is True
    assert report["production_boot_contract_satisfied"] is False
    assert report["claims_production_ready"] is False
    assert "production_database_url_required" in report["violations"]
    assert "production_postgres_enablement_required" in report["violations"]


def test_production_with_required_contract_is_satisfied_but_not_production_ready_claim() -> None:
    probe = ProductionBootProbe.from_env(
        {
            "ENV": "production",
            "APP_PROFILE": "api",
            "DATABASE_URL": "postgresql://example.invalid/db",
            "POSTGRES_RUNTIME_ENABLED": "1",
            "RUN_MIGRATIONS_BEFORE_START": "1",
            "BAIOS_REQUIRE_QUALITY_TOOLS": "release",
        }
    )

    report = evaluate_production_boot(probe)

    assert report["status"] == "contract_satisfied"
    assert report["production_boot_contract_satisfied"] is True
    assert report["claims_production_ready"] is False
    assert report["requires_live_postgres_probe"] is True
    assert report["requires_container_runtime_probe"] is True
    assert report["violations"] == []


def test_assert_production_boot_ready_blocks_unready_production() -> None:
    probe = ProductionBootProbe.from_env({"ENV": "production", "APP_PROFILE": "api"})

    with pytest.raises(RuntimeError, match="PRODUCTION_BOOT_NOT_READY"):
        assert_production_boot_ready(probe)


def test_production_boot_step_writes_non_prod_advisory_contract_artifact(monkeypatch) -> None:
    monkeypatch.setenv("ENV", "ci")
    monkeypatch.setenv("APP_PROFILE", "api")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_RUNTIME_ENABLED", raising=False)
    monkeypatch.delenv("REAL_RUNTIME_BOOT_EVIDENCE_REQUIRED", raising=False)
    artifact = Path("artifacts/ci/production_boot.json")
    if artifact.exists():
        artifact.unlink()

    ok, message = run_production_boot()
    payload = json.loads(artifact.read_text(encoding="utf-8"))

    assert ok is True, message
    assert payload["artifact"] == "production_boot_contract"
    assert payload["proof_kind"] == "contract_aggregation_not_process_boot"
    assert payload["claims_real_runtime_boot"] is False
    assert payload["status"] == "advisory_only"
    assert payload["production_profile"] is False
    assert payload["production_boot_contract_satisfied"] is False
    assert payload["claims_production_ready"] is False