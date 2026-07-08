from __future__ import annotations

from scripts.ci.paths import repo_root
from scripts.ci.pytest_tools import run_pytest_with_report
from scripts.ci.user_scenario_targets import USER_SCENARIO_MARK_EXPRESSION, USER_SCENARIO_TARGETS


def _missing_targets() -> tuple[str, ...]:
    root = repo_root()
    missing = [target for target in USER_SCENARIO_TARGETS if not (root / target).exists()]
    return tuple(missing)


def _run_user_scenario(index: int, target: str) -> tuple[bool, str]:
    ok, message = run_pytest_with_report(
        target_args=[target],
        mark_expression=USER_SCENARIO_MARK_EXPRESSION,
        junit_name=f"user-scenario-{index}.xml",
        coverage_name=f"user-scenario-{index}-coverage.xml",
        timeout=240,
    )
    if not ok:
        return False, f"user scenario failed: {target}\n{message}"
    return True, f"user scenario passed: {target}"


def run() -> tuple[bool, str]:
    missing = _missing_targets()
    if missing:
        return False, "user scenario target(s) missing: " + ", ".join(missing)

    passed: list[str] = []
    for index, target in enumerate(USER_SCENARIO_TARGETS, start=1):
        ok, message = _run_user_scenario(index, target)
        if not ok:
            return False, message
        passed.append(target)

    return True, f"user scenario acceptance gate passed: {len(passed)} scenario shard(s)"


__all__ = ["run"]
