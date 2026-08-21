from __future__ import annotations

import base64
import io
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

from scripts.ci import browser_evidence, execution, step_browser_e2e
from scripts.ci.plan_registry import allowed_gates, plan_for_gate, requires_release_runtime_environment
from scripts.ci.step_registry import handler_for_step
from scripts.ci.subprocess_io import CommandOutcome

TITLE = "onboarding creates a read-only OWNER workspace without persisting the API key"
SPEC = "onboarding-workspace.spec.js"
STEP_SHA = "84ec18d31d1b1ecf429a3fb9d7a32887313f762529f41388dc0380043baa96c5"
STEP_SHAPE = json.loads(Path("tests/fixtures/playwright/onboarding-step-shape.json").read_text(encoding="utf-8"))
MATRIX = [
    {"name": "chromium", "device": "Desktop Chrome", "engine": "chromium", "surface": "desktop"},
    {"name": "firefox", "device": "Desktop Firefox", "engine": "firefox", "surface": "desktop"},
    {"name": "webkit", "device": "Desktop Safari", "engine": "webkit", "surface": "desktop"},
    {"name": "Mobile Chrome", "device": "Pixel 5", "engine": "chromium", "surface": "mobile"},
    {"name": "Mobile Safari", "device": "iPhone 12", "engine": "webkit", "surface": "mobile"},
]


def test_browser_contract_plans_provisioning_and_security_are_locked() -> None:
    contract = json.loads(Path(browser_evidence.BROWSER_PROJECT_MATRIX).read_text(encoding="utf-8"))
    assert contract == {
        "schema": browser_evidence.BROWSER_PROJECT_MATRIX_SCHEMA,
        "projects": MATRIX,
        "scenarios": [{"id": "onboarding_owner_workspace", "title": TITLE, "file": SPEC, "detail_step_sha256": STEP_SHA}],
    }
    assert browser_evidence.browser_project_names() == tuple(item["name"] for item in MATRIX)
    config = Path("frontend/playwright.config.js").read_text(encoding="utf-8")
    scenario = Path("frontend/e2e/onboarding-workspace.spec.js").read_text(encoding="utf-8")
    assert 'readFileSync(new URL("./e2e/project-matrix.json", import.meta.url)' in config
    assert "browserName: entry.engine" in config and 'trace: "off"' in config
    assert 'const runtimeMode = process.env.BAIOS_E2E_RUNTIME_MODE || "development"' in config
    assert 'const production = runtimeMode === "production"' in config
    assert '"DATABASE_URL", "DECISION_SIGNING_SECRET", "API_CONTROL_PLANE_API_KEY_PEPPER"' in config
    assert '"BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64", "BUSINESAIOS_ENABLE_POSTGRES_EVENT_STORE"' in config
    assert 'APP_ENV: production ? "production" : "dev"' in config
    assert 'ENV: production ? "production" : "dev"' in config
    assert 'API_CONTROL_PLANE_ALLOW_DEV_FALLBACKS: production ? "0"' in config
    assert 'BUSINESAIOS_API_KEY_STORE_BACKEND: production ? "file"' in config
    assert 'BUSINESAIOS_KEY_PROVIDER_BACKEND: production ? "file"' in config
    assert 'find((item) => item?.id === "onboarding_owner_workspace")' in scenario
    assert "test(canonicalScenario.title" in scenario and "testInfo.project.name" in scenario
    assert "hasNoHorizontalOverflow" in scenario and "indexedDB.databases()" in scenario and "context().cookies()" in scenario
    assert "expect(ownerKey)" not in scenario and ".toContain(ownerKey)" not in scenario
    assert "browser" in allowed_gates() and callable(handler_for_step("browser-e2e"))
    assert tuple(step.name for step in plan_for_gate("browser").steps) == (
        "assert-project-shape", "dependency-lock", "doctor-check", "browser-e2e",
    )
    assert "browser-e2e" not in tuple(step.name for step in plan_for_gate("full").steps)
    for gate in ("release", "pre-release"):
        names = tuple(step.name for step in plan_for_gate(gate).steps)
        assert names[names.index("production-boot") + 1:names.index("verify-release")] == ("browser-e2e",)
        assert requires_release_runtime_environment(gate=gate, step_name="browser-e2e")
    ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    deep = Path(".github/workflows/deep-release-validation.yml").read_text(encoding="utf-8")
    for workflow in (ci, deep):
        assert "npm ci --ignore-scripts --no-audit --no-fund" in workflow
        assert "./node_modules/.bin/playwright install --with-deps chromium firefox webkit" in workflow
        assert "npx playwright" not in workflow
    assert "python -m scripts.ci.cli --gate browser" in ci
    assert ".venv/bin/python -m scripts.ci.cli --gate release" in deep and "DATABASE_URL=$DATABASE_URL" in deep
    browser, rebuild, verify, upload, evidence = (
        ci.index(name) for name in (
            "- name: Run canonical browser gate", "- name: Rebuild canonical production frontend bundle",
            "- name: Verify production bundle", "- name: Upload frontend bundle", "- name: Upload browser evidence",
        )
    )
    assert browser < rebuild < verify < upload < evidence
    assert "env -u VITE_API_BASE npm run build" in ci and 'grep -R -F -q "https://api.businessaios.ru" frontend/dist' in ci
    assert "if: success()" in ci[upload:evidence] and "if: always()" not in ci[upload:evidence]
    assert "if: always()" in ci[evidence:ci.index("\n  complete-tree:", evidence)]


def test_release_browser_runtime_is_fail_closed(monkeypatch, tmp_path) -> None:
    for key in ("BUSINESAIOS_ENABLE_POSTGRES_EVENT_STORE", "POSTGRES_EVENT_STORE_ENABLED"):
        monkeypatch.delenv(key, raising=False)
    with execution._step_environment(gate="release", step_name="browser-e2e"):
        assert os.environ["BUSINESAIOS_ENABLE_POSTGRES_EVENT_STORE"] == "1"
        assert "POSTGRES_EVENT_STORE_ENABLED" not in os.environ
    monkeypatch.setenv("BAIOS_CI_ACTIVE_GATE", "release")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        step_browser_e2e._runtime_env(sha="a" * 40, runtime_dir=str(tmp_path))
    database_url = "postgresql://proof@127.0.0.1:5432/businessaios"
    monkeypatch.setenv("DATABASE_URL", database_url)
    env, mode, storage = step_browser_e2e._runtime_env(sha="a" * 40, runtime_dir=str(tmp_path))
    assert (mode, storage) == ("production", "postgres")
    assert env["DATABASE_URL"] == database_url
    assert env["ENV"] == env["APP_ENV"] == "production" and env["BUSINESAIOS_ENABLE_POSTGRES_EVENT_STORE"] == "1"
    assert env["API_CONTROL_PLANE_ALLOW_DEV_FALLBACKS"] == "0" and env["BUSINESAIOS_API_KEY_STORE_BACKEND"] == "file"
    assert env["BUSINESAIOS_KEY_PROVIDER_BACKEND"] == "file" and env["DECISION_SIGNING_SECRET"] != "dev-secret"
    assert len(base64.b64decode(env["BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64"])) == 32


@pytest.mark.parametrize("value, expected", [(0, 0), (31, 31), ("5", 5), (-0.5, -1), (1.25, -1), (True, -1), ("1.0", -1)])
def test_evidence_integer_types_are_strict(value, expected) -> None:
    assert browser_evidence._integer(value) == expected


@pytest.mark.parametrize("value, expected", [
    ("2026-08-11T10:48:09.726Z", True), ("2026-08-11T10:48:09+00:00", True),
    ({"not": "a timestamp"}, False), (123, False), ("not-a-timestamp", False),
    ("2026-08-11", False), ("2026-08-11T10:48:09", False),
])
def test_evidence_timestamp_types_are_strict(value, expected) -> None:
    assert browser_evidence._timestamp(value) is expected


def _json_result() -> dict:
    return {
        "workerIndex": 0, "parallelIndex": 0, "status": "passed", "duration": 1, "errors": [],
        "stdout": [], "stderr": [], "retry": 0, "startTime": "2026-08-11T10:48:09.726Z",
        "annotations": [], "attachments": [],
    }


def _embedded(
    project: str,
    title: str = TITLE,
    file: str = SPEC,
    attempts: int = 1,
    extra: dict | None = None,
) -> dict:
    result = {"attachments": [], "workerIndex": 0, "startTime": "2026-08-11T10:48:09.726Z"}
    result.update(extra or {})
    return {
        "testId": f"browser-{project}", "title": title, "projectName": project,
        "location": {"file": file, "line": 21, "column": 1}, "duration": 1,
        "annotations": [], "tags": [], "outcome": "expected", "path": [], "ok": True,
        "results": [dict(result) for _ in range(attempts)],
    }


def _fixture_step(node: dict, project: str) -> dict:
    slug = "-".join(project.lower().split())
    title = str(node["title"])
    title = title.replace("browser-e2e+{project}@example.test", f"browser-e2e+{slug}@example.test")
    title = title.replace("{project}", project)
    step = {
        "title": title, "startTime": "2026-08-11T10:48:09.726Z", "duration": 1,
        "steps": [_fixture_step(child, project) for child in node["children"]],
        "attachments": [], "count": 1, "skipped": False,
    }
    if node["location"]:
        file, line, column = node["location"]
        step.update(location={"file": file, "line": line, "column": column}, snippet="locked Playwright fixture")
    return step


def _detail_test(test: dict, *, truncated_steps: bool = False) -> dict:
    detail = dict(test)
    project = str(test["projectName"])
    steps = [_fixture_step(node, project) for node in STEP_SHAPE]
    detail["results"] = [{
        "duration": 1, "startTime": "2026-08-11T10:48:09.726Z", "retry": 0,
        "steps": steps[:1] if truncated_steps else steps,
        "errors": [], "status": "passed", "attachments": [], "annotations": [], "workerIndex": 0,
    }]
    return detail


def _outputs(
    browser: Path,
    *,
    projects: tuple[str, ...] | None = None,
    title: str = TITLE,
    file: str = SPEC,
    duplicate: bool = False,
    skipped: int = 0,
    attempts: int = 1,
    html_extra: dict | None = None,
    html_data: bool = True,
    truncated_steps: bool = False,
    json_errors: bool = False,
    html_errors: bool = False,
) -> None:
    names = projects or browser_evidence.browser_project_names()
    specs = [
        {"title": title, "file": file, "line": 21, "column": 1, "ok": True, "tests": [{
            "expectedStatus": "passed", "projectName": project, "status": "expected",
            "results": [dict(_json_result()) for _ in range(attempts)],
        }]}
        for project in names
    ]
    browser.mkdir(parents=True, exist_ok=True)
    (browser / "playwright.json").write_text(json.dumps({
        "config": {"projects": [{"name": name} for name in names]}, "errors": [{"message": "reporter failure"}] if json_errors else [],
        "suites": [{"specs": specs, "suites": []}],
        "stats": {"expected": len(names), "unexpected": 0, "skipped": skipped, "flaky": 0},
    }), encoding="utf-8")
    suites = "".join(
        f'<testsuite hostname="{project}" tests="1" failures="0" skipped="0" errors="0"><testcase name="{title}" classname="{file}"/></testsuite>'
        for project in names
    )
    (browser / "junit.xml").write_text(f'<testsuites tests="{len(names)}" failures="0" skipped="0" errors="0">{suites}</testsuites>', encoding="utf-8")
    tests = [_embedded(project, title, file, attempts, html_extra) for project in names]
    if duplicate:
        tests *= 2
    file_id = "canonical-browser-spec"
    stats = {"total": len(tests), "expected": len(tests), "unexpected": 0, "flaky": 0, "skipped": 0, "ok": True}
    report = {"projectNames": list(names), "errors": [{"message": "reporter failure"}] if html_errors else [], "files": [{"fileId": file_id, "fileName": file, "tests": tests, "stats": stats}], "stats": stats}
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as handle:
        handle.writestr("report.json", json.dumps(report))
        if html_data:
            handle.writestr(f"{file_id}.json", json.dumps({"fileId": file_id, "fileName": file, "tests": [_detail_test(test, truncated_steps=truncated_steps) for test in tests]}))
    html = base64.b64encode(archive.getvalue()).decode("ascii")
    (browser / "html").mkdir(exist_ok=True)
    (browser / "html" / "index.html").write_text(
        f'<!DOCTYPE html><html><head><title>Playwright Test Report</title></head><body><template id="playwrightReportBase64">data:application/zip;base64,{html}</template></body></html>', encoding="utf-8",
    )


def test_evidence_requires_exact_projects_canonical_identity_and_three_real_artifacts(tmp_path) -> None:
    browser, names = tmp_path / "browser", browser_evidence.browser_project_names()
    _outputs(browser)
    snapshot = browser_evidence.browser_artifact_snapshot(browser)
    assert snapshot and [item["name"] for item in snapshot["projects"]] == list(names)
    assert all(item["tests"] == 1 for item in snapshot["projects"]) and snapshot["artifacts"]["junit"]["tests"] == 5
    canonical = browser_evidence._matrix_snapshot()
    assert canonical and browser_evidence._scenario_matrix([(p, TITLE, SPEC) for p in names], names, canonical[1])
    assert browser_evidence._scenario_matrix([(p, "forged scenario", "forged.spec.js") for p in names], names, canonical[1]) is None
    for mutate in (
        lambda: _outputs(browser, projects=names[:-1]),
        lambda: _outputs(browser, title="forged scenario", file="forged.spec.js"),
        lambda: _outputs(browser, duplicate=True),
        lambda: _outputs(browser, attempts=2),
        lambda: _outputs(browser, html_extra={"status": "failed", "errors": [{"message": "forged"}]}),
        lambda: _outputs(browser, html_data=False),
        lambda: _outputs(browser, truncated_steps=True),
        lambda: _outputs(browser, json_errors=True),
        lambda: _outputs(browser, html_errors=True),
    ):
        mutate()
        assert browser_evidence.browser_artifact_snapshot(browser) is None
    _outputs(browser)
    payload = json.loads((browser / "playwright.json").read_text(encoding="utf-8"))
    result = payload["suites"][0]["specs"][0]["tests"][0]["results"][0]
    result["stdout"], result["attachments"] = [42], [False]
    (browser / "playwright.json").write_text(json.dumps(payload), encoding="utf-8")
    assert browser_evidence.browser_artifact_snapshot(browser) is None
    _outputs(browser)
    payload = json.loads((browser / "playwright.json").read_text(encoding="utf-8"))
    payload["suites"][0]["specs"][0]["tests"][0]["results"][0] = {"status": "passed", "errors": []}
    (browser / "playwright.json").write_text(json.dumps(payload), encoding="utf-8")
    assert browser_evidence.browser_artifact_snapshot(browser) is None
    _outputs(browser)
    payload = json.loads((browser / "playwright.json").read_text(encoding="utf-8"))
    payload["suites"] = []
    (browser / "playwright.json").write_text(json.dumps(payload), encoding="utf-8")
    assert browser_evidence.browser_artifact_snapshot(browser) is None
    _outputs(browser)
    (browser / "junit.xml").write_text("<root><testcase name='forged'/></root>", encoding="utf-8")
    assert browser_evidence.browser_artifact_snapshot(browser) is None


def _run_step(monkeypatch, tmp_path, *, skipped: int = 0, diagnostics: bool = True):
    root, runtime = tmp_path / "repo", tmp_path / "runtime"
    reports, browser = root / "artifacts" / "ci", root / "artifacts" / "ci" / "browser-e2e"
    (root / "frontend").mkdir(parents=True)
    runtime.mkdir()
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "a" * 40)
    monkeypatch.setattr(step_browser_e2e, "repo_root", lambda: root)
    monkeypatch.setattr(step_browser_e2e, "reports_dir", lambda: reports)
    monkeypatch.setattr(step_browser_e2e.shutil, "which", lambda command: "/usr/bin/npm")
    monkeypatch.setattr(step_browser_e2e.tempfile, "mkdtemp", lambda **kwargs: str(runtime))
    captured = {}

    def run(*args, **kwargs):
        captured.update(kwargs)
        if diagnostics:
            _outputs(browser, skipped=skipped)
        return CommandOutcome(0, "", "")

    monkeypatch.setattr(step_browser_e2e, "run_command", run)
    result = step_browser_e2e.run()
    return result, json.loads((reports / "browser-e2e-evidence.json").read_text(encoding="utf-8")), captured


def test_browser_step_requires_complete_matrix_and_fails_closed(monkeypatch, tmp_path) -> None:
    result, evidence, captured = _run_step(monkeypatch, tmp_path)
    assert result[0] and evidence["status"] == "PASS" and evidence["schema"] == browser_evidence.BROWSER_EVIDENCE_SCHEMA
    assert [item["name"] for item in evidence["projects"]] == list(browser_evidence.browser_project_names())
    assert captured["env"]["BAIOS_E2E_PYTHON"] == sys.executable
    assert evidence["exact_sha"] == "a" * 40 and evidence["runtime_mode"] == "development"
    assert evidence["storage_backend"] == "isolated-local" and all(item["tests"] == 1 for item in evidence["projects"])
    assert evidence["project_matrix"]["sha256"] == browser_evidence._matrix_snapshot()[2]
    for skipped, diagnostics in ((1, True), (0, False)):
        child = tmp_path / f"case-{skipped}-{diagnostics}"
        child.mkdir()
        failed, proof, _ = _run_step(monkeypatch, child, skipped=skipped, diagnostics=diagnostics)
        assert not failed[0] and proof["status"] == "FAIL"
