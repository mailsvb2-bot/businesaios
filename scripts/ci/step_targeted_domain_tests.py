from __future__ import annotations

import os
import py_compile

from scripts.ci import targeted_domain_ci as targeted
from scripts.ci.pytest_tools import run_pytest_with_report


def run() -> tuple[bool, str]:
    base = os.environ.get("TARGETED_CI_BASE", "origin/main")
    changed = targeted.changed_files(base)
    changed_py = [path for path in changed if path.endswith(".py") and (targeted.ROOT / path).is_file()]
    print(f"[targeted-ci] changed={len(changed)} changed_py={len(changed_py)}")

    for path in changed_py:
        py_compile.compile(str(targeted.ROOT / path), doraise=True)

    domains = targeted.touched_domains(changed)
    tests = targeted.matching_tests(domains)
    print(f"[targeted-ci] domains={domains}")
    print(f"[targeted-ci] tests={len(tests)}")
    for test in tests[:200]:
        print(f"[targeted-ci] test={test}")

    if not tests:
        return True, "targeted-domain checks passed: changed Python compiled; no matching domain tests"

    ok, message = run_pytest_with_report(
        target_args=tests,
        mark_expression="not slow and not integration and not gate",
        junit_name="targeted-domain.xml",
        coverage_name="targeted-domain-coverage.json",
        timeout=900,
    )
    if not ok:
        return False, message
    return True, f"targeted-domain checks passed: {len(tests)} test file(s)"
