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
from scripts.ci.reports import write_report
from scripts.ci.step_demo_e2e_smoke import cleanup_ci_runtime_state
from scripts.ci.step_registry import handler_for_step
from scripts.ci.summary import write_failure_summary
from scripts.ci.timing import measure_time

_PROOF_ENV_KEYS = (
    "POSTGRES_LIVE_PROOF_REQUIRED",
    "CONTAINER_RUNTIME_PROOF_REQUIRED",
    "CONTAINER_RUNTIME_EVIDENCE_REQUIRED",
    "REAL_RUNTIME_BOOT_EVIDENCE_REQUIRED",
    "PRODUCTION_BOOT_PROOF_REQUIRED",
    "STAGING_RUNTIME_PROOF_REQUIRED",
)

_RELEASE_RUNTIME_ENV_KEYS = (
    "ENV",
    "APP_ENV",
    "APP_PROFILE",
    "POSTGRES_RUNTIME_ENABLED",
    "POSTGRES_EVENT_STORE_ENABLED",
    "RUN_MIGRATIONS_BEFORE_START",
    "POSTGRES_APPLY_MIGRATIONS",
    "BAIOS_REQUIRE_TRANSITIVE_DEPENDENCY_LOCK",
)


@contextmanager
def _step_environment(*, gate: str, step_name: str) -> Iterator[None]:
    quality_key = "BAIOS_REQUIRE_QUALITY_TOOLS"
    previous_quality = os.environ.get(quality_key)
    previous_proof = {key: os.environ.get(key) for key in _PROOF_ENV_KEYS}
    previous_release_runtime = {key: os.environ.get(key) for key in _RELEASE_RUNTIME_ENV_KEYS}
    if requires_release_dependency_lock_environment(gate=gate, step_name=step_name):
        os.environ["BAIOS_REQUIRE_TRANSITIVE_DEPENDENCY_LOCK"] = "1"
    if step_name == "quality-check" and gate in {"release", "pre-release"}:
        os.environ[quality_key] = "release"
    if requires_release_proof_environment(gate=gate, step_name=step_name):
        for key in _PROOF_ENV_KEYS:
            os.environ[key] = "1"
        os.environ.setdefault("ENV", "production")
        os.environ.setdefault("APP_ENV", "production")
        os.environ.setdefault("APP_PROFILE", "api")
        os.environ.setdefault("POSTGRES_RUNTIME_ENABLED", "1")
        os.environ.setdefault("POSTGRES_EVENT_STORE_ENABLED", "1")
        os.environ.setdefault("RUN_MIGRATIONS_BEFORE_START", "1")
        os.environ.setdefault("POSTGRES_APPLY_MIGRATIONS", "1")
        os.environ[quality_key] = "release"
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
        for key, value in previous_release_runtime.items():
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
