from __future__ import annotations

from scripts.ci.config import project_shape_config
from scripts.ci.paths import repo_root
from scripts.ci.pytest_tools import run_pytest_with_report


def run() -> tuple[bool, str]:
    cfg = project_shape_config(repo_root())
    targets = list(cfg.optional_integration_targets)
    if not targets:
        return True, "integration targets absent; skipped by contract"
    ok, message = run_pytest_with_report(
        target_args=targets,
        mark_expression=cfg.integration_mark_expression,
        junit_name="integration.xml",
        coverage_name="integration-coverage.xml",
        timeout=240,
    )
    if not ok:
        return False, message
    return True, "integration test gate passed"


__all__ = ["run"]
