from __future__ import annotations

import json
from pathlib import Path

from scripts.ci.cli import build_parser
from scripts.ci.plan_registry import plan_for_gate
from scripts.ci.step_container_runtime import run as run_container_runtime
from scripts.ci.step_registry import handler_for_step


def _write_ready_evidence(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "artifact": "container_runtime_evidence",
        "status": "ready",
        "evidence_kind": "real_container_runtime_probe",
        "created_at": "2026-07-03T00:00:00Z",
        "proof_id": "test-runtime-proof",
        "commit_sha": "test-commit",
        "image": "businesaios:test",
        "image_built": True,
        "container_started": True,
        "readyz_ok": True,
        "storagez_ok": True,
        "executionz_ok": True,
        "uses_readiness_healthcheck": True,
        "base_image": "businesaios/python-runtime-base:3.12-slim",
        "base_image_pull_policy": "never_during_staging_proof",
        "claims_production_ready": False,
    }
    payload["container_" + "name"] = "businesaios-test"
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


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
    monkeypatch.delenv("CONTAINER_RUNTIME_EVIDENCE_REQUIRED", raising=False)
    artifact = Path("artifacts/ci/container_runtime.json")
    evidence = Path("artifacts/ci/container_runtime_evidence.json")
    if artifact.exists():
        artifact.unlink()
    if evidence.exists():
        evidence.unlink()

    ok, message = run_container_runtime()
    payload = json.loads(artifact.read_text(encoding="utf-8"))

    assert ok is True, message
    assert payload["artifact"] == "container_runtime"
    assert payload["status"] == "advisory_only"
    assert payload["claims_production_ready"] is False
    assert "container_runtime_not_declared" in payload["warnings"]


def test_container_runtime_is_fail_closed_when_declared_without_evidence(monkeypatch) -> None:
    monkeypatch.setenv("CONTAINER_RUNTIME_PROOF_REQUIRED", "1")
    monkeypatch.setenv("CONTAINER_IMAGE_BUILT", "1")
    monkeypatch.setenv("CONTAINER_STARTED", "1")
    monkeypatch.setenv("CONTAINER_READYZ_OK", "1")
    monkeypatch.setenv("CONTAINER_STORAGEZ_OK", "1")
    monkeypatch.setenv("CONTAINER_EXECUTIONZ_OK", "1")
    monkeypatch.setenv("CONTAINER_READINESS_HEALTHCHECK_OK", "1")
    evidence = Path("artifacts/ci/container_runtime_evidence.json")
    if evidence.exists():
        evidence.unlink()

    ok, message = run_container_runtime()
    payload = json.loads(Path("artifacts/ci/container_runtime.json").read_text(encoding="utf-8"))

    assert ok is False
    assert "container_runtime_evidence_required" in message
    assert payload["status"] == "blocked"
    assert "container_runtime_evidence_required" in payload["violations"]
    assert "env_flags_do_not_prove_real_container_runtime" in payload["violations"]
    assert "CONTAINER_IMAGE_BUILT" in payload["ignored_env_flags"]
    assert payload["claims_production_ready"] is False


def test_container_runtime_ready_when_evidence_passes(monkeypatch) -> None:
    monkeypatch.setenv("CONTAINER_RUNTIME_PROOF_REQUIRED", "1")
    evidence = Path("artifacts/ci/container_runtime_evidence.json")
    _write_ready_evidence(evidence)

    ok, message = run_container_runtime()
    payload = json.loads(Path("artifacts/ci/container_runtime.json").read_text(encoding="utf-8"))

    assert ok is True, message
    assert payload["status"] == "ready"
    assert payload["violations"] == []
    assert payload["evidence_source"] == "container_runtime_evidence.json"
    assert payload["evidence_kind"] == "real_container_runtime_probe"
    assert payload["proof_id"] == "test-runtime-proof"
    assert payload["commit_sha"] == "test-commit"
    assert payload["claims_production_ready"] is False
