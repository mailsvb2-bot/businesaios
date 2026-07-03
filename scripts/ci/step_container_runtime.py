from __future__ import annotations

import json
import os
from pathlib import Path

from runtime.platform.container_runtime_contract import ContainerRuntimeProbe, evaluate_container_runtime
from scripts.ci.paths import repo_root
from scripts.ci.proof_artifacts import proof_artifact_violations

EVIDENCE_NAME = "container_runtime_evidence.json"
ENV_FLAG_NAMES = [
    "CONTAINER_IMAGE_BUILT",
    "CONTAINER_STARTED",
    "CONTAINER_READYZ_OK",
    "CONTAINER_STORAGEZ_OK",
    "CONTAINER_EXECUTIONZ_OK",
    "CONTAINER_READINESS_HEALTHCHECK_OK",
]
CONTAINER_EVIDENCE_REQUIRED_TEXT_FIELDS = (
    "evidence_kind",
    "created_at",
    "proof_id",
    "commit_sha",
    "image",
    "container_name",
)
CONTAINER_EVIDENCE_KINDS = ("real_container_runtime_probe",)
CANON_CONTAINER_RUNTIME_PROOF_EVIDENCE_GUARD = True


def _artifact_path(name: str) -> Path:
    return repo_root() / "artifacts" / "ci" / name


def _write_artifact(payload: dict[str, object]) -> None:
    path = _artifact_path("container_runtime.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _truthy_env(name: str) -> bool:
    return str(os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "required", "enabled"}


def _declared() -> bool:
    return _truthy_env("CONTAINER_RUNTIME_PROOF_REQUIRED") or _truthy_env("CONTAINER_RUNTIME_ENABLED")


def _evidence_required() -> bool:
    return _truthy_env("CONTAINER_RUNTIME_EVIDENCE_REQUIRED")


def _read_evidence() -> dict[str, object] | None:
    path = _artifact_path(EVIDENCE_NAME)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"artifact": "container_runtime_evidence", "status": "invalid", "violations": ["container_runtime_evidence_invalid"]}
    return dict(payload)


def _probe_from_evidence(payload: dict[str, object]) -> ContainerRuntimeProbe:
    return ContainerRuntimeProbe(
        image_built=payload.get("image_built") is True,
        container_started=payload.get("container_started") is True,
        readyz_ok=payload.get("readyz_ok") is True,
        storagez_ok=payload.get("storagez_ok") is True,
        executionz_ok=payload.get("executionz_ok") is True,
        uses_readiness_healthcheck=payload.get("uses_readiness_healthcheck") is True,
    )


def _ready_evidence_violations(payload: dict[str, object]) -> list[str]:
    violations = proof_artifact_violations(
        payload=payload,
        artifact_name="container_runtime_evidence",
        required_text_fields=CONTAINER_EVIDENCE_REQUIRED_TEXT_FIELDS,
        allowed_evidence_kinds=CONTAINER_EVIDENCE_KINDS,
    )
    if payload.get("status") == "ready" and payload.get("base_image_pull_policy") != "never_during_staging_proof":
        violations.append("container_runtime_evidence_vetted_base_image_policy_required")
    return violations


def _blocked_payload(*, violations: list[str], evidence: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "artifact": "container_runtime",
        "status": "blocked",
        "violations": sorted(set(violations)),
        "evidence_source": EVIDENCE_NAME,
        "claims_production_ready": False,
    }
    if evidence is not None:
        payload["evidence"] = evidence
    if "env_flags_do_not_prove_real_container_runtime" in violations:
        payload["ignored_env_flags"] = list(ENV_FLAG_NAMES)
    return payload


def _advisory_payload() -> dict[str, object]:
    return {
        "artifact": "container_runtime",
        "status": "advisory_only",
        "warnings": ["container_runtime_not_declared"],
        "image_built": False,
        "container_started": False,
        "readyz_ok": False,
        "storagez_ok": False,
        "executionz_ok": False,
        "uses_readiness_healthcheck": False,
        "claims_production_ready": False,
    }


def run() -> tuple[bool, str]:
    evidence = _read_evidence()
    if evidence is not None:
        evidence_violations = _ready_evidence_violations(evidence)
        if evidence.get("status") != "ready" or evidence_violations:
            violations = list(evidence.get("violations") or ["container_runtime_evidence_not_ready"])
            violations.extend(evidence_violations)
            payload = _blocked_payload(
                violations=violations,
                evidence=evidence,
            )
            _write_artifact(payload)
            return False, "container runtime blocked: " + ",".join(payload["violations"])
        payload = evaluate_container_runtime(_probe_from_evidence(evidence))
        payload["evidence_source"] = EVIDENCE_NAME
        payload["evidence_kind"] = evidence.get("evidence_kind")
        payload["proof_id"] = evidence.get("proof_id")
        payload["commit_sha"] = evidence.get("commit_sha")
        payload["base_image"] = evidence.get("base_image")
        payload["base_image_pull_policy"] = evidence.get("base_image_pull_policy")
        payload["claims_production_ready"] = False
        _write_artifact(payload)
        if payload["status"] != "ready":
            return False, "container runtime blocked: " + ",".join(payload["violations"])
        return True, "container runtime ready from evidence: artifacts/ci/container_runtime.json"

    if _evidence_required() or _declared():
        payload = _blocked_payload(
            violations=[
                "container_runtime_evidence_required",
                "env_flags_do_not_prove_real_container_runtime",
            ]
        )
        _write_artifact(payload)
        return False, "container runtime blocked: container_runtime_evidence_required"

    payload = _advisory_payload()
    _write_artifact(payload)
    return True, "container runtime artifact written: artifacts/ci/container_runtime.json status=advisory_only"


__all__ = [
    "CANON_CONTAINER_RUNTIME_PROOF_EVIDENCE_GUARD",
    "run",
]
