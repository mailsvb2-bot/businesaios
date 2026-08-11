from __future__ import annotations

import base64
import io
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

from scripts.ci import execution, step_browser_e2e
from scripts.ci.browser_evidence import (
    BROWSER_EVIDENCE_SCHEMA,
    BROWSER_PROJECT_MATRIX,
    browser_artifact_snapshot,
    browser_project_names,
)
from scripts.ci.plan_registry import allowed_gates, plan_for_gate, requires_release_runtime_environment
from scripts.ci.step_registry import handler_for_step
from scripts.ci.subprocess_io import CommandOutcome


def _matrix() -> list[dict]:
    return json.loads(Path(BROWSER_PROJECT_MATRIX).read_text(encoding="utf-8"))["projects"]


def test_browser_project_matrix_is_canonical_and_single_owned() -> None:
    expected = [
        {"name": "chromium", "device": "Desktop Chrome", "engine": "chromium", "surface": "desktop"},
        {"name": "firefox", "device": "Desktop Firefox", "engine": "firefox", "surface": "desktop"},
        {"name": "webkit", "device": "Desktop Safari", "engine": "webkit", "surface": "desktop"},
        {"name": "Mobile Chrome", "device": "Pixel 5", "engine": "chromium", "surface": "mobile"},
        {"name": "Mobile Safari", "device": "iPhone 12", "engine": "webkit", "surface": "mobile"},
    ]
    assert _matrix() == expected
    assert browser_project_names() == tuple(item["name"] for item in expected)
    config = Path("frontend/playwright.config.js").read_text(encoding="utf-8")
    assert 'readFileSync(new URL("./e2e/project-matrix.json", import.meta.url)' in config
    assert "browserName: entry.engine" in config


def test_browser_gate_and_release_plan_are_canonical() -> None:
    assert "browser" in allowed_gates()
    assert tuple(step.name for step in plan_for_gate("browser").steps) == (
        "assert-project-shape", "dependency-lock", "doctor-check", "browser-e2e",
    )
    assert "browser-e2e" not in tuple(step.name for step in plan_for_gate("full").steps)
    for gate in ("release", "pre-release"):
        names = tuple(step.name for step in plan_for_gate(gate).steps)
        assert names[names.index("production-boot") + 1:names.index("verify-release")] == ("browser-e2e",)
        assert requires_release_runtime_environment(gate=gate, step_name="browser-e2e") is True
    assert requires_release_runtime_environment(gate="browser", step_name="browser-e2e") is False
    assert callable(handler_for_step("browser-e2e"))


def test_browser_gate_is_provisioned_by_ci_and_deep_release() -> None:
    ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    deep = Path(".github/workflows/deep-release-validation.yml").read_text(encoding="utf-8")
    for workflow in (ci, deep):
        assert "actions/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e" in workflow
        assert "npm ci --ignore-scripts --no-audit --no-fund" in workflow
        assert "./node_modules/.bin/playwright install --with-deps chromium firefox webkit" in workflow
    assert "python -m scripts.ci.cli --gate browser" in ci
    assert ".venv/bin/python -m scripts.ci.cli --gate release" in deep
    assert "DATABASE_URL=$DATABASE_URL" in deep
    assert "npx playwright" not in ci + deep


def test_ci_rebuilds_default_production_bundle_after_e2e_override() -> None:
    ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    browser = ci.index("- name: Run canonical browser gate")
    rebuild = ci.index("- name: Rebuild canonical production frontend bundle")
    verify = ci.index("- name: Verify production bundle")
    upload = ci.index("- name: Upload frontend bundle")
    browser_evidence = ci.index("- name: Upload browser evidence")
    assert browser < rebuild < verify < upload < browser_evidence
    assert "env -u VITE_API_BASE npm run build" in ci
    assert 'grep -R -F -q "https://api.businessaios.ru" frontend/dist' in ci
    upload_block = ci[upload:browser_evidence]
    assert "if: success()" in upload_block and "if: always()" not in upload_block
    assert "if: always()" in ci[browser_evidence:]


def test_release_executor_sets_canonical_postgres_event_store_flag(monkeypatch) -> None:
    for key in ("BUSINESAIOS_ENABLE_POSTGRES_EVENT_STORE", "POSTGRES_EVENT_STORE_ENABLED"):
        monkeypatch.delenv(key, raising=False)
    with execution._step_environment(gate="release", step_name="browser-e2e"):
        assert os.environ["BUSINESAIOS_ENABLE_POSTGRES_EVENT_STORE"] == "1"
        assert "POSTGRES_EVENT_STORE_ENABLED" not in os.environ


def test_release_browser_runtime_requires_real_database_and_production_security(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BAIOS_CI_ACTIVE_GATE", "release")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        step_browser_e2e._runtime_env(sha="a" * 40, runtime_dir=str(tmp_path))

    monkeypatch.setenv("DATABASE_URL", "postgresql://proof@127.0.0.1:5432/businessaios")
    env, mode, storage = step_browser_e2e._runtime_env(sha="a" * 40, runtime_dir=str(tmp_path))
    assert (mode, storage) == ("production", "postgres")
    assert env["ENV"] == env["APP_ENV"] == "production"
    assert env["DATABASE_URL"].startswith("postgresql://")
    assert env["BUSINESAIOS_ENABLE_POSTGRES_EVENT_STORE"] == "1"
    assert "POSTGRES_EVENT_STORE_ENABLED" not in env
    assert env["API_CONTROL_PLANE_ALLOW_DEV_FALLBACKS"] == "0"
    assert env["BUSINESAIOS_API_KEY_STORE_BACKEND"] == "file"
    assert env["BUSINESAIOS_KEY_PROVIDER_BACKEND"] == "file"
    assert env["DECISION_SIGNING_SECRET"] != "dev-secret"
    assert len(base64.b64decode(env["BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64"])) == 32


def test_playwright_runtime_and_scenario_keep_security_and_mobile_contracts() -> None:
    config = Path("frontend/playwright.config.js").read_text(encoding="utf-8")
    scenario = Path("frontend/e2e/onboarding-workspace.spec.js").read_text(encoding="utf-8")
    assert 'const runtimeMode = process.env.BAIOS_E2E_RUNTIME_MODE || "development"' in config
    assert 'const production = runtimeMode === "production"' in config
    assert '"DATABASE_URL", "DECISION_SIGNING_SECRET", "API_CONTROL_PLANE_API_KEY_PEPPER"' in config
    assert '"BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64", "BUSINESAIOS_ENABLE_POSTGRES_EVENT_STORE"' in config
    assert 'APP_ENV: production ? "production" : "dev"' in config
    assert 'API_CONTROL_PLANE_ALLOW_DEV_FALLBACKS: production ? "0"' in config
    assert 'BUSINESAIOS_API_KEY_STORE_BACKEND: production ? "file"' in config
    assert 'trace: "off"' in config and 'trace: "retain-on-failure"' not in config
    assert "testInfo.project.name" in scenario and "hasNoHorizontalOverflow" in scenario
    assert "expect(ownerKey)" not in scenario and ".toContain(ownerKey)" not in scenario
    assert "indexedDB.databases()" in scenario and "context().cookies()" in scenario


def _signature(title: str = "onboarding creates a read-only OWNER workspace without persisting the API key") -> tuple[str, str, int, int]:
    return title, "onboarding-workspace.spec.js", 21, 1


def _embedded_test(project: str, title: str | None = None) -> dict:
    name, file, line, column = _signature(title or _signature()[0])
    return {
        "testId": f"browser-test-{project}", "title": name, "projectName": project,
        "location": {"file": file, "line": line, "column": column},
        "outcome": "expected", "ok": True,
        "results": [{"workerIndex": 0, "startTime": "2026-08-11T00:00:00.000Z"}],
    }


def _json_report(projects: tuple[str, ...], *, drift_project: str | None = None, skipped: int = 0) -> dict:
    title, file, line, column = _signature()
    tests = []
    for project in projects:
        project_title = f"{title} drift" if project == drift_project else title
        tests.append({
            "expectedStatus": "passed", "projectName": project, "status": "expected",
            "results": [{"status": "passed", "errors": []}], "_title": project_title,
        })
    specs = []
    for project, test in zip(projects, tests, strict=True):
        specs.append({
            "title": test.pop("_title"), "file": file, "line": line, "column": column, "ok": True,
            "tests": [test],
        })
    return {
        "config": {"projects": [{"name": name} for name in projects]},
        "suites": [{"specs": specs, "suites": []}],
        "stats": {"expected": len(projects), "unexpected": 0, "skipped": skipped, "flaky": 0},
    }


def _html_report(projects: tuple[str, ...], *, drift_project: str | None = None) -> str:
    title = _signature()[0]
    tests = [_embedded_test(project, f"{title} drift" if project == drift_project else title) for project in projects]
    report = {
        "projectNames": list(projects), "files": [{"tests": tests}],
        "stats": {"total": len(tests), "expected": len(tests), "unexpected": 0, "flaky": 0, "skipped": 0, "ok": True},
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("report.json", json.dumps(report))
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f'<!DOCTYPE html><html><head><title>Playwright Test Report</title></head><body><template id="playwrightReportBase64">data:application/zip;base64,{encoded}</template></body></html>'


def _write_outputs(browser: Path, *, projects: tuple[str, ...] | None = None, diagnostics: bool = True, skipped: int = 0, drift_project: str | None = None) -> None:
    names = projects or browser_project_names()
    browser.mkdir(parents=True, exist_ok=True)
    (browser / "playwright.json").write_text(json.dumps(_json_report(names, drift_project=drift_project, skipped=skipped)), encoding="utf-8")
    if not diagnostics:
        return
    testcases = "".join(f'<testcase name="browser-{index}"/>' for index, _ in enumerate(names, 1))
    (browser / "junit.xml").write_text(
        f'<testsuites tests="{len(names)}" failures="0" skipped="0" errors="0"><testsuite>{testcases}</testsuite></testsuites>',
        encoding="utf-8",
    )
    (browser / "html").mkdir(exist_ok=True)
    (browser / "html" / "index.html").write_text(_html_report(names, drift_project=drift_project), encoding="utf-8")


def test_browser_evidence_requires_every_project_and_identical_scenario() -> None:
    assert len(browser_project_names()) == 5


def test_browser_evidence_rejects_missing_project_or_cross_project_drift(tmp_path) -> None:
    browser = tmp_path / "browser"
    names = browser_project_names()
    _write_outputs(browser, projects=names[:-1])
    assert browser_artifact_snapshot(browser) is None
    _write_outputs(browser, projects=names, drift_project=names[-1])
    assert browser_artifact_snapshot(browser) is None


def _run_browser_step(monkeypatch, tmp_path, *, skipped: int = 0, diagnostics: bool = True):
    root = tmp_path / "repo"
    reports = root / "artifacts" / "ci"
    browser = reports / "browser-e2e"
    (root / "frontend").mkdir(parents=True)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    captured = {}
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "a" * 40)
    monkeypatch.setattr(step_browser_e2e, "repo_root", lambda: root)
    monkeypatch.setattr(step_browser_e2e, "reports_dir", lambda: reports)
    monkeypatch.setattr(step_browser_e2e.shutil, "which", lambda command: "/usr/bin/npm")
    monkeypatch.setattr(step_browser_e2e.tempfile, "mkdtemp", lambda **kwargs: str(runtime))

    def _run(*args, **kwargs):
        captured.update(kwargs)
        _write_outputs(browser, diagnostics=diagnostics, skipped=skipped)
        return CommandOutcome(0, "", "")

    monkeypatch.setattr(step_browser_e2e, "run_command", _run)
    result = step_browser_e2e.run()
    evidence = json.loads((reports / "browser-e2e-evidence.json").read_text(encoding="utf-8"))
    return result, evidence, captured


def test_browser_step_requires_complete_non_skipped_matrix(monkeypatch, tmp_path) -> None:
    result, evidence, captured = _run_browser_step(monkeypatch, tmp_path)
    assert result[0] is True and evidence["status"] == "PASS" and evidence["schema"] == BROWSER_EVIDENCE_SCHEMA
    assert evidence["exact_sha"] == "a" * 40
    assert evidence["runtime_mode"] == "development" and evidence["storage_backend"] == "isolated-local"
    assert [item["name"] for item in evidence["projects"]] == list(browser_project_names())
    assert all(item["tests"] == 1 for item in evidence["projects"])
    assert evidence["artifacts"]["junit"]["tests"] == len(browser_project_names())
    assert len(evidence["project_matrix"]["sha256"]) == 64
    assert captured["env"]["BAIOS_E2E_PYTHON"] == sys.executable


def test_browser_step_fails_closed_on_skipped_or_missing_diagnostics(monkeypatch, tmp_path) -> None:
    result, evidence, _ = _run_browser_step(monkeypatch, tmp_path, skipped=1)
    assert result[0] is False and evidence["status"] == "FAIL"

    second = tmp_path / "second"
    second.mkdir()
    result, evidence, _ = _run_browser_step(monkeypatch, second, diagnostics=False)
    assert result[0] is False and evidence["status"] == "FAIL"
