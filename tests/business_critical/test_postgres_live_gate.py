from __future__ import annotations

import json
from pathlib import Path

from scripts.ci.cli import build_parser
from scripts.ci.plan_registry import plan_for_gate
from scripts.ci.step_postgres_live import run as run_postgres_live
from scripts.ci.step_registry import handler_for_step


def test_postgres_live_gate_is_registered_and_release_ordered() -> None:
    assert callable(handler_for_step("postgres-live"))
    assert build_parser().parse_args(["--gate", "postgres-live"]).gate == "postgres-live"
    assert [step.name for step in plan_for_gate("postgres-live").steps] == [
        "assert-project-shape",
        "doctor-check",
        "postgres-live",
    ]
    release_steps = [step.name for step in plan_for_gate("release").steps]
    prerelease_steps = [step.name for step in plan_for_gate("pre-release").steps]
    assert release_steps.index("postgres-contract") < release_steps.index("postgres-migrations") < release_steps.index("postgres-live") < release_steps.index("production-boot")
    assert prerelease_steps.index("postgres-contract") < prerelease_steps.index("postgres-migrations") < prerelease_steps.index("postgres-live") < prerelease_steps.index("production-boot")


def test_postgres_live_is_advisory_when_runtime_not_declared(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.delenv("POSTGRES_RUNTIME_ENABLED", raising=False)
    artifact = Path("artifacts/ci/postgres_live.json")
    if artifact.exists():
        artifact.unlink()

    ok, message = run_postgres_live()
    payload = json.loads(artifact.read_text(encoding="utf-8"))

    assert ok is True, message
    assert payload["artifact"] == "postgres_live"
    assert payload["status"] == "advisory_only"
    assert payload["live_runtime_probe"] is False
    assert payload["claims_production_ready"] is False


def test_production_boot_gate_requires_migrations_and_live_before_boot() -> None:
    assert [step.name for step in plan_for_gate("production-boot").steps] == [
        "assert-project-shape",
        "doctor-check",
        "postgres-contract",
        "postgres-migrations",
        "postgres-live",
        "production-boot",
    ]
