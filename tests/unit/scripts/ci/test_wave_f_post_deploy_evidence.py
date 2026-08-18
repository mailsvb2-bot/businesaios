from __future__ import annotations

import json
from pathlib import Path

from scripts.ci.post_deploy_evidence import finalize_release_verdict

ROOT = Path(__file__).resolve().parents[4]
SHA = "a" * 40
REQUIRED_CHECKS = (
    "production_environment_file", "production_environment", "production_ingress",
    "production_runtime_bindings", "production_credentials", "deployed_sha", "sha_match",
    "service_state", "nginx", "health", "readiness", "runtime", "postgresql",
    "synthetic_flow", "public_api", "public_status",
)


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _base(tmp_path: Path, *, status: str = "PASS", sha: str = SHA) -> Path:
    return _write(tmp_path / "release-verdict.json", {
        "schema": "businessaios_release_verdict.v1", "gate": "release", "status": status,
        "exact_sha": sha, "canonical_user_scenarios": {"status": "PASS"},
        "browser_e2e": {"status": "PASS"}, "security_verification": {"status": "PASS"},
        "steps": [],
    })


def _host(tmp_path: Path, *, sha: str = SHA, verdict: str = "pass", drop_check: str | None = None) -> Path:
    checks = {name: {"status": "pass"} for name in REQUIRED_CHECKS if name != drop_check}
    return _write(tmp_path / "production-host-verdict.json", {
        "schema_version": 1, "verdict": verdict, "expected_sha": sha, "observed_sha": sha,
        "environment": "production", "tenant_id": "production-smoke",
        "synthetic_run_id": "run-1", "checks": checks,
    })


def _hardware(tmp_path: Path, *, sha: str = SHA, trusted: bool = True, ref: str = "refs/heads/main") -> Path:
    return _write(tmp_path / "physical_hardware_evidence.json", {
        "schema": "businessaios_physical_hardware_evidence.v1", "status": "PASS",
        "exact_sha": sha, "ref": ref, "trusted_execution": trusted, "canonical_gate": "acceptance",
    })


def test_wave_f_finalizes_same_release_verdict_with_real_host_evidence(tmp_path: Path) -> None:
    output = tmp_path / "final.json"
    verdict = finalize_release_verdict(
        base_path=_base(tmp_path), production_path=_host(tmp_path), output_path=output, exact_sha=SHA,
    )
    assert verdict["schema"] == "businessaios_release_verdict.v1"
    assert verdict["status"] == "PASS"
    assert verdict["verification_phase"] == "post_deploy"
    assert verdict["production_verified"] is True
    assert verdict["production_synthetic"]["status"] == "PASS"
    assert verdict["production_synthetic"]["source"] == "scripts/server/verify_runtime_host_contract.sh"
    assert verdict["physical_hardware"]["status"] == "NOT_PROVEN"
    assert verdict["physical_hardware"]["optional"] is True
    assert json.loads(output.read_text(encoding="utf-8"))["production_verified"] is True


def test_wave_f_fails_closed_on_stale_or_incomplete_production_evidence(tmp_path: Path) -> None:
    stale = finalize_release_verdict(
        base_path=_base(tmp_path), production_path=_host(tmp_path, sha="b" * 40),
        output_path=tmp_path / "stale.json", exact_sha=SHA,
    )
    assert stale["status"] == "NOT_PROVEN"
    assert stale["production_verified"] is False

    incomplete = finalize_release_verdict(
        base_path=_base(tmp_path), production_path=_host(tmp_path, drop_check="synthetic_flow"),
        output_path=tmp_path / "incomplete.json", exact_sha=SHA,
    )
    assert incomplete["status"] == "FAIL"
    assert incomplete["production_verified"] is False


def test_wave_f_never_upgrades_an_unproven_predeploy_verdict(tmp_path: Path) -> None:
    verdict = finalize_release_verdict(
        base_path=_base(tmp_path, status="NOT_PROVEN"), production_path=_host(tmp_path),
        output_path=tmp_path / "final.json", exact_sha=SHA,
    )
    assert verdict["status"] == "NOT_PROVEN"
    assert verdict["production_verified"] is False


def test_optional_hardware_is_trusted_when_present_and_fails_closed_when_invalid(tmp_path: Path) -> None:
    passed = finalize_release_verdict(
        base_path=_base(tmp_path), production_path=_host(tmp_path), hardware_path=_hardware(tmp_path),
        output_path=tmp_path / "hardware-pass.json", exact_sha=SHA,
    )
    assert passed["status"] == "PASS"
    assert passed["physical_hardware"]["status"] == "PASS"

    failed = finalize_release_verdict(
        base_path=_base(tmp_path), production_path=_host(tmp_path), hardware_path=_hardware(tmp_path, trusted=False),
        output_path=tmp_path / "hardware-fail.json", exact_sha=SHA,
    )
    assert failed["status"] == "FAIL"
    assert failed["production_verified"] is False


def test_protected_production_workflow_never_exposes_self_hosted_runner_to_pr_code() -> None:
    text = (ROOT / ".github/workflows/protected-production-verification.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text and "pull_request_target:" not in text and "\n  push:" not in text
    assert "environment: production" in text
    assert "runs-on: [self-hosted, Linux, X64, baios-production]" in text
    assert 'test "$GITHUB_REF" = "refs/heads/main"' in text
    assert "deep-release-validation.yml" in text and "event=push&status=success" in text
    assert "/opt/businesaios/scripts/server/verify_runtime_host_contract.sh" in text
    assert "scripts.ci.post_deploy_evidence" in text
    assert "continue-on-error" not in text


def test_physical_hardware_workflow_is_manual_protected_and_reuses_acceptance_gate() -> None:
    text = (ROOT / ".github/workflows/protected-physical-hardware-verification.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text and "pull_request_target:" not in text and "\n  push:" not in text
    assert "environment: production-hardware" in text
    assert "runs-on: [self-hosted, Windows, X64, baios-production-hardware]" in text
    assert "python -m scripts.ci.cli --gate acceptance" in text
    assert "businessaios_physical_hardware_evidence.v1" in text
    assert '"trusted_execution": True' in text
    assert "continue-on-error" not in text
