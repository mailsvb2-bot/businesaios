from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import scripts.ci.step_container_runtime as step_container_runtime
import scripts.ci.step_production_boot as step_production_boot
from scripts.ci.contracts import ExecutionReport, StepResult
from scripts.ci.coverage_report import write_ci_execution_summary_xml


def _isolate_ci_root(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(step_container_runtime, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_production_boot, "repo_root", lambda: tmp_path)
    return tmp_path / "artifacts" / "ci"


def test_container_runtime_declared_requires_real_evidence(monkeypatch, tmp_path: Path) -> None:
    artifact_dir = _isolate_ci_root(monkeypatch, tmp_path)
    monkeypatch.setenv("CONTAINER_RUNTIME_PROOF_REQUIRED", "1")
    monkeypatch.setenv("CONTAINER_IMAGE_BUILT", "1")
    monkeypatch.setenv("CONTAINER_STARTED", "1")
    monkeypatch.setenv("CONTAINER_READYZ_OK", "1")
    monkeypatch.setenv("CONTAINER_STORAGEZ_OK", "1")
    monkeypatch.setenv("CONTAINER_EXECUTIONZ_OK", "1")
    monkeypatch.setenv("CONTAINER_READINESS_HEALTHCHECK_OK", "1")

    ok, message = step_container_runtime.run()
    payload = json.loads((artifact_dir / "container_runtime.json").read_text(encoding="utf-8"))

    assert ok is False
    assert "container_runtime_evidence_required" in message
    assert payload["status"] == "blocked"
    assert "env_flags_do_not_prove_real_container_runtime" in payload["violations"]
    assert payload["claims_production_ready"] is False


def test_container_runtime_accepts_ready_evidence(monkeypatch, tmp_path: Path) -> None:
    artifact_dir = _isolate_ci_root(monkeypatch, tmp_path)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "container_runtime_evidence.json").write_text(json.dumps({
        "artifact": "container_runtime_evidence",
        "status": "ready",
        "evidence_kind": "real_container_runtime_probe",
        "image_built": True,
        "container_started": True,
        "readyz_ok": True,
        "storagez_ok": True,
        "executionz_ok": True,
        "uses_readiness_healthcheck": True,
        "base_image": "businesaios/python-runtime-base:3.12-slim",
        "base_image_pull_policy": "never_during_staging_proof",
        "claims_production_ready": False,
    }), encoding="utf-8")

    ok, message = step_container_runtime.run()
    payload = json.loads((artifact_dir / "container_runtime.json").read_text(encoding="utf-8"))

    assert ok is True, message
    assert payload["status"] == "ready"
    assert payload["evidence_source"] == "container_runtime_evidence.json"
    assert payload["evidence_kind"] == "real_container_runtime_probe"
    assert payload["claims_production_ready"] is False


def test_production_boot_contract_does_not_claim_real_runtime_without_evidence(monkeypatch, tmp_path: Path) -> None:
    artifact_dir = _isolate_ci_root(monkeypatch, tmp_path)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    for name in ("postgres_contract", "postgres_migrations", "postgres_live", "container_runtime"):
        (artifact_dir / f"{name}.json").write_text(json.dumps({"artifact": name, "status": "ready", "claims_production_ready": False}), encoding="utf-8")
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("APP_PROFILE", "api")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/db")
    monkeypatch.setenv("POSTGRES_RUNTIME_ENABLED", "1")
    monkeypatch.setenv("POSTGRES_EVENT_STORE_ENABLED", "1")
    monkeypatch.setenv("RUN_MIGRATIONS_BEFORE_START", "1")
    monkeypatch.delenv("REAL_RUNTIME_BOOT_EVIDENCE_REQUIRED", raising=False)

    ok, message = step_production_boot.run()
    payload = json.loads((artifact_dir / "production_boot.json").read_text(encoding="utf-8"))

    assert ok is True, message
    assert payload["artifact"] == "production_boot_contract"
    assert payload["proof_kind"] == "contract_aggregation_not_process_boot"
    assert payload["claims_real_runtime_boot"] is False
    assert payload["claims_production_ready"] is False


def test_ci_summary_xml_is_not_code_coverage(tmp_path: Path) -> None:
    report = ExecutionReport(gate="full", goal="test")
    report.add(StepResult(name="unit-tests", status="passed", message="ok", duration_ms=1))
    path = tmp_path / "ci-summary.xml"

    write_ci_execution_summary_xml(path, report)
    root = ET.parse(path).getroot()

    assert root.tag == "ci-execution-summary"
    assert root.attrib["claims_code_coverage"] == "false"
    assert root.attrib["claims_production_ready"] == "false"
    assert root.find("summary").attrib["coverage_kind"] == "not_code_coverage"


def test_runtime_boot_manifest_owner_is_importable_and_non_empty() -> None:
    from bootstrap.runtime_boot_manifest import RUNTIME_BOOT_MANIFEST

    assert isinstance(RUNTIME_BOOT_MANIFEST, tuple)
    assert RUNTIME_BOOT_MANIFEST
    for item in RUNTIME_BOOT_MANIFEST:
        assert isinstance(item, dict)
        assert item


def test_boot_runtime_manifest_alias_resolves_to_canonical_owner() -> None:
    import boot.runtime_boot_manifest as alias
    from bootstrap import runtime_boot_manifest as owner

    assert alias.RUNTIME_BOOT_MANIFEST == owner.RUNTIME_BOOT_MANIFEST
    assert getattr(owner, "CANON_RUNTIME_BOOT_MANIFEST_FINAL_OWNER") is True


def test_staging_runner_writes_evidence_before_contract_gates() -> None:
    text = Path("scripts/staging/run_staging_runtime_proof.sh").read_text(encoding="utf-8")

    assert "container_runtime_evidence.json" in text
    assert "real_runtime_boot_evidence.json" in text
    assert "CONTAINER_RUNTIME_EVIDENCE_REQUIRED=1" in text
    assert "REAL_RUNTIME_BOOT_EVIDENCE_REQUIRED=1" in text
    assert text.index("container_runtime_evidence.json") < text.index("run_gate container-runtime")
    assert text.index("real_runtime_boot_evidence.json") < text.index("run_gate production-boot")
