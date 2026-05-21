from __future__ import annotations

import json
from pathlib import Path

from scripts.ci.step_production_boot import run as run_production_boot


def test_production_boot_blocks_when_postgres_contract_is_not_ready(monkeypatch) -> None:
    artifact = Path("artifacts/ci/postgres_contract.json")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        json.dumps(
            {
                "artifact": "postgres_contract",
                "status": "blocked",
                "violations": ["postgres_live_probe_required"],
                "claims_production_ready": False,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("APP_PROFILE", "api")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/db")
    monkeypatch.setenv("POSTGRES_RUNTIME_ENABLED", "1")
    monkeypatch.setenv("RUN_MIGRATIONS_BEFORE_START", "1")
    monkeypatch.setenv("BAIOS_REQUIRE_QUALITY_TOOLS", "release")

    ok, message = run_production_boot()
    payload = json.loads(Path("artifacts/ci/production_boot.json").read_text(encoding="utf-8"))

    assert ok is False
    assert "postgres_contract_not_ready" in message
    assert payload["status"] == "blocked"
    assert payload["production_profile"] is True
    assert payload["postgres_contract"]["status"] == "blocked"
    assert "postgres_contract_not_ready" in payload["violations"]
    assert payload["claims_production_ready"] is False


def test_production_boot_keeps_non_production_advisory_with_advisory_postgres_contract(monkeypatch) -> None:
    artifact = Path("artifacts/ci/postgres_contract.json")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        json.dumps(
            {
                "artifact": "postgres_contract",
                "status": "advisory_only",
                "warnings": ["postgres_runtime_not_declared"],
                "claims_production_ready": False,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ENV", "ci")
    monkeypatch.setenv("APP_PROFILE", "api")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_RUNTIME_ENABLED", raising=False)

    ok, message = run_production_boot()
    payload = json.loads(Path("artifacts/ci/production_boot.json").read_text(encoding="utf-8"))

    assert ok is True, message
    assert payload["status"] == "advisory_only"
    assert payload["production_profile"] is False
    assert payload["postgres_contract"]["status"] == "advisory_only"
    assert payload["claims_production_ready"] is False
