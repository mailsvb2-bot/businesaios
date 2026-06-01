from __future__ import annotations

import json
import os
from pathlib import Path

from scripts.ci.paths import repo_root

RUNNER = Path("scripts/staging/run_staging_runtime_proof.sh")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _runner_path() -> Path:
    return _project_root() / RUNNER


def _write_artifact(payload: dict[str, object]) -> None:
    path = repo_root() / "artifacts" / "ci" / "staging_runtime_proof.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _declared() -> bool:
    return str(os.getenv("STAGING_RUNTIME_PROOF_REQUIRED") or "").strip().lower() in {"1", "true", "yes", "required"}


def run() -> tuple[bool, str]:
    runner = _runner_path()
    violations: list[str] = []
    if not runner.exists():
        violations.append("staging_runtime_runner_missing")
    else:
        text = runner.read_text(encoding="utf-8")
        if not text.startswith("#!/usr/bin/env bash"):
            violations.append("staging_runtime_runner_shebang_required")
        if "DATABASE_URL is required" not in text:
            violations.append("database_url_guard_required")
        if "docker build" not in text or "docker run" not in text:
            violations.append("docker_build_run_required")
        if "probe_url /readyz" not in text or "probe_url /storagez" not in text or "probe_url /executionz" not in text:
            violations.append("readiness_probe_surfaces_required")
        if "staging_runtime_proof.json" not in text:
            violations.append("staging_runtime_artifact_required")
    if violations:
        payload = {
            "artifact": "staging_runtime_proof",
            "status": "blocked",
            "violations": violations,
            "claims_production_ready": False,
        }
        _write_artifact(payload)
        return False, "staging runtime proof blocked: " + ",".join(violations)
    if not _declared():
        payload = {
            "artifact": "staging_runtime_proof",
            "status": "advisory_only",
            "warnings": ["staging_runtime_not_declared"],
            "runner": RUNNER.as_posix(),
            "runner_command": "bash " + RUNNER.as_posix(),
            "claims_production_ready": False,
        }
        _write_artifact(payload)
        return True, "staging runtime proof artifact written: artifacts/ci/staging_runtime_proof.json status=advisory_only"
    if not os.getenv("DATABASE_URL", "").strip():
        payload = {
            "artifact": "staging_runtime_proof",
            "status": "blocked",
            "violations": ["database_url_required"],
            "runner": RUNNER.as_posix(),
            "runner_command": "bash " + RUNNER.as_posix(),
            "claims_production_ready": False,
        }
        _write_artifact(payload)
        return False, "staging runtime proof blocked: database_url_required"
    payload = {
        "artifact": "staging_runtime_proof",
        "status": "blocked",
        "violations": ["run_staging_runtime_proof_on_server"],
        "runner": RUNNER.as_posix(),
        "runner_command": "bash " + RUNNER.as_posix(),
        "claims_production_ready": False,
    }
    _write_artifact(payload)
    return False, "staging runtime proof requires direct server runner execution: bash scripts/staging/run_staging_runtime_proof.sh"


__all__ = ["run"]
