from __future__ import annotations

from scripts.ci.contracts import ExecutionReport, ExecutionRequest, StepResult
from scripts.ci.coverage_report import write_coverage_stub_xml
from scripts.ci.goal import optimization_goal
from scripts.ci.junit_report import write_junit_xml
from scripts.ci.paths import coverage_dir, execution_dir, junit_dir, reports_dir
from scripts.ci.plan_registry import plan_for_gate
from scripts.ci.reports import write_report
from scripts.ci.step_registry import handler_for_step
from scripts.ci.summary import write_failure_summary
from scripts.ci.timing import measure_time


def execute(request: ExecutionRequest) -> ExecutionReport:
    plan = plan_for_gate(request.gate)
    report = ExecutionReport(gate=plan.gate, goal=optimization_goal())

    for step in plan.steps:
        handler = handler_for_step(step.name)
        with measure_time() as watch:
            ok, message = handler()

        status = "passed" if ok else ("skipped" if "skipped by contract" in message else "failed")
        result = StepResult(
            name=step.name,
            status=status,
            message=message,
            duration_ms=watch.duration_ms,
        )
        report.add(result)

        if result.status == "failed":
            break

    if request.emit_report:
        write_report(reports_dir() / f"{request.gate}.report.json", report)
        if request.emit_junit:
            write_junit_xml(junit_dir() / f"{request.gate}.xml", report)
        if request.emit_coverage:
            write_coverage_stub_xml(execution_dir() / f"{request.gate}.xml", report)
        if not report.success:
            write_failure_summary(report)

    return report
