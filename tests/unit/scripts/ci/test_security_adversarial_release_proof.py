from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.ci import step_verify_release
from scripts.ci.config import SECURITY_TEST_TARGET, project_shape_config
from scripts.ci.contracts import ExecutionReport, StepResult
from scripts.ci.reports import release_verdict

ROOT = Path(__file__).resolve().parents[4]


def _write_junit(path: Path, *, tests: int = 3, failures: int = 0, errors: int = 0, skipped: int = 0) -> None:
    path.write_text(
        f'<testsuites tests="{tests}" failures="{failures}" errors="{errors}" skipped="{skipped}" time="0.1"/>',
        encoding="utf-8",
    )


def _proof_artifacts(root: Path) -> Path:
    target = root / "artifacts" / "ci"
    target.mkdir(parents=True, exist_ok=True)
    for name, status in {
        "postgres_contract.json": "ready",
        "postgres_migrations.json": "ready",
        "postgres_live.json": "ready",
        "container_runtime.json": "ready",
        "staging_runtime_proof.json": "ready",
        "production_boot.json": "contract_satisfied",
    }.items():
        (target / name).write_text(json.dumps({"status": status}), encoding="utf-8")
    return target


def _install_security_result(monkeypatch, artifact_dir: Path, evidence: dict[str, object]) -> None:
    def fake_security_proof() -> tuple[bool, str, dict[str, object]]:
        (artifact_dir / "security_adversarial.json").write_text(json.dumps(evidence), encoding="utf-8")
        ok = evidence["status"] == "PASS"
        return ok, "security:ready" if ok else "security:blocked", evidence

    monkeypatch.setattr(step_verify_release, "_run_security_adversarial_proof", fake_security_proof)


def test_security_release_proof_reuses_the_existing_canonical_unit_target() -> None:
    cfg = project_shape_config(ROOT)
    assert SECURITY_TEST_TARGET in cfg.unit_targets
    source = (ROOT / "scripts/ci/step_verify_release.py").read_text(encoding="utf-8")
    assert "target_args=targets" in source
    assert 'target_args=["tests/security"]' not in source
    assert "target_args=['tests/security']" not in source


def test_verify_release_keeps_the_existing_zero_argument_aggregation_seam() -> None:
    assert tuple(inspect.signature(step_verify_release._aggregate_required_proof_artifacts).parameters) == ()


def test_security_adversarial_proof_is_exact_sha_bound_and_non_vacuous(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "a" * 40)
    monkeypatch.setattr(step_verify_release, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_verify_release, "junit_dir", lambda: tmp_path)
    monkeypatch.setattr(
        step_verify_release,
        "run_pytest_sharded_with_report",
        lambda **kwargs: (True, "pytest passed"),
    )
    _write_junit(tmp_path / step_verify_release.SECURITY_ADVERSARIAL_JUNIT, tests=7)

    ok, message, evidence = step_verify_release._run_security_adversarial_proof()

    assert ok is True
    assert "7 tests" in message
    assert evidence["schema"] == step_verify_release.SECURITY_ADVERSARIAL_SCHEMA
    assert evidence["status"] == "PASS"
    assert evidence["exact_sha"] == "a" * 40
    assert evidence["target"] == SECURITY_TEST_TARGET
    assert evidence["stats"] == {"tests": 7, "failures": 0, "errors": 0, "skipped": 0}
    assert evidence["violations"] == []
    written = json.loads((tmp_path / "artifacts/ci/security_adversarial.json").read_text(encoding="utf-8"))
    assert written == evidence


def test_security_adversarial_proof_fails_closed_on_skips(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "b" * 40)
    monkeypatch.setattr(step_verify_release, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_verify_release, "junit_dir", lambda: tmp_path)
    monkeypatch.setattr(step_verify_release, "run_pytest_sharded_with_report", lambda **kwargs: (True, "pytest passed"))
    _write_junit(tmp_path / step_verify_release.SECURITY_ADVERSARIAL_JUNIT, tests=4, skipped=1)

    ok, _, evidence = step_verify_release._run_security_adversarial_proof()

    assert ok is False
    assert evidence["status"] == "FAIL"
    assert "security_junit_skipped" in evidence["violations"]


def test_security_adversarial_proof_is_not_proven_without_exact_sha(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("BAIOS_CI_TARGET_SHA", raising=False)
    monkeypatch.setattr(step_verify_release, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_verify_release, "junit_dir", lambda: tmp_path)
    monkeypatch.setattr(step_verify_release, "run_pytest_sharded_with_report", lambda **kwargs: (True, "pytest passed"))
    _write_junit(tmp_path / step_verify_release.SECURITY_ADVERSARIAL_JUNIT)

    ok, _, evidence = step_verify_release._run_security_adversarial_proof()

    assert ok is False
    assert evidence["status"] == "NOT_PROVEN"
    assert evidence["violations"] == ["security_exact_sha_missing_or_invalid"]


def test_verify_release_artifact_aggregates_security_as_required_evidence(monkeypatch, tmp_path) -> None:
    artifact_dir = _proof_artifacts(tmp_path)
    monkeypatch.setattr(step_verify_release, "repo_root", lambda: tmp_path)
    security = {
        "schema": step_verify_release.SECURITY_ADVERSARIAL_SCHEMA,
        "status": "PASS",
        "exact_sha": "c" * 40,
        "violations": [],
        "repair_owner": "tests/security",
        "claims_production_ready": False,
    }
    _install_security_result(monkeypatch, artifact_dir, security)

    ok, _ = step_verify_release._aggregate_required_proof_artifacts()
    payload = json.loads((artifact_dir / "verify_release.json").read_text(encoding="utf-8"))

    assert ok is True
    assert payload["status"] == "ready"
    assert payload["exact_sha"] == "c" * 40
    assert payload["artifacts"]["security_adversarial"] == security
    assert "security_adversarial.json" in payload["required_artifacts"]
    assert payload["claims_production_ready"] is False

    blocked = dict(security, status="FAIL", violations=["security_junit_skipped"])
    _install_security_result(monkeypatch, artifact_dir, blocked)
    ok, _ = step_verify_release._aggregate_required_proof_artifacts()
    payload = json.loads((artifact_dir / "verify_release.json").read_text(encoding="utf-8"))
    assert ok is False
    assert payload["status"] == "blocked"
    assert "security_adversarial_not_ready" in payload["violations"]
    assert payload["artifacts"]["security_adversarial"]["violations"] == ["security_junit_skipped"]


def test_canonical_release_verdict_surfaces_security_layer_from_verify_release(monkeypatch) -> None:
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "d" * 40)
    report = ExecutionReport(
        gate="fast",
        goal="test",
        steps=[StepResult(name="verify-release", status="passed", message="verified", duration_ms=1)],
    )

    verdict = release_verdict(report)

    assert verdict["security_verification"] == {
        "source_step": "verify-release",
        "status": "PASS",
        "artifact": "verify_release.json",
        "layer": "security_adversarial",
    }
    assert verdict["status"] == "NOT_PROVEN"
