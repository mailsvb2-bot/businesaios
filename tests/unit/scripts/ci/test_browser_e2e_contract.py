from __future__ import annotations

import json

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


def _run_browser_step(monkeypatch, tmp_path, stats: dict, returncode: int = 0):
    root = tmp_path / "repo"
    reports = root / "artifacts" / "ci"
    browser = reports / "browser-e2e"
    (root / "frontend").mkdir(parents=True)
    browser.mkdir(parents=True)
    (browser / "playwright.json").write_text(json.dumps({"stats": stats}), encoding="utf-8")
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "a" * 40)
    monkeypatch.setattr(step_browser_e2e, "repo_root", lambda: root)
    monkeypatch.setattr(step_browser_e2e, "reports_dir", lambda: reports)
    monkeypatch.setattr(step_browser_e2e.shutil, "which", lambda command: "/usr/bin/npm")
    monkeypatch.setattr(step_browser_e2e.tempfile, "mkdtemp", lambda **kwargs: str(runtime))
    monkeypatch.setattr(step_browser_e2e, "run_command", lambda *args, **kwargs: CommandOutcome(returncode, "", ""))
    return step_browser_e2e.run(), json.loads((reports / "browser-e2e-evidence.json").read_text(encoding="utf-8"))


def test_browser_step_requires_real_non_skipped_playwright_test(monkeypatch, tmp_path) -> None:
    (result, evidence) = _run_browser_step(monkeypatch, tmp_path, {"expected": 1, "unexpected": 0, "skipped": 0})
    assert result[0] is True
    assert evidence["status"] == "PASS"
    assert evidence["exact_sha"] == "a" * 40


def test_browser_step_fails_closed_on_vacuous_or_skipped_report(monkeypatch, tmp_path) -> None:
    (result, evidence) = _run_browser_step(monkeypatch, tmp_path, {"expected": 0, "unexpected": 0, "skipped": 1})
    assert result[0] is False
    assert evidence["status"] == "FAIL"
