from __future__ import annotations

import json
from pathlib import Path

import scripts.ci.step_staging_runtime as step_staging_runtime
from scripts.ci.cli import build_parser
from scripts.ci.plan_registry import plan_for_gate
from scripts.ci.step_registry import handler_for_step


def test_staging_runtime_gate_is_registered() -> None:
    assert callable(handler_for_step("staging-runtime"))
    assert build_parser().parse_args(["--gate", "staging-runtime"]).gate == "staging-runtime"
    assert [step.name for step in plan_for_gate("staging-runtime").steps] == [
        "assert-project-shape",
        "doctor-check",
        "staging-runtime",
    ]


def test_staging_runner_contains_required_real_proof_steps() -> None:
    text = Path("scripts/staging/run_staging_runtime_proof.sh").read_text(encoding="utf-8")

    assert text.startswith("#!/usr/bin/env bash")
    assert "DATABASE_URL is required" in text
    assert "run_gate postgres-migrations" in text
    assert "run_gate postgres-contract" in text
    assert "run_gate postgres-live" in text
    assert text.index("run_gate postgres-migrations") < text.index("run_gate postgres-contract") < text.index("run_gate postgres-live")
    assert "docker build" in text
    assert "docker run" in text
    assert "probe_url /readyz" in text
    assert "probe_url /storagez" in text
    assert "probe_url /executionz" in text
    assert "run_gate container-runtime" in text
    assert "run_gate production-boot" in text
    assert "staging_runtime_proof.json" in text
    assert "claims_production_ready" in text


def _isolate_artifacts(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(step_staging_runtime, "repo_root", lambda: tmp_path)
    return tmp_path / "artifacts" / "ci" / "staging_runtime_proof.json"


def test_staging_runtime_gate_is_advisory_when_not_declared(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("STAGING_RUNTIME_PROOF_REQUIRED", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    artifact = _isolate_artifacts(monkeypatch, tmp_path)

    ok, message = step_staging_runtime.run()
    payload = json.loads(artifact.read_text(encoding="utf-8"))

    assert ok is True, message
    assert payload["artifact"] == "staging_runtime_proof"
    assert payload["status"] == "advisory_only"
    assert payload["runner_command"] == "bash scripts/staging/run_staging_runtime_proof.sh"
    assert "staging_runtime_not_declared" in payload["warnings"]
    assert payload["claims_production_ready"] is False


def test_staging_runtime_gate_blocks_when_declared_without_database_url(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STAGING_RUNTIME_PROOF_REQUIRED", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    artifact = _isolate_artifacts(monkeypatch, tmp_path)

    ok, message = step_staging_runtime.run()
    payload = json.loads(artifact.read_text(encoding="utf-8"))

    assert ok is False
    assert "database_url_required" in message
    assert payload["status"] == "blocked"
    assert "database_url_required" in payload["violations"]
    assert payload["claims_production_ready"] is False


def test_staging_runtime_gate_refuses_to_fake_server_run(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STAGING_RUNTIME_PROOF_REQUIRED", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/db")
    artifact = _isolate_artifacts(monkeypatch, tmp_path)

    ok, message = step_staging_runtime.run()
    payload = json.loads(artifact.read_text(encoding="utf-8"))

    assert ok is False
    assert "direct server runner execution" in message
    assert "run_staging_runtime_proof_on_server" in payload["violations"]
    assert payload["claims_production_ready"] is False
