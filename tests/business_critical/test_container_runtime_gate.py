from __future__ import annotations

import json
from pathlib import Path

from scripts.ci.cli import build_parser
from scripts.ci.plan_registry import plan_for_gate
from scripts.ci.step_container_runtime import run as run_container_runtime
from scripts.ci.step_registry import handler_for_step


def test_container_runtime_gate_is_registered_and_release_ordered() -> None:
    assert callable(handler_for_step("container-runtime"))
    assert build_parser().parse_args(["--gate", "container-runtime"]).gate == "container-runtime"
    assert [step.name for step in plan_for_gate("container-runtime").steps] == [
        "assert-project-shape",
        "doctor-check",
        "container-runtime",
    ]
    release_steps = [step.name for step in plan_for_gate("release").steps]
    prerelease_steps = [step.name for step in plan_for_gate("pre-release").steps]
    assert release_steps.index("postgres-live") < release_steps.index("container-runtime") < release_steps.index("production-boot")
    assert prerelease_steps.index("postgres-live") < prerelease_steps.index("container-runtime") < prerelease_steps.index("production-boot")


def test_container_runtime_is_advisory_when_not_declared(monkeypatch) -> None:
    monkeypatch.delenv("CONTAINER_RUNTIME_PROOF_REQUIRED", raising=False)
    monkeypatch.delenv("CONTAINER_RUNTIME_ENABLED", raising=False)
    artifact = Path("artifacts/ci/container_runtime.json")
    if artifact.exists():
        artifact.unlink()

    ok, message = run_container_runtime()
    payload = json.loads(artifact.read_text(encoding="utf-8"))

    assert ok is True, message
    assert payload["artifact"] == "container_runtime"
    assert payload["status"] == "advisory_only"
    assert payload["claims_production_ready"] is False
    assert "container_runtime_not_declared" in payload["warnings"]


def test_container_runtime_is_fail_closed_when_declared_incomplete(monkeypatch) -> None:
    monkeypatch.setenv("CONTAINER_RUNTIME_PROOF_REQUIRED", "1")
    monkeypatch.setenv("CONTAINER_IMAGE_BUILT", "1")
    monkeypatch.setenv("CONTAINER_STARTED", "1")
    monkeypatch.setenv("CONTAINER_READYZ_OK", "1")
    monkeypatch.delenv("CONTAINER_STORAGEZ_OK", raising=False)
    monkeypatch.delenv("CONTAINER_EXECUTIONZ_OK", raising=False)
    monkeypatch.delenv("CONTAINER_READINESS_HEALTHCHECK_OK", raising=False)

    ok, message = run_container_runtime()
    payload = json.loads(Path("artifacts/ci/container_runtime.json").read_text(encoding="utf-8"))

    assert ok is False
    assert "storagez_required" in message
    assert payload["status"] == "blocked"
    assert "executionz_required" in payload["violations"]
    assert "readiness_healthcheck_required" in payload["violations"]
    assert payload["claims_production_ready"] is False


def test_container_runtime_ready_when_all_declared_checks_pass(monkeypatch) -> None:
    monkeypatch.setenv("CONTAINER_RUNTIME_PROOF_REQUIRED", "1")
    monkeypatch.setenv("CONTAINER_IMAGE_BUILT", "1")
    monkeypatch.setenv("CONTAINER_STARTED", "1")
    monkeypatch.setenv("CONTAINER_READYZ_OK", "1")
    monkeypatch.setenv("CONTAINER_STORAGEZ_OK", "1")
    monkeypatch.setenv("CONTAINER_EXECUTIONZ_OK", "1")
    monkeypatch.setenv("CONTAINER_READINESS_HEALTHCHECK_OK", "1")

    ok, message = run_container_runtime()
    payload = json.loads(Path("artifacts/ci/container_runtime.json").read_text(encoding="utf-8"))

    assert ok is True, message
    assert payload["status"] == "ready"
    assert payload["violations"] == []
    assert payload["claims_production_ready"] is False
