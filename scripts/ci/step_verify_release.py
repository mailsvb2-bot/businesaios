from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path

from scripts.ci.makefile_tools import has_make_target
from scripts.ci.paths import repo_root
from scripts.ci.subprocess_io import run_command, run_python

CANON_VERIFY_RELEASE_ARTIFACT_AGGREGATION = True

_REQUIRED_PROOF_ARTIFACTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("postgres_contract.json", ("ready",)),
    ("postgres_migrations.json", ("ready",)),
    ("postgres_live.json", ("ready",)),
    ("container_runtime.json", ("ready",)),
    ("staging_runtime_proof.json", ("ready",)),
    ("production_boot.json", ("contract_satisfied",)),
)


def _artifact_path(name: str) -> Path:
    return repo_root() / "artifacts" / "ci" / name


def _invalid_artifact(name: str, reason: str) -> dict[str, object]:
    return {
        "artifact": name.removesuffix(".json"),
        "status": "invalid",
        "violations": [name.removesuffix(".json") + reason],
    }


def _read_artifact(name: str) -> dict[str, object]:
    path = _artifact_path(name)
    if not path.exists():
        return {
            "artifact": name.removesuffix(".json"),
            "status": "missing",
            "violations": [name.removesuffix(".json") + "_artifact_missing"],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _invalid_artifact(name, "_artifact_invalid")
    if not isinstance(payload, Mapping):
        return _invalid_artifact(name, "_artifact_not_object")
    return dict(payload)


def _write_verify_artifact(payload: dict[str, object]) -> None:
    path = _artifact_path("verify_release.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")


def _aggregate_required_proof_artifacts() -> tuple[bool, str]:
    artifacts: dict[str, dict[str, object]] = {}
    violations: list[str] = []
    for filename, accepted_statuses in _REQUIRED_PROOF_ARTIFACTS:
        artifact_name = filename.removesuffix(".json")
        payload = _read_artifact(filename)
        artifacts[artifact_name] = payload
        status = str(payload.get("status") or "")
        if status not in accepted_statuses:
            violations.append(artifact_name + "_not_ready")
        if payload.get("claims_production_ready") is True:
            violations.append(artifact_name + "_must_not_claim_production_ready")

    payload = {
        "artifact": "verify_release",
        "status": "blocked" if violations else "ready",
        "required_artifacts": [name for name, _ in _REQUIRED_PROOF_ARTIFACTS],
        "artifacts": artifacts,
        "violations": violations,
        "claims_production_ready": False,
    }
    _write_verify_artifact(payload)
    if violations:
        return False, "verify release blocked: " + ",".join(violations)
    return True, "verify release proof artifacts ready: artifacts/ci/verify_release.json"


def _canonical_python_env() -> dict[str, str]:
    return {"PYTHON_BIN": sys.executable}


def _run_optional_make_target(name: str) -> tuple[bool, str]:
    if not has_make_target(name):
        return True, f"make target absent; skipped by contract: {name}"

    outcome = run_command(["make", name], env=_canonical_python_env())
    if outcome.returncode != 0:
        return False, f"make target failed: {name}"
    return True, f"make target passed: {name}"


def _run_optional_project_release_script() -> tuple[bool, str]:
    root = repo_root()

    verify_release = root / "scripts" / "verify_release.sh"
    if verify_release.exists():
        outcome = run_command(
            ["bash", str(verify_release)],
            env=_canonical_python_env(),
        )
        if outcome.returncode != 0:
            return False, "verify_release.sh failed"
        return True, "verify_release.sh passed"

    package_release = root / "scripts" / "package_release.py"
    if package_release.exists():
        outcome = run_python(["scripts/package_release.py"])
        if outcome.returncode != 0:
            return False, "package_release.py failed"
        return True, "package_release.py passed"

    if has_make_target("regen-manifest"):
        outcome = run_command(
            ["make", "regen-manifest"],
            env=_canonical_python_env(),
        )
        if outcome.returncode != 0:
            return False, "make regen-manifest failed"
        return True, "make regen-manifest passed"

    return True, "project-specific release verification absent; skipped by contract"


def run() -> tuple[bool, str]:
    parts: list[str] = []

    ok_guard, msg_guard = _run_optional_make_target("ci-guard")
    parts.append(msg_guard)
    if not ok_guard:
        return False, "; ".join(parts)

    ok_locks, msg_locks = _run_optional_make_target("ci-locks")
    parts.append(msg_locks)
    if not ok_locks:
        return False, "; ".join(parts)

    ok_project, msg_project = _run_optional_project_release_script()
    parts.append(msg_project)
    if not ok_project:
        return False, "; ".join(parts)

    ok_proof, msg_proof = _aggregate_required_proof_artifacts()
    parts.append(msg_proof)
    if not ok_proof:
        return False, "; ".join(parts)

    return True, "; ".join(parts)


__all__ = ["CANON_VERIFY_RELEASE_ARTIFACT_AGGREGATION", "run"]
