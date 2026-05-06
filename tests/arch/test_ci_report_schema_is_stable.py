from __future__ import annotations

from scripts.ci.contracts import ExecutionReport, StepResult


def test_execution_report_schema_is_stable() -> None:
    report = ExecutionReport(
        gate="fast",
        goal="goal",
        steps=[
            StepResult(
                name="assert-project-shape",
                status="passed",
                message="ok",
                duration_ms=12,
            )
        ],
    )
    payload = report.to_dict()
    assert set(payload.keys()) == {"gate", "goal", "success", "steps"}
    assert set(payload["steps"][0].keys()) == {"name", "status", "message", "duration_ms"}
