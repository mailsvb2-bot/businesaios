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
from scripts.ci.browser_evidence import browser_artifact_snapshot
from scripts.ci.plan_registry import allowed_gates, plan_for_gate, requires_release_runtime_environment
from scripts.ci.step_registry import handler_for_step
from scripts.ci.subprocess_io import CommandOutcome


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
        assert "./node_modules/.bin/playwright install --with-deps chromium" in workflow
    assert "python -m scripts.ci.cli --gate browser" in ci
    assert ".venv/bin/python -m scripts.ci.cli --gate release" in deep
    assert "DATABASE_URL=$DATABASE_URL" in deep
    assert "npx playwright" not in ci + deep


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


def test_playwright_runtime_switches_mode_without_production_fallbacks() -> None:
    config = Path("frontend/playwright.config.js").read_text(encoding="utf-8")
    assert 'const runtimeMode = process.env.BAIOS_E2E_RUNTIME_MODE || "development"' in config
    assert 'const production = runtimeMode === "production"' in config
    assert '"DATABASE_URL", "DECISION_SIGNING_SECRET", "API_CONTROL_PLANE_API_KEY_PEPPER"' in config
    assert '"BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64", "BUSINESAIOS_ENABLE_POSTGRES_EVENT_STORE"' in config
    assert 'APP_ENV: production ? "production" : "dev"' in config
    assert 'API_CONTROL_PLANE_ALLOW_DEV_FALLBACKS: production ? "0"' in config
    assert 'BUSINESAIOS_API_KEY_STORE_BACKEND: production ? "file"' in config


def test_browser_failure_evidence_cannot_capture_owner_key_network_payload() -> None:
    config = Path("frontend/playwright.config.js").read_text(encoding="utf-8")
    scenario = Path("frontend/e2e/onboarding-workspace.spec.js").read_text(encoding="utf-8")
    assert 'trace: "off"' in config
    assert 'trace: "retain-on-failure"' not in config
    assert "expect(ownerKey)" not in scenario
    assert ".toContain(ownerKey)" not in scenario
    assert "indexedDB.databases()" in scenario
    assert "context().cookies()" in scenario


def _embedded_test(index: int) -> dict:
    return {
        "testId": f"browser-test-{index}",
        "title": f"browser-{index}",
        "projectName": "chromium",
        "location": {"file": "onboarding-workspace.spec.js", "line": index + 1, "column": 1},
        "outcome": "expected",
        "ok": True,
        "results": [{"workerIndex": 0}],
    }


def _html_report(expected: int, *, embedded_count: int | None = None, empty_records: bool = False) -> str:
    count = expected if embedded_count is None else embedded_count
    tests = [{} for _ in range(count)] if empty_records else [_embedded_test(index) for index in range(count)]
    report = {
        "projectNames": ["chromium"], "files": [{"tests": tests}],
        "stats": {"total": expected, "expected": expected, "unexpected": 0, "flaky": 0, "skipped": 0, "ok": True},
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("report.json", json.dumps(report))
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f'<!DOCTYPE html><html><head><title>Playwright Test Report</title></head><body><template id="playwrightReportBase64">data:application/zip;base64,{encoded}</template></body></html>'


def _write_outputs(browser: Path, stats: dict, *, diagnostics: bool) -> None:
    browser.mkdir(parents=True, exist_ok=True)
    (browser / "playwright.json").write_text(json.dumps({"stats": stats}), encoding="utf-8")
    if not diagnostics:
        return
    expected = int(stats.get("expected", 0))
    testcases = "".join(f'<testcase name="browser-{index}"/>' for index in range(expected))
    (browser / "junit.xml").write_text(
        f'<testsuites tests="{expected}" failures="0" skipped="0" errors="0"><testsuite>{testcases}</testsuite></testsuites>',
        encoding="utf-8",
    )
    (browser / "html").mkdir(exist_ok=True)
    (browser / "html" / "index.html").write_text(_html_report(expected), encoding="utf-8")


def test_browser_evidence_rejects_mismatched_or_empty_embedded_test_records(tmp_path) -> None:
    browser = tmp_path / "browser"
    stats = {"expected": 2, "unexpected": 0, "skipped": 0}
    _write_outputs(browser, stats, diagnostics=True)
    html_path = browser / "html" / "index.html"
    html_path.write_text(_html_report(2, embedded_count=1), encoding="utf-8")
    assert browser_artifact_snapshot(browser) is None
    html_path.write_text(_html_report(2, empty_records=True), encoding="utf-8")
    assert browser_artifact_snapshot(browser) is None


def _run_browser_step(monkeypatch, tmp_path, stats: dict, returncode: int = 0, diagnostics: bool = True):
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
        _write_outputs(browser, stats, diagnostics=diagnostics)
        return CommandOutcome(returncode, "", "")

    monkeypatch.setattr(step_browser_e2e, "run_command", _run)
    result = step_browser_e2e.run()
    evidence = json.loads((reports / "browser-e2e-evidence.json").read_text(encoding="utf-8"))
    return result, evidence, captured


def test_browser_step_requires_real_non_skipped_playwright_test(monkeypatch, tmp_path) -> None:
    result, evidence, captured = _run_browser_step(monkeypatch, tmp_path, {"expected": 1, "unexpected": 0, "skipped": 0})
    assert result[0] is True
    assert evidence["status"] == "PASS"
    assert evidence["exact_sha"] == "a" * 40
    assert evidence["runtime_mode"] == "development"
    assert evidence["storage_backend"] == "isolated-local"
    assert evidence["artifacts"]["junit"]["tests"] == 1
    assert len(evidence["artifacts"]["html"]["sha256"]) == 64
    assert captured["env"]["BAIOS_E2E_PYTHON"] == sys.executable


def test_browser_step_fails_closed_on_vacuous_or_skipped_report(monkeypatch, tmp_path) -> None:
    result, evidence, _ = _run_browser_step(monkeypatch, tmp_path, {"expected": 0, "unexpected": 0, "skipped": 1})
    assert result[0] is False
    assert evidence["status"] == "FAIL"


def test_browser_step_fails_closed_without_parseable_diagnostics(monkeypatch, tmp_path) -> None:
    result, evidence, _ = _run_browser_step(
        monkeypatch, tmp_path, {"expected": 1, "unexpected": 0, "skipped": 0}, diagnostics=False,
    )
    assert result[0] is False
    assert evidence["status"] == "FAIL"
