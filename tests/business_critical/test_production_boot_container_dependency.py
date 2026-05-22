from __future__ import annotations

import json
from pathlib import Path

from scripts.ci.step_production_boot import run as run_production_boot


def _write_artifact(name: str, payload: dict[str, object]) -> None:
    path = Path("artifacts/ci") / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_production_boot_blocks_when_container_runtime_is_not_ready(monkeypatch) -> None:
    _write_artifact("postgres_contract.json", {"artifact": "postgres_contract", "status": "ready", "violations": [], "claims_production_ready": False})
    _write_artifact("postgres_migrations.json", {"artifact": "postgres_migrations", "status": "ready", "violations": [], "claims_production_ready": False})
    _write_artifact("postgres_live.json", {"artifact": "postgres_live", "status": "ready", "violations": [], "claims_production_ready": False})
    _write_artifact("container_runtime.json", {"artifact": "container_runtime", "status": "advisory_only", "warnings": ["container_runtime_not_declared"], "claims_production_ready": False})
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("APP_PROFILE", "api")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/db")
    monkeypatch.setenv("POSTGRES_RUNTIME_ENABLED", "1")
    monkeypatch.setenv("RUN_MIGRATIONS_BEFORE_START", "1")
    monkeypatch.setenv("BAIOS_REQUIRE_QUALITY_TOOLS", "release")

    ok, message = run_production_boot()
    payload = json.loads(Path("artifacts/ci/production_boot.json").read_text(encoding="utf-8"))

    assert ok is False
    assert "container_runtime_not_ready" in message
    assert payload["status"] == "blocked"
    assert payload["container_runtime"]["status"] == "advisory_only"
    assert "container_runtime_not_ready" in payload["violations"]
    assert payload["claims_production_ready"] is False


def test_production_boot_allows_non_production_with_advisory_container_runtime(monkeypatch) -> None:
    _write_artifact("postgres_contract.json", {"artifact": "postgres_contract", "status": "advisory_only", "warnings": ["postgres_runtime_not_declared"], "claims_production_ready": False})
    _write_artifact("postgres_migrations.json", {"artifact": "postgres_migrations", "status": "advisory_only", "warnings": ["postgres_runtime_not_declared"], "claims_production_ready": False})
    _write_artifact("postgres_live.json", {"artifact": "postgres_live", "status": "advisory_only", "warnings": ["postgres_runtime_not_declared"], "claims_production_ready": False})
    _write_artifact("container_runtime.json", {"artifact": "container_runtime", "status": "advisory_only", "warnings": ["container_runtime_not_declared"], "claims_production_ready": False})
    monkeypatch.setenv("ENV", "ci")
    monkeypatch.setenv("APP_PROFILE", "api")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_RUNTIME_ENABLED", raising=False)

    ok, message = run_production_boot()
    payload = json.loads(Path("artifacts/ci/production_boot.json").read_text(encoding="utf-8"))

    assert ok is True, message
    assert payload["status"] == "advisory_only"
    assert payload["production_profile"] is False
    assert payload["container_runtime"]["status"] == "advisory_only"
    assert payload["claims_production_ready"] is False
