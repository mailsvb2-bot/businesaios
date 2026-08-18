from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from xml.etree import ElementTree

from scripts.ci.config import SECURITY_TEST_TARGET, project_shape_config
from scripts.ci.makefile_tools import has_make_target
from scripts.ci.paths import junit_dir, repo_root
from scripts.ci.pytest_tools import run_pytest_sharded_with_report
from scripts.ci.step_demo_e2e_smoke import cleanup_ci_runtime_state
from scripts.ci.subprocess_io import CommandOutcome, run_command, run_python

CANON_VERIFY_RELEASE_ARTIFACT_AGGREGATION = True
CANON_VERIFY_RELEASE_COMMAND_DIAGNOSTICS = True
SECURITY_ADVERSARIAL_JUNIT = "security-release.xml"
SECURITY_ADVERSARIAL_SCHEMA = "businessaios_security_adversarial_evidence.v1"

_REQUIRED_PROOF_ARTIFACTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("postgres_contract.json", ("ready",)),
    ("postgres_migrations.json", ("ready",)),
    ("postgres_live.json", ("ready",)),
    ("container_runtime.json", ("ready",)),
    ("staging_runtime_proof.json", ("ready",)),
    ("production_boot.json", ("contract_satisfied",)),
)
_COMMAND_FAILURE_ARTIFACT = "verify_release_command_failure.json"


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


def _clear_command_failure_artifact() -> None:
    _artifact_path(_COMMAND_FAILURE_ARTIFACT).unlink(missing_ok=True)


def _diagnostic_tail(value: str, *, limit: int = 12_000) -> str:
    normalized = "\n".join(line.rstrip() for line in value.splitlines()).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[-limit:]


def _write_command_failure_artifact(
    *,
    label: str,
    command: Sequence[str],
    outcome: CommandOutcome,
) -> Path:
    path = _artifact_path(_COMMAND_FAILURE_ARTIFACT)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "artifact": "verify_release_command_failure",
        "status": "failed",
        "label": label,
        "command": list(command),
        "returncode": int(outcome.returncode),
        "stdout_tail": _diagnostic_tail(outcome.stdout),
        "stderr_tail": _diagnostic_tail(outcome.stderr),
        "claims_production_ready": False,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _command_failure_message(
    *,
    label: str,
    command: Sequence[str],
    outcome: CommandOutcome,
) -> str:
    path = _write_command_failure_artifact(
        label=label,
        command=command,
        outcome=outcome,
    )
    output = _diagnostic_tail(outcome.stderr or outcome.stdout, limit=1_500)
    last_line = output.splitlines()[-1] if output else "command produced no diagnostic output"
    relative = path.relative_to(repo_root()).as_posix()
    return (
        f"{label} failed (exit={outcome.returncode}): {last_line}; "
        f"diagnostics={relative}"
    )


def _exact_sha(value: str | None) -> bool:
    return bool(value and len(value) == 40 and value == value.lower() and all(char in "0123456789abcdef" for char in value))


def _junit_stats(path: Path) -> dict[str, int] | None:
    try:
        root = ElementTree.parse(path).getroot()
        return {key: int(root.attrib.get(key, "0") or 0) for key in ("tests", "failures", "errors", "skipped")}
    except (OSError, ElementTree.ParseError, TypeError, ValueError):
        return None


def _run_security_adversarial_proof() -> tuple[bool, str, dict[str, object]]:
    cfg = project_shape_config(repo_root())
    targets = [target for target in cfg.unit_targets if target == SECURITY_TEST_TARGET]
    exact_sha = os.environ.get("BAIOS_CI_TARGET_SHA")
    violations: list[str] = []
    if targets != [SECURITY_TEST_TARGET]:
        violations.append("security_canonical_target_missing")
        pytest_ok = False
    else:
        pytest_ok, _ = run_pytest_sharded_with_report(
            target_args=targets,
            mark_expression=cfg.unit_mark_expression,
            junit_name=SECURITY_ADVERSARIAL_JUNIT,
            coverage_name="security-release-coverage.xml",
            timeout_per_shard=240,
        )
        if not pytest_ok:
            violations.append("security_pytest_failed")
    stats = _junit_stats(junit_dir() / SECURITY_ADVERSARIAL_JUNIT)
    if stats is None:
        violations.append("security_junit_missing_or_invalid")
    else:
        if stats["tests"] <= 0:
            violations.append("security_junit_vacuous")
        if stats["failures"] or stats["errors"]:
            violations.append("security_junit_failed")
        if stats["skipped"]:
            violations.append("security_junit_skipped")
    if not _exact_sha(exact_sha):
        violations.append("security_exact_sha_missing_or_invalid")
    status = "PASS" if not violations else ("NOT_PROVEN" if violations == ["security_exact_sha_missing_or_invalid"] else "FAIL")
    evidence: dict[str, object] = {
        "schema": SECURITY_ADVERSARIAL_SCHEMA,
        "status": status,
        "exact_sha": exact_sha,
        "target": SECURITY_TEST_TARGET,
        "mark_expression": cfg.unit_mark_expression,
        "junit": f"junit/{SECURITY_ADVERSARIAL_JUNIT}",
        "stats": stats or {},
        "violations": violations,
        "repair_owner": "tests/security",
        "claims_production_ready": False,
    }
    if status == "PASS":
        return True, f"security adversarial proof passed: {stats['tests']} tests", evidence
    return False, "security adversarial proof blocked: " + ",".join(violations), evidence


def _aggregate_required_proof_artifacts(*, security_evidence: dict[str, object]) -> tuple[bool, str]:
    artifacts: dict[str, dict[str, object]] = {}
    violations = [str(item) for item in security_evidence.get("violations", []) if str(item)]
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
        "exact_sha": security_evidence.get("exact_sha"),
        "required_artifacts": [name for name, _ in _REQUIRED_PROOF_ARTIFACTS],
        "security_adversarial": security_evidence,
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
    command = ["make", name]
    outcome = run_command(["make", name], env=_canonical_python_env())
    if outcome.returncode != 0:
        return False, _command_failure_message(
            label=f"make target {name}",
            command=command,
            outcome=outcome,
        )
    return True, f"make target passed: {name}"


def _cleanup_runtime_state_before_ci_locks() -> tuple[bool, str]:
    try:
        removed = cleanup_ci_runtime_state()
    except OSError as exc:
        return False, f"pre-ci-lock runtime cleanup failed: {type(exc).__name__}"
    if removed:
        return True, f"pre-ci-lock runtime cleanup removed {len(removed)} mutable runtime artifact(s)"
    return True, "pre-ci-lock runtime cleanup found no mutable DB artifacts"


def _run_optional_project_release_script() -> tuple[bool, str]:
    root = repo_root()

    verify_release = root / "scripts" / "verify_release.sh"
    if verify_release.exists():
        command = ["bash", str(verify_release)]
        outcome = run_command(
            command,
            env=_canonical_python_env(),
        )
        if outcome.returncode != 0:
            return False, _command_failure_message(
                label="verify_release.sh",
                command=command,
                outcome=outcome,
            )
        return True, "verify_release.sh passed"

    package_release = root / "scripts" / "package_release.py"
    if package_release.exists():
        command = ["scripts/package_release.py"]
        outcome = run_python(command)
        if outcome.returncode != 0:
            return False, _command_failure_message(
                label="package_release.py",
                command=[sys.executable, "-S", *command],
                outcome=outcome,
            )
        return True, "package_release.py passed"

    if has_make_target("regen-manifest"):
        command = ["make", "regen-manifest"]
        outcome = run_command(
            command,
            env=_canonical_python_env(),
        )
        if outcome.returncode != 0:
            return False, _command_failure_message(
                label="make regen-manifest",
                command=command,
                outcome=outcome,
            )
        return True, "make regen-manifest passed"

    return True, "project-specific release verification absent; skipped by contract"


def run() -> tuple[bool, str]:
    _clear_command_failure_artifact()
    parts: list[str] = []

    ok_guard, msg_guard = _run_optional_make_target("ci-guard")
    parts.append(msg_guard)
    if not ok_guard:
        return False, "; ".join(parts)

    ok_cleanup, msg_cleanup = _cleanup_runtime_state_before_ci_locks()
    parts.append(msg_cleanup)
    if not ok_cleanup:
        return False, "; ".join(parts)

    ok_locks, msg_locks = _run_optional_make_target("ci-locks")
    parts.append(msg_locks)
    if not ok_locks:
        return False, "; ".join(parts)

    ok_project, msg_project = _run_optional_project_release_script()
    parts.append(msg_project)
    if not ok_project:
        return False, "; ".join(parts)

    ok_security, msg_security, security_evidence = _run_security_adversarial_proof()
    parts.append(msg_security)
    ok_proof, msg_proof = _aggregate_required_proof_artifacts(security_evidence=security_evidence)
    parts.append(msg_proof)
    if not ok_security or not ok_proof:
        return False, "; ".join(parts)

    return True, "; ".join(parts)


__all__ = [
    "CANON_VERIFY_RELEASE_ARTIFACT_AGGREGATION",
    "CANON_VERIFY_RELEASE_COMMAND_DIAGNOSTICS",
    "SECURITY_ADVERSARIAL_JUNIT",
    "SECURITY_ADVERSARIAL_SCHEMA",
    "run",
]
