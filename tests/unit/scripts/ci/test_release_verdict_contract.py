from __future__ import annotations

import base64
import io
import json
import zipfile
from pathlib import Path

from scripts.ci import execution
from scripts.ci import reports as reports_module
from scripts.ci.browser_evidence import (
    BROWSER_EVIDENCE_NAME,
    BROWSER_EVIDENCE_SCHEMA,
    browser_artifact_snapshot,
    browser_project_names,
)
from scripts.ci.contracts import ExecutionPlan, ExecutionReport, ExecutionRequest, StepResult
from scripts.ci.plan_registry import plan_for_gate
from scripts.ci.reports import release_verdict
from scripts.ci.user_scenario_targets import USER_SCENARIO_EVIDENCE_NAME, USER_SCENARIO_RUST_FIXTURE, USER_SCENARIOS


def _step(name: str, status: str = "passed") -> StepResult:
    return StepResult(name=name, status=status, message=name, duration_ms=1)


def _report_for(gate: str) -> ExecutionReport:
    return ExecutionReport(gate=gate, goal="test", steps=[_step(step.name) for step in plan_for_gate(gate).steps])


def _write_payload(tmp_path, payload: dict) -> None:
    (tmp_path / USER_SCENARIO_EVIDENCE_NAME).write_text(json.dumps(payload), encoding="utf-8")


def _browser_test(project: str) -> dict:
    return {
        "testId": f"browser-test-{project}",
        "title": "onboarding creates a read-only OWNER workspace without persisting the API key",
        "projectName": project,
        "location": {"file": "onboarding-workspace.spec.js", "line": 21, "column": 1},
        "outcome": "expected", "ok": True,
        "results": [{"attachments": [], "workerIndex": 0, "startTime": "2026-08-11T00:00:00.000Z"}],
    }


def _browser_detail_test(test: dict) -> dict:
    detail = dict(test)
    detail["results"] = [{
        "duration": 1, "startTime": "2026-08-11T00:00:00.000Z", "retry": 0, "steps": [],
        "errors": [], "status": "passed", "attachments": [], "annotations": [], "workerIndex": 0,
    }]
    return detail


def _html_report(projects: tuple[str, ...]) -> str:
    tests = [_browser_test(project) for project in projects]
    file_id, file_name = "canonical-browser-spec", "onboarding-workspace.spec.js"
    stats = {"total": len(tests), "expected": len(tests), "unexpected": 0, "flaky": 0, "skipped": 0, "ok": True}
    report = {"projectNames": list(projects), "files": [{"fileId": file_id, "fileName": file_name, "tests": tests, "stats": stats}], "stats": stats}
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("report.json", json.dumps(report))
        archive.writestr(f"{file_id}.json", json.dumps({"fileId": file_id, "fileName": file_name, "tests": [_browser_detail_test(test) for test in tests]}))
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f'<!DOCTYPE html><html><head><title>Playwright Test Report</title></head><body><template id="playwrightReportBase64">data:application/zip;base64,{encoded}</template></body></html>'


def _json_report(projects: tuple[str, ...]) -> dict:
    tests = [
        {
            "expectedStatus": "passed", "projectName": project, "status": "expected",
            "results": [{
                "workerIndex": 0, "parallelIndex": 0, "status": "passed", "duration": 1,
                "errors": [], "stdout": [], "stderr": [], "retry": 0,
                "startTime": "2026-08-11T10:48:09.726Z", "annotations": [], "attachments": [],
            }],
        }
        for project in projects
    ]
    return {
        "config": {"projects": [{"name": name} for name in projects]},
        "suites": [{
            "specs": [{
                "title": "onboarding creates a read-only OWNER workspace without persisting the API key",
                "file": "onboarding-workspace.spec.js", "line": 21, "column": 1, "ok": True, "tests": tests,
            }],
            "suites": [],
        }],
        "stats": {"expected": len(projects), "unexpected": 0, "skipped": 0, "flaky": 0},
    }


def _junit_report(projects: tuple[str, ...]) -> str:
    title, file = "onboarding creates a read-only OWNER workspace without persisting the API key", "onboarding-workspace.spec.js"
    suites = "".join(
        f'<testsuite name="{file}" hostname="{project}" tests="1" failures="0" skipped="0" errors="0">'
        f'<testcase name="{title}" classname="{file}"/></testsuite>'
        for project in projects
    )
    return f'<testsuites tests="{len(projects)}" failures="0" skipped="0" errors="0">{suites}</testsuites>'


def _write_browser_evidence(
    tmp_path, sha: str, *, expected: int | None = None, runtime_mode: str = "production", storage_backend: str = "postgres",
) -> None:
    projects = browser_project_names() if expected != 0 else ()
    browser = tmp_path / "browser-e2e"
    browser.mkdir(parents=True, exist_ok=True)
    payload = _json_report(projects)
    (browser / "playwright.json").write_text(json.dumps(payload), encoding="utf-8")
    (browser / "junit.xml").write_text(_junit_report(projects), encoding="utf-8")
    (browser / "html").mkdir(exist_ok=True)
    (browser / "html" / "index.html").write_text(_html_report(projects), encoding="utf-8")
    snapshot = browser_artifact_snapshot(browser)
    (tmp_path / BROWSER_EVIDENCE_NAME).write_text(json.dumps({
        "schema": BROWSER_EVIDENCE_SCHEMA, "exact_sha": sha, "status": "PASS",
        "runtime_mode": runtime_mode, "storage_backend": storage_backend,
        "stats": snapshot["stats"] if snapshot else payload["stats"],
        "projects": snapshot["projects"] if snapshot else [],
        "project_matrix": snapshot["project_matrix"] if snapshot else {},
        "artifacts": snapshot["artifacts"] if snapshot else {},
    }), encoding="utf-8")


def _write_scenario_evidence(monkeypatch, tmp_path, sha: str) -> dict:
    monkeypatch.setattr(reports_module, "reports_dir", lambda: tmp_path)
    fixture = json.loads(Path(USER_SCENARIO_RUST_FIXTURE).read_text(encoding="utf-8"))
    cases = []
    for case in fixture["cases"]:
        expected = case["expected"]
        cases.append({
            "name": case["name"], "scenario": case["scenario"], "entrypoint": case["input"]["entrypoint"],
            "allowed": expected["allowed"], "reason": expected["reason"],
            "expected_allowed": expected["allowed"], "expected_reason": expected["reason"], "passed": True,
        })
    payload = {
        "schema": "businessaios_user_scenario_evidence.v1", "exact_sha": sha, "status": "PASS",
        "rust_matrix": {"status": "PASS", "version": fixture["version"], "total_cases": len(cases), "cases": cases},
        "scenarios": [
            {"id": scenario_id, "target": target, "status": "PASS", "junit": f"junit/user-scenario-{index}.xml"}
            for index, (scenario_id, target) in enumerate(USER_SCENARIOS, 1)
        ],
    }
    _write_payload(tmp_path, payload)
    _write_browser_evidence(tmp_path, sha)
    return payload


def _release_without_steps(monkeypatch, *, emit_report: bool, tmp_path=None) -> ExecutionReport:
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "d" * 40)
    monkeypatch.setattr(execution, "plan_for_gate", lambda gate: ExecutionPlan(gate=gate, steps=()))
    monkeypatch.setattr(execution, "cleanup_ci_runtime_state", lambda: [])
    monkeypatch.setattr(execution, "write_failure_summary", lambda report: None)
    if tmp_path is not None:
        monkeypatch.setattr(execution, "reports_dir", lambda: tmp_path)
    return execution.execute(
        ExecutionRequest(gate="release", emit_report=emit_report, emit_junit=False, emit_coverage=False)
    )


def test_release_verdict_requires_exact_sha_complete_plan_and_scenario_evidence(monkeypatch, tmp_path) -> None:
    report = _report_for("release")
    _write_scenario_evidence(monkeypatch, tmp_path, "a" * 40)

    monkeypatch.delenv("BAIOS_CI_TARGET_SHA", raising=False)
    assert release_verdict(report)["status"] == "NOT_PROVEN"

    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "a" * 40)
    verdict = release_verdict(report)
    assert verdict["status"] == "PASS"
    assert verdict["exact_sha"] == "a" * 40
    assert verdict["canonical_user_scenarios"]["status"] == "PASS"
    assert verdict["browser_e2e"]["status"] == "PASS"
    assert verdict["browser_e2e"]["runtime_mode"] == "production"
    assert verdict["browser_e2e"]["storage_backend"] == "postgres"
    assert [item["name"] for item in verdict["browser_e2e"]["projects"]] == list(browser_project_names())
    assert [item["id"] for item in verdict["canonical_user_scenarios"]["scenarios"]] == [
        scenario_id for scenario_id, _ in USER_SCENARIOS
    ]


def test_non_release_gate_cannot_publish_pass_verdict(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "b" * 40)
    _write_scenario_evidence(monkeypatch, tmp_path, "b" * 40)
    verdict = release_verdict(_report_for("full"))
    assert verdict["status"] == "NOT_PROVEN"
    assert verdict["canonical_user_scenarios"]["status"] == "PASS"
    assert verdict["browser_e2e"]["status"] == "NOT_PROVEN"


def test_release_verdict_is_not_proven_when_required_release_evidence_is_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "c" * 40)
    _write_scenario_evidence(monkeypatch, tmp_path, "c" * 40)
    report = _report_for("release")
    report.steps = [step for step in report.steps if step.name != "build-artifact"]
    assert release_verdict(report)["status"] == "NOT_PROVEN"


def test_release_verdict_requires_exact_browser_evidence(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "c" * 40)
    _write_scenario_evidence(monkeypatch, tmp_path, "c" * 40)
    (tmp_path / BROWSER_EVIDENCE_NAME).unlink()
    assert release_verdict(_report_for("release"))["status"] == "NOT_PROVEN"
    _write_browser_evidence(tmp_path, "e" * 40)
    assert release_verdict(_report_for("release"))["status"] == "NOT_PROVEN"


def test_release_verdict_rejects_development_browser_evidence(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "c" * 40)
    _write_scenario_evidence(monkeypatch, tmp_path, "c" * 40)
    _write_browser_evidence(tmp_path, "c" * 40, runtime_mode="development", storage_backend="isolated-local")
    verdict = release_verdict(_report_for("release"))
    assert verdict["status"] == "FAIL"
    assert verdict["browser_e2e"]["evidence_status"] == "FAIL"


def test_release_verdict_rejects_vacuous_browser_evidence(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "c" * 40)
    _write_scenario_evidence(monkeypatch, tmp_path, "c" * 40)
    _write_browser_evidence(tmp_path, "c" * 40, expected=0)
    assert release_verdict(_report_for("release"))["status"] == "FAIL"


def test_release_verdict_rejects_tampered_browser_diagnostics(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "c" * 40)
    _write_scenario_evidence(monkeypatch, tmp_path, "c" * 40)
    (tmp_path / "browser-e2e" / "junit.xml").write_text("<testsuites/>", encoding="utf-8")
    assert release_verdict(_report_for("release"))["status"] == "FAIL"


def test_release_verdict_rejects_legacy_single_browser_evidence(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "c" * 40)
    _write_scenario_evidence(monkeypatch, tmp_path, "c" * 40)
    evidence_path = tmp_path / BROWSER_EVIDENCE_NAME
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence.update(schema="businessaios_browser_e2e.v1", projects=[], project="chromium")
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    assert release_verdict(_report_for("release"))["status"] == "FAIL"


def test_release_verdict_rejects_stale_scenario_evidence(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "c" * 40)
    _write_scenario_evidence(monkeypatch, tmp_path, "e" * 40)
    _write_browser_evidence(tmp_path, "c" * 40)
    verdict = release_verdict(_report_for("release"))
    assert verdict["status"] == "NOT_PROVEN"
    assert verdict["canonical_user_scenarios"]["evidence_status"] == "NOT_PROVEN"


def test_release_verdict_recomputes_nested_scenario_evidence(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "c" * 40)
    payload = _write_scenario_evidence(monkeypatch, tmp_path, "c" * 40)
    payload["rust_matrix"]["status"] = "FAIL"
    payload["scenarios"] = []
    _write_payload(tmp_path, payload)
    verdict = release_verdict(_report_for("release"))
    assert verdict["status"] == "FAIL"
    assert verdict["canonical_user_scenarios"]["evidence_status"] == "FAIL"


def test_release_verdict_rejects_forged_rust_case_fields(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "c" * 40)
    payload = _write_scenario_evidence(monkeypatch, tmp_path, "c" * 40)
    payload["rust_matrix"]["cases"][0]["reason"] = "forged"
    payload["rust_matrix"]["cases"][0]["allowed"] = False
    _write_payload(tmp_path, payload)
    assert release_verdict(_report_for("release"))["status"] == "FAIL"


def test_release_verdict_rejects_truncated_python_evidence(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "c" * 40)
    payload = _write_scenario_evidence(monkeypatch, tmp_path, "c" * 40)
    payload["scenarios"][0]["target"] = "tests/forged.py"
    payload["scenarios"][0]["junit"] = "junit/forged.xml"
    _write_payload(tmp_path, payload)
    assert release_verdict(_report_for("release"))["status"] == "FAIL"


def test_release_verdict_treats_invalid_utf8_evidence_as_corrupt(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "c" * 40)
    monkeypatch.setattr(reports_module, "reports_dir", lambda: tmp_path)
    (tmp_path / USER_SCENARIO_EVIDENCE_NAME).write_bytes(b"\xff\xfe\xfa")
    verdict = release_verdict(_report_for("release"))
    assert verdict["status"] == "FAIL"
    assert verdict["canonical_user_scenarios"]["status"] == "FAIL"


def test_release_verdict_is_not_proven_without_scenario_evidence(monkeypatch) -> None:
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "b" * 40)
    report = ExecutionReport(gate="fast", goal="test", steps=[_step("doctor-check")])
    verdict = release_verdict(report)
    assert verdict["status"] == "NOT_PROVEN"
    assert verdict["canonical_user_scenarios"]["status"] == "NOT_PROVEN"
    assert verdict["browser_e2e"]["status"] == "NOT_PROVEN"


def test_release_verdict_fails_when_a_required_step_fails(monkeypatch) -> None:
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "c" * 40)
    report = ExecutionReport(
        gate="acceptance", goal="test",
        steps=[_step("user-scenario-gate"), _step("business-critical-tests", "failed")],
    )
    assert release_verdict(report)["status"] == "FAIL"


def test_release_gate_turns_not_proven_verdict_into_failure(monkeypatch, tmp_path) -> None:
    report = _release_without_steps(monkeypatch, emit_report=True, tmp_path=tmp_path)
    assert report.success is False
    assert report.steps[-1].name == "release-verdict"
    assert report.steps[-1].status == "failed"
    verdict = json.loads((tmp_path / "release-verdict.json").read_text(encoding="utf-8"))
    assert verdict["status"] == "FAIL"
    assert verdict["canonical_user_scenarios"]["status"] == "NOT_PROVEN"
    assert verdict["browser_e2e"]["status"] == "NOT_PROVEN"


def test_release_gate_enforces_not_proven_when_reports_are_disabled(monkeypatch) -> None:
    report = _release_without_steps(monkeypatch, emit_report=False)
    assert report.success is False
    assert report.steps[-2].name == "final-runtime-artifact-cleanup"
    assert (report.steps[-1].name, report.steps[-1].status) == ("release-verdict", "failed")
