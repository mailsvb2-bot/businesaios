from __future__ import annotations

from pathlib import Path

from canon.enforcer.checks_ast import check_ast_semantics
from canon.enforcer.checks_docs import check_readme_and_contributing, check_super_canon_world_model_contract
from canon.enforcer.checks_files import check_duplicate_config_roots, check_empty_non_init_files
from canon.enforcer.checks_invariants import (
    check_required_invariants,
    check_second_brain_file_hints,
    check_synonym_namespaces,
)
from canon.enforcer.reporting import EnforcerReport, Violation
from canon.enforcer.rules import REPO_ROOT


def run_enforcer(root: str | Path = REPO_ROOT) -> EnforcerReport:
    root = Path(root)
    report = EnforcerReport(ok=True)
    check_required_invariants(report, root)
    check_second_brain_file_hints(report, root)
    check_synonym_namespaces(report, root)
    check_empty_non_init_files(report, root)
    check_duplicate_config_roots(report, root)
    check_readme_and_contributing(report, root)
    check_super_canon_world_model_contract(report, root)
    check_ast_semantics(report, root)
    report.recompute_ok()
    return report


def main() -> int:
    report = run_enforcer(REPO_ROOT)
    print(report.render_text())
    print("\nJSON REPORT:")
    print(report.to_json())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
