from __future__ import annotations

import json

from scripts.ci import execution
from scripts.ci.contracts import ExecutionPlan, ExecutionReport, ExecutionRequest, StepResult
from scripts.ci.reports import release_verdict


def _step(name: str, status: str = "passed") -> StepResult:
    return StepResult(name=name, status=status, message=name, duration_ms=1)


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


def test_release_verdict_requires_exact_sha_and_canonical_user_scenarios(monkeypatch) -> None:
    report = ExecutionReport(gate="acceptance", goal="test", steps=[_step("user-scenario-gate")])

    monkeypatch.delenv("BAIOS_CI_TARGET_SHA", raising=False)
    assert release_verdict(report)["status"] == "NOT_PROVEN"

    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "a" * 40)
    verdict = release_verdict(report)
    assert verdict["status"] == "PASS"
    assert verdict["exact_sha"] == "a" * 40
    assert verdict["canonical_user_scenarios"] == {
        "source_step": "user-scenario-gate",
        "status": "PASS",
    }


def test_release_verdict_is_not_proven_without_scenario_evidence(monkeypatch) -> None:
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "b" * 40)
    report = ExecutionReport(gate="fast", goal="test", steps=[_step("doctor-check")])

    verdict = release_verdict(report)

    assert verdict["status"] == "NOT_PROVEN"
    assert verdict["canonical_user_scenarios"]["status"] == "NOT_PROVEN"


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


def test_release_gate_enforces_not_proven_when_reports_are_disabled(monkeypatch) -> None:
    report = _release_without_steps(monkeypatch, emit_report=False)

    assert report.success is False
    assert [(step.name, step.status) for step in report.steps] == [("release-verdict", "failed")]
