from __future__ import annotations

import json
import os

from runtime.platform.container_runtime_contract import ContainerRuntimeProbe, evaluate_container_runtime
from scripts.ci.paths import repo_root


def _write_artifact(payload: dict[str, object]) -> None:
    path = repo_root() / "artifacts" / "ci" / "container_runtime.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _truthy(name: str) -> bool:
    return str(os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "ok", "ready", "passed"}


def _declared() -> bool:
    return str(os.getenv("CONTAINER_RUNTIME_PROOF_REQUIRED") or os.getenv("CONTAINER_RUNTIME_ENABLED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "required",
        "enabled",
    }


def run() -> tuple[bool, str]:
    if not _declared():
        payload = {
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
        _write_artifact(payload)
        return True, "container runtime artifact written: artifacts/ci/container_runtime.json status=advisory_only"
    payload = evaluate_container_runtime(
        ContainerRuntimeProbe(
            image_built=_truthy("CONTAINER_IMAGE_BUILT"),
            container_started=_truthy("CONTAINER_STARTED"),
            readyz_ok=_truthy("CONTAINER_READYZ_OK"),
            storagez_ok=_truthy("CONTAINER_STORAGEZ_OK"),
            executionz_ok=_truthy("CONTAINER_EXECUTIONZ_OK"),
            uses_readiness_healthcheck=_truthy("CONTAINER_READINESS_HEALTHCHECK_OK"),
        )
    )
    _write_artifact(payload)
    if payload["status"] != "ready":
        return False, "container runtime blocked: " + ",".join(payload["violations"])
    return True, "container runtime ready: artifacts/ci/container_runtime.json"


__all__ = ["run"]
