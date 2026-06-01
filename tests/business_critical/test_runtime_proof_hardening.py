from __future__ import annotations

import json
from pathlib import Path

from scripts.ci.pytest_tools import run_pytest_with_report
import scripts.ci.step_production_boot as step_production_boot


_VALID_CONTRACT_DSN = "postgresql://user:pass@db.internal.invalid:5432/businesaios"


def test_production_boot_contract_requires_real_boot_evidence_when_declared(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(step_production_boot, "repo_root", lambda: tmp_path)
    artifact_dir = tmp_path / "artifacts" / "ci"
    artifact_dir.mkdir(parents=True)
    for name in ("postgres_contract.json", "postgres_migrations.json", "postgres_live.json", "container_runtime.json"):
        (artifact_dir / name).write_text(json.dumps({"artifact": name.removesuffix(".json"), "status": "ready"}), encoding="utf-8")
    monkeypatch.setenv("REAL_RUNTIME_BOOT_EVIDENCE_REQUIRED", "1")
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("APP_PROFILE", "api")
    monkeypatch.setenv("DATABASE_URL", _VALID_CONTRACT_DSN)
    monkeypatch.setenv("POSTGRES_RUNTIME_ENABLED", "1")
    monkeypatch.setenv("RUN_MIGRATIONS_BEFORE_START", "1")
    monkeypatch.setenv("BAIOS_REQUIRE_QUALITY_TOOLS", "release")

    ok, message = step_production_boot.run()
    payload = json.loads((artifact_dir / "production_boot.json").read_text(encoding="utf-8"))

    assert ok is False
    assert "real_runtime_boot_evidence_required" in message
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
    monkeypatch.setenv("DATABASE_URL", _VALID_CONTRACT_DSN)
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
        stdout = ""
        stderr = ""

    monkeypatch.setattr(pytest_tools, "run_pytest", lambda args, timeout=None: Outcome())

    ok, message = run_pytest_with_report(
        target_args=["tests/unit"],
        mark_expression="not slow",
        junit_name="unit.xml",
        coverage_name="unit-coverage.xml",
    )

    payload = json.loads((tmp_path / "coverage" / "unit-coverage.xml").read_text(encoding="utf-8"))
    assert ok is True, message
    assert payload["coverage_kind"] == "not_code_coverage"
    assert payload["claims_code_coverage"] is False
    assert payload["claims_production_ready"] is False
