from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ci import physical_hardware_evidence as hardware
from scripts.ci.trusted_release_evidence import TrustedEvidenceError, finalize_trusted_release_verdict

ROOT = Path(__file__).resolve().parents[4]
SHA = "a" * 40
WORKFLOW = ROOT / ".github" / "workflows" / "trusted-production-certification.yml"
PRODUCTION_ADAPTER = ROOT / "scripts" / "server" / "production_synthetic_evidence.sh"
PRIVILEGED_BRIDGE = ROOT / "scripts" / "server" / "production_synthetic_privileged_bridge.sh"
SYSTEMD_INSTALLER = ROOT / "deploy" / "systemd" / "install.sh"
REQUIRED_CHECKS = (
    "canonical_python", "production_environment_file", "production_environment", "production_ingress",
    "production_runtime_bindings", "production_credentials", "deployed_sha", "sha_match", "service_state",
    "nginx", "health", "readiness", "runtime", "postgresql", "synthetic_flow", "public_api", "public_status",
)


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _base(status: str = "PASS") -> dict:
    return {"schema": "businessaios_release_verdict.v1", "exact_sha": SHA, "gate": "release", "status": status,
            "scope": "canonical", "canonical_user_scenarios": {"status": "PASS"}, "browser_e2e": {"status": "PASS"}}


def _production(*, exact_sha: str = SHA, status: str = "PASS") -> dict:
    return {
        "schema": "businessaios_production_synthetic_evidence.v1", "status": status,
        "exact_sha": exact_sha, "observed_sha": exact_sha, "environment": "production",
        "tenant_id": "production-smoke", "synthetic_run_id": "run-1", "claims_production_ready": False,
        "checks": {name: {"status": "pass"} for name in REQUIRED_CHECKS},
    }


def _physical() -> dict:
    return {"schema": "businessaios_physical_hardware_evidence.v1", "status": "PASS", "exact_sha": SHA,
            "platform": "windows", "runner": "physical-01", "acceptance_gate": "PASS", "claims_production_ready": False}


def test_wave_f_finalizer_is_monotonic_and_cannot_promote_not_proven(tmp_path: Path) -> None:
    with pytest.raises(TrustedEvidenceError, match="not PASS"):
        finalize_trusted_release_verdict(
            base_verdict_path=_write(tmp_path / "base.json", _base("NOT_PROVEN")),
            production_evidence_path=_write(tmp_path / "production.json", _production()),
            output_path=tmp_path / "out.json",
        )
    assert not (tmp_path / "out.json").exists()


def test_wave_f_requires_exact_sha_and_all_factual_production_checks(tmp_path: Path) -> None:
    production = _production(exact_sha="b" * 40)
    production["checks"].pop("synthetic_flow")
    result = finalize_trusted_release_verdict(
        base_verdict_path=_write(tmp_path / "base.json", _base()),
        production_evidence_path=_write(tmp_path / "production.json", production),
        output_path=tmp_path / "out.json",
    )
    assert result["status"] == "FAIL"
    proof = result["production_synthetic"]
    assert "production_synthetic_exact_sha_mismatch" in proof["violations"]
    assert any("synthetic_flow" in item for item in proof["violations"])


def test_wave_f_malformed_check_entry_fails_closed(tmp_path: Path) -> None:
    production = _production()
    production["checks"]["runtime"] = "not-an-object"
    result = finalize_trusted_release_verdict(
        base_verdict_path=_write(tmp_path / "base.json", _base()),
        production_evidence_path=_write(tmp_path / "production.json", production),
        output_path=tmp_path / "out.json",
    )
    assert result["status"] == "FAIL"
    assert any("runtime" in item for item in result["production_synthetic"]["violations"])


def test_wave_f_production_certification_passes_without_optional_hardware(tmp_path: Path) -> None:
    result = finalize_trusted_release_verdict(
        base_verdict_path=_write(tmp_path / "base.json", _base()),
        production_evidence_path=_write(tmp_path / "production.json", _production()),
        output_path=tmp_path / "out.json",
    )
    assert result["schema"] == "businessaios_release_verdict.v1"
    assert result["status"] == "PASS"
    assert result["production_synthetic"]["status"] == "PASS"
    assert result["physical_hardware"]["status"] == "NOT_PROVEN"
    assert result["trusted_evidence"]["physical_hardware_required"] is False


def test_wave_f_can_require_physical_hardware_on_same_sha(tmp_path: Path) -> None:
    result = finalize_trusted_release_verdict(
        base_verdict_path=_write(tmp_path / "base.json", _base()),
        production_evidence_path=_write(tmp_path / "production.json", _production()),
        physical_evidence_path=_write(tmp_path / "physical.json", _physical()),
        require_physical_hardware=True,
        output_path=tmp_path / "out.json",
    )
    assert result["status"] == "PASS"
    assert result["physical_hardware"]["status"] == "PASS"


def test_physical_evidence_requires_windows_and_passed_canonical_acceptance(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    report = _write(tmp_path / "acceptance.report.json", {
        "gate": "acceptance", "success": True,
        "steps": [{"name": "user-scenario-gate", "status": "passed", "message": "ok", "duration_ms": 1}],
    })
    monkeypatch.setattr(hardware.platform, "system", lambda: "Windows")
    evidence = hardware.build_evidence(acceptance_report=report, exact_sha=SHA, runner="physical-01")
    assert evidence["status"] == "PASS"
    monkeypatch.setattr(hardware.platform, "system", lambda: "Linux")
    with pytest.raises(RuntimeError, match="must be produced on Windows"):
        hardware.build_evidence(acceptance_report=report, exact_sha=SHA, runner="not-physical")


def test_public_repo_self_hosted_workflow_is_manual_and_trust_gated() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text
    assert "pull_request_target:" not in text
    assert "runs-on: [self-hosted, linux, production]" in text
    assert "runs-on: [self-hosted, windows, x64, physical-hardware]" in text
    assert "needs: trust_gate" in text
    assert "trusted certification accepts current main only" in text
    assert "Deep Release SHA mismatch" in text
    assert 'deep-release-$TARGET_SHA' in text
    assert 'artifacts/deep-release/artifacts/ci/release-verdict.json' in text
    assert "environment: production" in text
    assert "environment: physical-hardware" in text


def test_production_adapter_never_persists_legacy_verdict_as_wave_f_authority() -> None:
    text = PRODUCTION_ADAPTER.read_text(encoding="utf-8")
    assert "businessaios_production_synthetic_evidence.v1" in text
    assert '"claims_production_ready": False' in text
    assert "mktemp" in text and "rm -f \"$TEMP_VERDICT\"" in text
    assert "PRODUCTION_VERDICT_PATH=\"$TEMP_VERDICT\"" in text
    assert "production-synthetic-$EXPECTED_SHA.json" in text


def test_wave_f_production_runner_uses_narrow_root_owned_bridge() -> None:
    adapter = PRODUCTION_ADAPTER.read_text(encoding="utf-8")
    bridge = PRIVILEGED_BRIDGE.read_text(encoding="utf-8")
    installer = SYSTEMD_INSTALLER.read_text(encoding="utf-8")

    assert 'PRIVILEGED_BRIDGE="/usr/local/sbin/businesaios-production-synthetic-evidence"' in adapter
    assert 'sudo -n "$PRIVILEGED_BRIDGE" "$EXPECTED_SHA"' in adapter
    assert 'trusted production evidence bridge must run as root' in bridge
    assert '[[ "$#" -eq 1 ]]' in bridge
    assert 'git -C "$APP_DIR" rev-parse HEAD' in bridge
    assert 'env -i' in bridge
    assert 'production_synthetic_evidence.sh' in bridge
    assert '[[ -r "$ADAPTER" ]]' in bridge
    assert '[[ -x "$ADAPTER" ]]' not in bridge
    assert 'verify_runtime_host_contract.sh' not in bridge
    assert 'unexpected production evidence fields' in bridge
    assert 'NOPASSWD: %s *' in installer
    assert 'visudo -cf' in installer
    assert 'runuser -u "$runner_user" -- sudo -n -l' in installer
