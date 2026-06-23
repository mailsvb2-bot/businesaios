from __future__ import annotations

from scripts.ci.config import project_shape_config
from scripts.ci.paths import repo_root
from scripts.ci.pytest_tools import run_pytest_with_report


_HEADLESS_SMOKE_FILES = (
    "tests/integration/headless/test_cli_run_smoke.py",
    "tests/integration/headless/test_cli_scenario_smoke.py",
    "tests/integration/headless/test_sdk_execute_smoke.py",
)


def _has_integration_target(targets: list[str]) -> bool:
    return "tests/integration" in targets or any(
        target.startswith("tests/integration/") for target in targets
    )


def _core_targets_without_headless_smoke(targets: list[str]) -> list[str]:
    core_targets = list(targets)
    if _has_integration_target(core_targets):
        for path in _HEADLESS_SMOKE_FILES:
            core_targets.append(f"--ignore={path}")
    return core_targets


def _run_pytest_gate(
    *,
    label: str,
    target_args: list[str],
    mark_expression: str,
    junit_name: str,
    coverage_name: str,
    timeout: int,
) -> tuple[bool, str]:
    ok, message = run_pytest_with_report(
        target_args=target_args,
        mark_expression=mark_expression,
        junit_name=junit_name,
        coverage_name=coverage_name,
        timeout=timeout,
    )
    if not ok:
        return False, f"{label} failed\n{message}"
    return True, f"{label} passed"


def run() -> tuple[bool, str]:
    cfg = project_shape_config(repo_root())
    targets = list(cfg.optional_integration_targets)
    if not targets:
        return True, "integration targets absent; skipped by contract"

    mark = cfg.integration_mark_expression

    ok, message = _run_pytest_gate(
        label="integration-core",
        target_args=_core_targets_without_headless_smoke(targets),
        mark_expression=mark,
        junit_name="integration-core.xml",
        coverage_name="integration-core-coverage.xml",
        timeout=240,
    )
    if not ok:
        return False, message

    if _has_integration_target(targets):
        for index, path in enumerate(_HEADLESS_SMOKE_FILES, start=1):
            ok, message = _run_pytest_gate(
                label=f"integration-headless-smoke-{index}",
                target_args=[path],
                mark_expression=mark,
                junit_name=f"integration-headless-smoke-{index}.xml",
                coverage_name=f"integration-headless-smoke-{index}-coverage.xml",
                timeout=240,
            )
            if not ok:
                return False, message

    return True, "integration test gate passed: core integration plus headless smoke shards"


__all__ = ["run"]
