from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.ci import browser_evidence, step_browser_e2e
from scripts.ci.subprocess_io import CommandOutcome


def test_playwright_production_security_bindings_remain_locked() -> None:
    config = Path("frontend/playwright.config.js").read_text(encoding="utf-8")
    assert 'const runtimeMode = process.env.BAIOS_E2E_RUNTIME_MODE || "development"' in config
    assert 'const production = runtimeMode === "production"' in config
    assert '"DATABASE_URL", "DECISION_SIGNING_SECRET", "API_CONTROL_PLANE_API_KEY_PEPPER"' in config
    assert '"BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64", "BUSINESAIOS_ENABLE_POSTGRES_EVENT_STORE"' in config
    assert 'APP_ENV: production ? "production" : "dev"' in config
    assert 'ENV: production ? "production" : "dev"' in config
    assert 'API_CONTROL_PLANE_ALLOW_DEV_FALLBACKS: production ? "0"' in config
    assert 'BUSINESAIOS_API_KEY_STORE_BACKEND: production ? "file"' in config
    assert 'BUSINESAIOS_KEY_PROVIDER_BACKEND: production ? "file"' in config


def test_browser_workflow_execution_and_failure_diagnostics_remain_locked() -> None:
    ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    deep = Path(".github/workflows/deep-release-validation.yml").read_text(encoding="utf-8")
    assert "python -m scripts.ci.cli --gate browser" in ci
    assert ".venv/bin/python -m scripts.ci.cli --gate release" in deep
    assert "DATABASE_URL=$DATABASE_URL" in deep
    evidence = ci.index("- name: Upload browser evidence")
    complete_tree = ci.index("\n  complete-tree:", evidence)
    assert "if: always()" in ci[evidence:complete_tree]


def test_playwright_evidence_timestamps_require_timezone() -> None:
    assert browser_evidence._timestamp("2026-08-11T10:48:09.726Z") is True
    assert browser_evidence._timestamp("2026-08-11T10:48:09+00:00") is True
    for value in ("2026-08-11", "2026-08-11T10:48:09", "2026-08-11T10:48:09.726"):
        assert browser_evidence._timestamp(value) is False


def test_release_runtime_forwards_database_url(monkeypatch, tmp_path) -> None:
    database_url = "postgresql://proof@127.0.0.1:5432/businessaios"
    monkeypatch.setenv("BAIOS_CI_ACTIVE_GATE", "release")
    monkeypatch.setenv("DATABASE_URL", database_url)
    env, mode, storage = step_browser_e2e._runtime_env(sha="a" * 40, runtime_dir=str(tmp_path))
    assert (mode, storage) == ("production", "postgres")
    assert env["DATABASE_URL"] == database_url


def test_browser_step_emits_exact_release_binding_fields(monkeypatch, tmp_path) -> None:
    reports = tmp_path / "artifacts" / "ci"
    frontend = tmp_path / "frontend"
    runtime = tmp_path / "runtime"
    frontend.mkdir(parents=True)
    runtime.mkdir()
    matrix_bytes = Path(browser_evidence.BROWSER_PROJECT_MATRIX).read_bytes()
    matrix = json.loads(matrix_bytes)
    projects = [{**item, "tests": 1} for item in matrix["projects"]]
    snapshot = {
        "stats": {"expected": len(projects), "unexpected": 0, "skipped": 0, "flaky": 0},
        "projects": projects,
        "project_matrix": {
            "path": browser_evidence.BROWSER_PROJECT_MATRIX,
            "schema": browser_evidence.BROWSER_PROJECT_MATRIX_SCHEMA,
            "sha256": hashlib.sha256(matrix_bytes).hexdigest(),
        },
        "artifacts": {
            "json": {"path": "browser-e2e/playwright.json", "sha256": "a" * 64, "bytes": 1},
            "junit": {"path": "browser-e2e/junit.xml", "sha256": "b" * 64, "bytes": 1, "tests": 5, "failures": 0, "skipped": 0},
            "html": {"path": "browser-e2e/html/index.html", "sha256": "c" * 64, "bytes": 1},
        },
    }
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "d" * 40)
    monkeypatch.delenv("BAIOS_CI_ACTIVE_GATE", raising=False)
    monkeypatch.setattr(step_browser_e2e, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_browser_e2e, "reports_dir", lambda: reports)
    monkeypatch.setattr(step_browser_e2e.shutil, "which", lambda command: "/usr/bin/npm")
    monkeypatch.setattr(step_browser_e2e.tempfile, "mkdtemp", lambda **kwargs: str(runtime))
    monkeypatch.setattr(step_browser_e2e, "browser_artifact_snapshot", lambda browser_dir: snapshot)
    monkeypatch.setattr(step_browser_e2e, "run_command", lambda *args, **kwargs: CommandOutcome(0, "", ""))

    result = step_browser_e2e.run()
    evidence = json.loads((reports / browser_evidence.BROWSER_EVIDENCE_NAME).read_text(encoding="utf-8"))
    assert result[0] is True
    assert evidence["status"] == "PASS"
    assert evidence["exact_sha"] == "d" * 40
    assert evidence["runtime_mode"] == "development"
    assert evidence["storage_backend"] == "isolated-local"
    assert evidence["projects"] == projects
    assert all(item["tests"] == 1 for item in evidence["projects"])
    assert evidence["project_matrix"]["sha256"] == hashlib.sha256(matrix_bytes).hexdigest()
