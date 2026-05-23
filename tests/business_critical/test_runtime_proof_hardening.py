from __future__ import annotations

import json
from pathlib import Path

import scripts.ci.step_container_runtime as step_container_runtime
import scripts.ci.step_production_boot as step_production_boot
from scripts.ci.pytest_tools import run_pytest_with_report


def test_container_runtime_gate_requires_evidence_when_declared(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(step_container_runtime, "repo_root", lambda: tmp_path)
    monkeypatch.setenv("CONTAINER_RUNTIME_EVIDENCE_REQUIRED", "1")
    monkeypatch.delenv("CONTAINER_RUNTIME_PROOF_REQUIRED", raising=False)

    ok, message = step_container_runtime.run()
    payload = json.loads((tmp_path / "artifacts" / "ci" / "container_runtime.json").read_text(encoding="utf-8"))

    assert ok is False
    assert "container_runtime_evidence_required" in message
    assert payload["status"] == "blocked"
    assert "container_runtime_evidence_required" in payload["violations"]
    assert payload["claims_production_ready"] is False


def test_container_runtime_gate_accepts_real_evidence(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(step_container_runtime, "repo_root", lambda: tmp_path)
    artifact_dir = tmp_path / "artifacts" / "ci"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "container_runtime_evidence.json").write_text(
        json.dumps(
            {
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
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    ok, message = step_container_runtime.run()
    payload = json.loads((artifact_dir / "container_runtime.json").read_text(encoding="utf-8"))

    assert ok is True, message
    assert payload["status"] == "ready"
    assert payload["evidence_source"] == "container_runtime_evidence.json"
    assert payload["evidence_kind"] == "real_container_runtime_probe"
    assert payload["claims_production_ready"] is False


def test_production_boot_contract_requires_real_boot_evidence_when_declared(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(step_production_boot, "repo_root", lambda: tmp_path)
    artifact_dir = tmp_path / "artifacts" / "ci"
    artifact_dir.mkdir(parents=True)
    for name in ("postgres_contract.json", "postgres_migrations.json", "postgres_live.json", "container_runtime.json"):
        (artifact_dir / name).write_text(json.dumps({"artifact": name.removesuffix(".json"), "status": "ready"}), encoding="utf-8")
    monkeypatch.setenv("REAL_RUNTIME_BOOT_EVIDENCE_REQUIRED", "1")
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("APP_PROFILE", "api")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/db")
    monkeypatch.setenv("POSTGRES_RUNTIME_ENABLED", "1")
    monkeypatch.setenv("RUN_MIGRATIONS_BEFORE_START", "1")
    monkeypatch.setenv("BAIOS_REQUIRE_QUALITY_TOOLS", "release")

    ok, message = step_production_boot.run()
    payload = json.loads((artifact_dir / "production_boot.json").read_text(encoding="utf-8"))

    assert ok is False
    assert "real_runtime_boot_evidence" in message
    assert payload["artifact"] == "production_boot_contract"
    assert payload["proof_kind"] == "contract_aggregation_not_process_boot"
    assert payload["claims_real_runtime_boot"] is False
    assert "real_runtime_boot_evidence_required" in payload["violations"]
    assert payload["claims_production_ready"] is False


def test_production_boot_contract_records_real_boot_evidence(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(step_production_boot, "repo_root", lambda: tmp_path)
    artifact_dir = tmp_path / "artifacts" / "ci"
    artifact_dir.mkdir(parents=True)
    for name in ("postgres_contract.json", "postgres_migrations.json", "postgres_live.json", "container_runtime.json"):
        (artifact_dir / name).write_text(json.dumps({"artifact": name.removesuffix(".json"), "status": "ready"}), encoding="utf-8")
    (artifact_dir / "real_runtime_boot_evidence.json").write_text(
        json.dumps({"artifact": "real_runtime_boot_evidence", "status": "ready", "claims_production_ready": False}),
        encoding="utf-8",
    )
    monkeypatch.setenv("REAL_RUNTIME_BOOT_EVIDENCE_REQUIRED", "1")
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("APP_PROFILE", "api")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/db")
    monkeypatch.setenv("POSTGRES_RUNTIME_ENABLED", "1")
    monkeypatch.setenv("RUN_MIGRATIONS_BEFORE_START", "1")
    monkeypatch.setenv("BAIOS_REQUIRE_QUALITY_TOOLS", "release")

    ok, message = step_production_boot.run()
    payload = json.loads((artifact_dir / "production_boot.json").read_text(encoding="utf-8"))

    assert ok is True, message
    assert payload["status"] == "contract_satisfied"
    assert payload["claims_real_runtime_boot"] is True
    assert payload["claims_production_ready"] is False


def test_pytest_coverage_artifact_is_explicitly_not_code_coverage(tmp_path: Path, monkeypatch) -> None:
    import scripts.ci.pytest_tools as pytest_tools

    monkeypatch.setattr(pytest_tools, "junit_dir", lambda: tmp_path / "junit")
    monkeypatch.setattr(pytest_tools, "coverage_dir", lambda: tmp_path / "coverage")

    class Outcome:
        returncode = 0

    monkeypatch.setattr(pytest_tools, "run_pytest", lambda args, timeout=None: Outcome())

    ok, message = run_pytest_with_report(
        target_args=["tests/example"],
        mark_expression="not slow",
        junit_name="example.xml",
        coverage_name="example.coverage.json",
        timeout=1,
    )
    payload = json.loads((tmp_path / "coverage" / "example.coverage.json").read_text(encoding="utf-8"))

    assert ok is True, message
    assert "code coverage not collected" in message
    assert payload["coverage_kind"] == "not_code_coverage"
    assert payload["claims_code_coverage"] is False
    assert payload["claims_production_ready"] is False


def test_runtime_manifest_loader_is_not_stale_boot_dependency() -> None:
    root = Path.cwd()
    suspicious = []
    for path in (root / "runtime").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "runtime_manifest_loader" in text or "RUNTIME_BOOT_MANIFEST" in text:
            suspicious.append(path.relative_to(root).as_posix())
    assert suspicious == []
