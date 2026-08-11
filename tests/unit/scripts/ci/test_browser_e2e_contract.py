from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts.ci import step_browser_e2e
from scripts.ci.plan_registry import allowed_gates, plan_for_gate
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
    assert "npx playwright" not in ci + deep


def test_browser_failure_evidence_cannot_capture_owner_key_network_payload() -> None:
    config = Path("frontend/playwright.config.js").read_text(encoding="utf-8")
    scenario = Path("frontend/e2e/onboarding-workspace.spec.js").read_text(encoding="utf-8")
    assert 'trace: "off"' in config
    assert "retain-on-failure" not in config.split('trace: "off"', 1)[0]
    assert "expect(ownerKey)" not in scenario
    assert ".toContain(ownerKey)" not in scenario
    assert "indexedDB.databases()" in scenario
    assert "context().cookies()" in scenario


def _run_browser_step(monkeypatch, tmp_path, stats: dict, returncode: int = 0, diagnostics: bool = True):
    root = tmp_path / "repo"
    reports = root / "artifacts" / "ci"
    browser = reports / "browser-e2e"
    (root / "frontend").mkdir(parents=True)
    browser.mkdir(parents=True)
    (browser / "playwright.json").write_text(json.dumps({"stats": stats}), encoding="utf-8")
    if diagnostics:
        (browser / "junit.xml").write_text("<testsuites/>", encoding="utf-8")
        (browser / "html").mkdir()
        (browser / "html" / "index.html").write_text("browser evidence", encoding="utf-8")
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
        browser.mkdir(parents=True, exist_ok=True)
        (browser / "playwright.json").write_text(json.dumps({"stats": stats}), encoding="utf-8")
        if diagnostics:
            (browser / "junit.xml").write_text("<testsuites/>", encoding="utf-8")
            (browser / "html").mkdir(exist_ok=True)
            (browser / "html" / "index.html").write_text("browser evidence", encoding="utf-8")
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
    assert captured["env"]["BAIOS_E2E_PYTHON"] == sys.executable


def test_browser_step_fails_closed_on_vacuous_or_skipped_report(monkeypatch, tmp_path) -> None:
    result, evidence, _ = _run_browser_step(monkeypatch, tmp_path, {"expected": 0, "unexpected": 0, "skipped": 1})
    assert result[0] is False
    assert evidence["status"] == "FAIL"


def test_browser_step_fails_closed_without_diagnostics(monkeypatch, tmp_path) -> None:
    result, evidence, _ = _run_browser_step(
        monkeypatch, tmp_path, {"expected": 1, "unexpected": 0, "skipped": 0}, diagnostics=False,
    )
    assert result[0] is False
    assert evidence["status"] == "FAIL"
