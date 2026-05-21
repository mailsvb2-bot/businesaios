from __future__ import annotations

import json
from pathlib import Path

from runtime.platform.postgres_migration_runner import migration_files
from scripts.ci.cli import build_parser
from scripts.ci.plan_registry import plan_for_gate
from scripts.ci.step_postgres_migrations import run as run_postgres_migrations
from scripts.ci.step_registry import handler_for_step


def test_postgres_migrations_gate_is_registered_and_release_ordered() -> None:
    assert callable(handler_for_step("postgres-migrations"))
    assert build_parser().parse_args(["--gate", "postgres-migrations"]).gate == "postgres-migrations"
    assert [step.name for step in plan_for_gate("postgres-migrations").steps] == [
        "assert-project-shape",
        "doctor-check",
        "postgres-migrations",
    ]
    release_steps = [step.name for step in plan_for_gate("release").steps]
    assert release_steps.index("postgres-contract") < release_steps.index("postgres-migrations") < release_steps.index("postgres-live")


def test_postgres_migrations_advisory_without_runtime(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.delenv("POSTGRES_RUNTIME_ENABLED", raising=False)
    artifact = Path("artifacts/ci/postgres_migrations.json")
    if artifact.exists():
        artifact.unlink()

    ok, message = run_postgres_migrations()
    payload = json.loads(artifact.read_text(encoding="utf-8"))

    assert ok is True, message
    assert payload["artifact"] == "postgres_migrations"
    assert payload["status"] == "advisory_only"
    assert payload["migration_files"] == [path.name for path in migration_files()]
    assert payload["claims_production_ready"] is False


def test_postgres_migrations_fail_closed_when_declared_without_dsn(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.setenv("POSTGRES_RUNTIME_ENABLED", "1")

    ok, message = run_postgres_migrations()
    payload = json.loads(Path("artifacts/ci/postgres_migrations.json").read_text(encoding="utf-8"))

    assert ok is False
    assert "database_url_required" in message
    assert payload["status"] == "blocked"
    assert payload["claims_production_ready"] is False
