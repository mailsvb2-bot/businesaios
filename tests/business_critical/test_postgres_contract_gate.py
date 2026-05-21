from __future__ import annotations

import json
from pathlib import Path

from runtime.platform.postgres_contract import (
    REQUIRED_MIGRATIONS,
    REQUIRED_SCHEMA_OBJECTS,
    PostgresRuntimeProof,
    evaluate_postgres_contract,
)
from scripts.ci.cli import build_parser
from scripts.ci.plan_registry import plan_for_gate
from scripts.ci.step_postgres_contract import run as run_postgres_contract
from scripts.ci.step_registry import handler_for_step


def test_postgres_contract_advisory_when_runtime_not_declared(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.delenv("POSTGRES_RUNTIME_ENABLED", raising=False)
    artifact = Path("artifacts/ci/postgres_contract.json")
    if artifact.exists():
        artifact.unlink()

    ok, message = run_postgres_contract()
    payload = json.loads(artifact.read_text(encoding="utf-8"))

    assert ok is True, message
    assert payload["artifact"] == "postgres_contract"
    assert payload["status"] == "advisory_only"
    assert payload["claims_production_ready"] is False
    assert "postgres_runtime_not_declared" in payload["warnings"]


def test_postgres_contract_blocks_declared_runtime_without_live_proof() -> None:
    report = evaluate_postgres_contract(
        PostgresRuntimeProof(
            database_url_present=True,
            postgres_enabled=True,
            psycopg_available=True,
            live_probe_ok=False,
            schema_objects_present=(),
            migrations_applied=(),
            event_store_roundtrip_ok=False,
            outbox_roundtrip_ok=False,
            recovery_contract_ok=False,
        )
    )

    assert report["status"] == "blocked"
    assert "postgres_live_probe_required" in report["violations"]
    assert any(str(item).startswith("postgres_schema_objects_missing") for item in report["violations"])
    assert "postgres_event_store_roundtrip_required" in report["violations"]
    assert "postgres_outbox_roundtrip_required" in report["violations"]
    assert "postgres_recovery_contract_required" in report["violations"]
    assert report["claims_production_ready"] is False


def test_postgres_contract_ready_requires_schema_migrations_event_outbox_and_recovery() -> None:
    report = evaluate_postgres_contract(
        PostgresRuntimeProof(
            database_url_present=True,
            postgres_enabled=True,
            psycopg_available=True,
            live_probe_ok=True,
            schema_objects_present=REQUIRED_SCHEMA_OBJECTS,
            migrations_applied=REQUIRED_MIGRATIONS,
            event_store_roundtrip_ok=True,
            outbox_roundtrip_ok=True,
            recovery_contract_ok=True,
        )
    )

    assert report["status"] == "ready"
    assert report["violations"] == []
    assert report["claims_production_ready"] is False


def test_postgres_migration_file_declares_required_schema_and_migrations() -> None:
    text = Path("migrations/postgres/0001_runtime_core.sql").read_text(encoding="utf-8")

    for table in REQUIRED_SCHEMA_OBJECTS:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text
    for migration in REQUIRED_MIGRATIONS:
        assert f"'{migration}'" in text
    assert "schema_migrations" in text
    assert "ON CONFLICT" in text


def test_postgres_contract_gate_is_registered_and_release_ordered() -> None:
    assert callable(handler_for_step("postgres-contract"))
    assert build_parser().parse_args(["--gate", "postgres-contract"]).gate == "postgres-contract"
    assert [step.name for step in plan_for_gate("postgres-contract").steps] == [
        "assert-project-shape",
        "doctor-check",
        "postgres-contract",
    ]
    release_steps = [step.name for step in plan_for_gate("release").steps]
    prerelease_steps = [step.name for step in plan_for_gate("pre-release").steps]
    assert release_steps.index("postgres-contract") < release_steps.index("postgres-live") < release_steps.index("production-boot")
    assert prerelease_steps.index("postgres-contract") < prerelease_steps.index("postgres-live") < prerelease_steps.index("production-boot")
