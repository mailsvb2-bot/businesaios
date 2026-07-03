from __future__ import annotations

import json
import os
from pathlib import Path

from scripts.ci.paths import repo_root
from scripts.ci.proof_artifacts import proof_artifact_violations

RUNNER = Path("scripts/staging/run_staging_runtime_proof.sh")
EVIDENCE_NAME = "staging_runtime_proof.json"
CANON_STAGING_RUNTIME_PROOF_AGGREGATION_GUARD = True
STAGING_PROOF_REQUIRED_TEXT_FIELDS = (
    "evidence_kind",
    "created_at",
    "proof_id",
    "commit_sha",
)
STAGING_PROOF_KINDS = ("real_staging_runtime_proof",)
CONTAINER_EVIDENCE_REQUIRED_TEXT_FIELDS = (
    "evidence_kind",
    "created_at",
    "proof_id",
    "commit_sha",
    "image",
    "container_name",
)
REAL_BOOT_EVIDENCE_REQUIRED_TEXT_FIELDS = (
    "evidence_kind",
    "created_at",
    "proof_id",
    "commit_sha",
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _runner_path() -> Path:
    return _project_root() / RUNNER


def _artifact_path(name: str = EVIDENCE_NAME) -> Path:
    return repo_root() / "artifacts" / "ci" / name


def _write_artifact(payload: dict[str, object]) -> None:
    path = _artifact_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _declared() -> bool:
    return str(os.getenv("STAGING_RUNTIME_PROOF_REQUIRED") or "").strip().lower() in {"1", "true", "yes", "required"}


def _read_existing_evidence() -> dict[str, object] | None:
    path = _artifact_path()
    if not path.exists():
        return None
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return {"artifact": "staging_runtime_proof", "status": "invalid", "violations": ["staging_runtime_proof_invalid"]}


def _validate_runner() -> list[str]:
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
        if "GIT_COMMIT_SHA" not in text or "BAIOS_STAGING_PROOF_ID" not in text:
            violations.append("staging_runtime_provenance_required")
        if EVIDENCE_NAME not in text:
            violations.append("staging_runtime_artifact_required")
    return violations


def _nested_ready_artifact_violations(
    *,
    evidence: dict[str, object],
    key: str,
    artifact_name: str,
    required_fields: tuple[str, ...],
    allowed_kinds: tuple[str, ...],
) -> list[str]:
    nested = evidence.get(key)
    if not isinstance(nested, dict):
        return [f"{key}_not_ready"]
    return proof_artifact_violations(
        payload=nested,
        artifact_name=artifact_name,
        required_text_fields=required_fields,
        allowed_evidence_kinds=allowed_kinds,
    )


def _ready_staging_evidence_violations(evidence: dict[str, object]) -> list[str]:
    violations = proof_artifact_violations(
        payload=evidence,
        artifact_name="staging_runtime_proof",
        required_text_fields=STAGING_PROOF_REQUIRED_TEXT_FIELDS,
        allowed_evidence_kinds=STAGING_PROOF_KINDS,
    )
    required_ready = (
        "postgres_contract",
        "postgres_migrations",
        "postgres_live",
        "container_runtime",
        "container_runtime_evidence",
        "real_runtime_boot_evidence",
    )
    for name in required_ready:
        nested = evidence.get(name)
        if not isinstance(nested, dict) or nested.get("status") != "ready":
            violations.append(f"{name}_not_ready")
    violations.extend(
        _nested_ready_artifact_violations(
            evidence=evidence,
            key="container_runtime_evidence",
            artifact_name="container_runtime_evidence",
            required_fields=CONTAINER_EVIDENCE_REQUIRED_TEXT_FIELDS,
            allowed_kinds=("real_container_runtime_probe",),
        )
    )
    violations.extend(
        _nested_ready_artifact_violations(
            evidence=evidence,
            key="real_runtime_boot_evidence",
            artifact_name="real_runtime_boot_evidence",
            required_fields=REAL_BOOT_EVIDENCE_REQUIRED_TEXT_FIELDS,
            allowed_kinds=("real_staging_runtime_boot_probe", "real_production_runtime_boot_probe"),
        )
    )
    production_boot = evidence.get("production_boot")
    if not isinstance(production_boot, dict) or production_boot.get("status") != "contract_satisfied":
        violations.append("production_boot_contract_not_satisfied")
    return sorted(set(violations))


def run() -> tuple[bool, str]:
    violations = _validate_runner()
    if violations:
        payload = {
            "artifact": "staging_runtime_proof",
            "status": "blocked",
            "violations": violations,
            "claims_production_ready": False,
        }
        _write_artifact(payload)
        return False, "staging runtime proof blocked: " + ",".join(violations)

    evidence = _read_existing_evidence()
    if evidence is not None:
        if evidence.get("status") == "ready":
            violations = _ready_staging_evidence_violations(evidence)
            if violations:
                payload = dict(evidence)
                payload["status"] = "blocked"
                payload["violations"] = violations
                payload["claims_production_ready"] = False
                _write_artifact(payload)
                return False, "staging runtime proof blocked: " + ",".join(violations)
            evidence["claims_production_ready"] = False
            _write_artifact(evidence)
            return True, "staging runtime proof ready from artifacts/ci/staging_runtime_proof.json"
        if _declared():
            payload = dict(evidence)
            payload.setdefault("violations", ["staging_runtime_proof_not_ready"])
            payload["status"] = "blocked"
            payload["claims_production_ready"] = False
            _write_artifact(payload)
            return False, "staging runtime proof blocked: staging_runtime_proof_not_ready"

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
            "violations": ["database_url_required", "real_staging_runtime_proof_required"],
            "runner": RUNNER.as_posix(),
            "runner_command": "bash " + RUNNER.as_posix(),
            "claims_production_ready": False,
        }
        _write_artifact(payload)
        return False, (
            "staging runtime proof blocked: database_url_required; "
            "direct server runner execution required: bash scripts/staging/run_staging_runtime_proof.sh"
        )

    payload = {
        "artifact": "staging_runtime_proof",
        "status": "blocked",
        "violations": ["real_staging_runtime_proof_required", "run_staging_runtime_proof_on_server"],
        "runner": RUNNER.as_posix(),
        "runner_command": "bash " + RUNNER.as_posix(),
        "claims_production_ready": False,
    }
    _write_artifact(payload)
    return False, (
        "staging runtime proof blocked: real_staging_runtime_proof_required; "
        "direct server runner execution required: bash scripts/staging/run_staging_runtime_proof.sh"
    )


__all__ = ["CANON_STAGING_RUNTIME_PROOF_AGGREGATION_GUARD", "run"]
