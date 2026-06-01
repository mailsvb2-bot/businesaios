from __future__ import annotations

from scripts.ci.doctor_checks import (
    find_actionlint_workflow_violations,
    find_domain_coupling,
    find_empty_ci_files,
    find_invalid_github_workflow_shapes,
    find_second_execution_imports,
    find_second_plan_order_definitions,
    find_unapproved_ci_shell_files,
    find_workflows_without_single_entrypoint,
)
from scripts.ci.paths import repo_root


def run_doctor() -> tuple[bool, str]:
    root = repo_root()

    empty_files = find_empty_ci_files(root)
    if empty_files:
        return False, f"empty ci files detected: {empty_files}"

    second_execution = find_second_execution_imports(root)
    if second_execution:
        return False, f"second execution path detected: {second_execution}"

    second_plan = find_second_plan_order_definitions(root)
    if second_plan:
        return False, f"second plan/order definition detected: {second_plan}"

    shell_drift = find_unapproved_ci_shell_files(root)
    if shell_drift:
        return False, f"unapproved ci shell files detected: {shell_drift}"

    workflow_drift = find_workflows_without_single_entrypoint(root)
    if workflow_drift:
        return False, f"workflow entrypoint drift detected: {workflow_drift}"

    workflow_shape_drift = find_invalid_github_workflow_shapes(root)
    if workflow_shape_drift:
        return False, f"github workflow yaml contract drift detected: {workflow_shape_drift}"

    workflow_lint = find_actionlint_workflow_violations(root)
    if workflow_lint:
        return False, f"github workflow actionlint failed: {workflow_lint}"

    domain_coupling = find_domain_coupling(root)
    if domain_coupling:
        return False, f"ci domain coupling detected: {domain_coupling}"

    return True, "doctor checks passed"


if __name__ == "__main__":
    ok, message = run_doctor()
    print(message)
    raise SystemExit(0 if ok else 1)
