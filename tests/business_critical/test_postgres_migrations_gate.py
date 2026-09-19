from __future__ import annotations

import json
from pathlib import Path

import scripts.ci.step_postgres_migrations as step_postgres_migrations
from runtime.platform.postgres_migration_runner import migration_files
from scripts.ci.cli import build_parser
from scripts.ci.plan_registry import plan_for_gate
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


def _isolate_artifacts(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(step_postgres_migrations, "repo_root", lambda: tmp_path)
    return tmp_path / "artifacts" / "ci" / "postgres_migrations.json"


def test_postgres_migrations_advisory_without_runtime(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.delenv("POSTGRES_RUNTIME_ENABLED", raising=False)
    artifact = _isolate_artifacts(monkeypatch, tmp_path)

    ok, message = step_postgres_migrations.run()
    payload = json.loads(artifact.read_text(encoding="utf-8"))

    assert ok is True, message
    assert payload["artifact"] == "postgres_migrations"
    assert payload["status"] == "advisory_only"
    assert payload["migration_files"] == [path.name for path in migration_files()]
    assert payload["claims_production_ready"] is False


def test_postgres_migrations_fail_closed_when_declared_without_dsn(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.setenv("POSTGRES_RUNTIME_ENABLED", "1")
    artifact = _isolate_artifacts(monkeypatch, tmp_path)

    ok, message = step_postgres_migrations.run()
    payload = json.loads(artifact.read_text(encoding="utf-8"))

    assert ok is False
    assert "database_url_required" in message
    assert payload["status"] == "blocked"
    assert payload["claims_production_ready"] is False


def test_runtime_store_schema_is_owned_by_tracked_migration() -> None:
    migration = Path("migrations/postgres/0003_runtime_store_schema_v2.sql").read_text(encoding="utf-8")
    event_store = Path("runtime/platform/event_store/postgres_event_store.py").read_text(encoding="utf-8")
    payment_outbox = Path("runtime/platform/outbox/postgres_payment_outbox.py").read_text(encoding="utf-8")
    runtime_adapters = [
        event_store,
        payment_outbox,
        Path("runtime/platform/outbox/postgres_outbox.py").read_text(encoding="utf-8"),
        Path("runtime/platform/ledger/postgres_ledger.py").read_text(encoding="utf-8"),
        Path("observability/platform/snapshot_store/postgres_snapshot_store.py").read_text(encoding="utf-8"),
        Path("observability/platform/decision_archive/postgres_decision_archive.py").read_text(encoding="utf-8"),
    ]

    assert "event_store_v2" in migration
    assert "payment_outbox_v2" in migration
    assert "durable_runtime_v2" in migration
    assert "ADD COLUMN IF NOT EXISTS append_seq" in migration
    assert "run_after_ms BIGINT NOT NULL" in migration
    assert all("CREATE TABLE" not in text and "ALTER TABLE" not in text for text in runtime_adapters)
