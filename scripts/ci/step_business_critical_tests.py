from __future__ import annotations

from scripts.ci.pytest_tools import run_pytest_with_report


def run() -> tuple[bool, str]:
    ok, message = run_pytest_with_report(
        target_args=["tests/business_critical"],
        mark_expression="not slow and not integration and not gate",
        junit_name="business-critical.xml",
        coverage_name="business-critical-coverage.xml",
        timeout=240,
    )
    if not ok:
        return False, message
    return True, "business critical invariant gate passed"


__all__ = ["run"]
