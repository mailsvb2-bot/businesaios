from __future__ import annotations

import os
from contextlib import contextmanager
from collections.abc import Iterator

from scripts.ci.contracts import ExecutionReport, ExecutionRequest, StepResult
from scripts.ci.coverage_report import write_coverage_stub_xml
from scripts.ci.goal import optimization_goal
from scripts.ci.junit_report import write_junit_xml
from scripts.ci.paths import coverage_dir, execution_dir, junit_dir, reports_dir
from scripts.ci.plan_registry import plan_for_gate
from scripts.ci.reports import write_report
from scripts.ci.step_demo_e2e_smoke import cleanup_ci_runtime_state
from scripts.ci.step_registry import handler_for_step
from scripts.ci.summary import write_failure_summary
from scripts.ci.timing import measure_time


_PRODUCTION_PROOF_ENV_KEYS = (
    "POSTGRES_LIVE_PROOF_REQUIRED",
    "CONTAINER_RUNTIME_PROOF_REQUIRED",
    "CONTAINER_RUNTIME_EVIDENCE_REQUIRED",
    "REAL_RUNTIME_BOOT_EVIDENCE_REQUIRED",
    "PRODUCTION_BOOT_PROOF_REQUIRED",
)


@contextmanager
def _step_environment(*, gate: str, step_name: str) -> Iterator[None]:
    quality_key = "BAIOS_REQUIRE_QUALITY_TOOLS"
    previous_quality = os.environ.get(quality_key)
    previous_proof = {key: os.environ.get(key) for key in _PRODUCTION_PROOF_ENV_KEYS}
    release_gate = gate in {"release", "pre-release"}
    if step_name == "quality-check" and release_gate:
        os.environ[quality_key] = "release"
    if release_gate and step_name in {"postgres-live", "container-runtime", "production-boot"}:
        for key in _PRODUCTION_PROOF_ENV_KEYS:
            os.environ[key] = "1"
    try:
        yield
    finally:
        if previous_quality is None:
            os.environ.pop(quality_key, None)
        else:
            os.environ[quality_key] = previous_quality
        for key, value in previous_proof.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _mutable_cleanup_result(*, name: str, duration_ms: int, removed: list[str]) -> StepResult:
    message = (
        f"{name} removed {len(removed)} mutable runtime artifact(s)"
        if removed
        else f"{name} found no mutable DB artifacts"
    )
    return StepResult(name=name, status="passed", message=message, duration_ms=duration_ms)


def _cleanup_before_lock_tests(report: ExecutionReport, *, next_step_name: str) -> None:
    if next_step_name != "lock-tests":
        return
    if report.gate not in {"fast", "full", "release", "pre-push", "pre-release", "business-critical"}:
        return
    with measure_time() as watch:
        removed = cleanup_ci_runtime_state()
    report.add(
        _mutable_cleanup_result(
            name="pre-lock-runtime-artifact-cleanup",
            duration_ms=watch.duration_ms,
            removed=removed,
        )
    )


def _cleanup_after_gate(report: ExecutionReport) -> None:
    if report.gate not in {"fast", "full", "release", "pre-push", "pre-release"}:
        return
    with measure_time() as watch:
        removed = cleanup_ci_runtime_state()
    report.add(
        _mutable_cleanup_result(
            name="final-runtime-artifact-cleanup",
            duration_ms=watch.duration_ms,
            removed=removed,
        )
    )


def execute(request: ExecutionRequest) -> ExecutionReport:
    plan = plan_for_gate(request.gate)
    report = ExecutionReport(gate=plan.gate, goal=optimization_goal())

    for step in plan.steps:
        _cleanup_before_lock_tests(report, next_step_name=step.name)
        handler = handler_for_step(step.name)
        with measure_time() as watch:
            with _step_environment(gate=plan.gate, step_name=step.name):
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
    _cleanup_after_gate(report)

    if request.emit_report:
        write_report(reports_dir() / f"{request.gate}.report.json", report)
        if request.emit_junit:
            write_junit_xml(junit_dir() / f"{request.gate}.xml", report)
        if request.emit_coverage:
            write_coverage_stub_xml(execution_dir() / f"{request.gate}.xml", report)
        if not report.success:
            write_failure_summary(report)

    return report


__all__ = ["execute"]
