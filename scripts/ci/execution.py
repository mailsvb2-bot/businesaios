from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from scripts.ci.contracts import ExecutionReport, ExecutionRequest, StepResult
from scripts.ci.coverage_report import write_coverage_stub_xml
from scripts.ci.goal import optimization_goal
from scripts.ci.junit_report import write_junit_xml
from scripts.ci.paths import execution_dir, junit_dir, reports_dir
from scripts.ci.plan_registry import (
    plan_for_gate,
    requires_release_dependency_lock_environment,
    requires_release_proof_environment,
)
from scripts.ci.reports import release_verdict, write_release_verdict, write_report
from scripts.ci.step_demo_e2e_smoke import cleanup_ci_runtime_state
from scripts.ci.step_registry import handler_for_step
from scripts.ci.summary import write_failure_summary
from scripts.ci.timing import measure_time

_PROOF_ENV_KEYS = (
    "POSTGRES_LIVE_PROOF_REQUIRED", "CONTAINER_RUNTIME_PROOF_REQUIRED", "CONTAINER_RUNTIME_EVIDENCE_REQUIRED",
    "REAL_RUNTIME_BOOT_EVIDENCE_REQUIRED", "PRODUCTION_BOOT_PROOF_REQUIRED", "STAGING_RUNTIME_PROOF_REQUIRED",
)
_RELEASE_RUNTIME_DEFAULTS = {
    "ENV": "production", "APP_ENV": "production", "APP_PROFILE": "api", "POSTGRES_RUNTIME_ENABLED": "1",
    "POSTGRES_EVENT_STORE_ENABLED": "1", "RUN_MIGRATIONS_BEFORE_START": "1", "POSTGRES_APPLY_MIGRATIONS": "1",
}
_RELEASE_RUNTIME_ENV_KEYS = (*_RELEASE_RUNTIME_DEFAULTS, "BAIOS_REQUIRE_TRANSITIVE_DEPENDENCY_LOCK")


@contextmanager
def _step_environment(*, gate: str, step_name: str) -> Iterator[None]:
    quality_key = "BAIOS_REQUIRE_QUALITY_TOOLS"
    previous = {key: os.environ.get(key) for key in (quality_key, *_PROOF_ENV_KEYS, *_RELEASE_RUNTIME_ENV_KEYS)}
    if requires_release_dependency_lock_environment(gate=gate, step_name=step_name):
        os.environ["BAIOS_REQUIRE_TRANSITIVE_DEPENDENCY_LOCK"] = "1"
    if step_name == "quality-check" and gate in {"release", "pre-release"}:
        os.environ[quality_key] = "release"
    if requires_release_proof_environment(gate=gate, step_name=step_name):
        for key in _PROOF_ENV_KEYS:
            os.environ[key] = "1"
        for key, value in _RELEASE_RUNTIME_DEFAULTS.items():
            os.environ.setdefault(key, value)
        os.environ[quality_key] = "release"
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _cleanup_runtime_state(report: ExecutionReport, name: str) -> None:
    with measure_time() as watch:
        removed = cleanup_ci_runtime_state()
    message = f"{name} removed {len(removed)} mutable runtime artifact(s)" if removed else f"{name} found no mutable DB artifacts"
    report.add(StepResult(name=name, status="passed", message=message, duration_ms=watch.duration_ms))


def execute(request: ExecutionRequest) -> ExecutionReport:
    plan = plan_for_gate(request.gate)
    report = ExecutionReport(gate=plan.gate, goal=optimization_goal())

    for step in plan.steps:
        if step.name == "lock-tests" and report.gate in {"fast", "full", "release", "pre-push", "pre-release", "business-critical"}:
            _cleanup_runtime_state(report, "pre-lock-runtime-artifact-cleanup")
        handler = handler_for_step(step.name)
        with measure_time() as watch, _step_environment(gate=plan.gate, step_name=step.name):
            ok, message = handler()

        status = "passed" if ok else ("skipped" if "skipped by contract" in message else "failed")
        result = StepResult(name=step.name, status=status, message=message, duration_ms=watch.duration_ms)
        report.add(result)
        if result.status == "failed":
            break
    if report.gate in {"fast", "full", "release", "pre-push", "pre-release"}:
        _cleanup_runtime_state(report, "final-runtime-artifact-cleanup")

    verdict_status = str(release_verdict(report)["status"])
    if request.gate == "release" and verdict_status != "PASS":
        report.add(StepResult(
            name="release-verdict", status="failed",
            message=f"release blocked by canonical verdict: {verdict_status}", duration_ms=0,
        ))

    if request.emit_report:
        write_release_verdict(reports_dir() / "release-verdict.json", report)
        write_report(reports_dir() / f"{request.gate}.report.json", report)
        if request.emit_junit:
            write_junit_xml(junit_dir() / f"{request.gate}.xml", report)
        if request.emit_coverage:
            write_coverage_stub_xml(execution_dir() / f"{request.gate}.xml", report)
        if not report.success:
            write_failure_summary(report)

    return report


__all__ = ["execute"]
