from __future__ import annotations

import sys
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
from canon.enforcer.rules import REPO_ROOT, iter_py_files
from canon.repository_sources import RepositorySourceError, validate_repository_root

__all__ = ["EnforcerReport", "Violation", "main", "run_enforcer"]


def _write_text_stdout(text: str) -> None:
    sys.stdout.write(str(text) + "\n")


def run_enforcer(root: str | Path = REPO_ROOT) -> EnforcerReport:
    report = EnforcerReport(ok=True)
    try:
        repository_root = validate_repository_root(root)
    except ValueError as exc:
        report.add(
            severity="critical",
            kind="invalid-repository-root",
            path=str(root),
            line=None,
            message=str(exc),
            hint="Provide an existing repository directory.",
        )
        report.recompute_ok()
        return report

    check_required_invariants(report, repository_root)
    check_readme_and_contributing(report, repository_root)
    check_super_canon_world_model_contract(report, repository_root)

    try:
        source_files = tuple(iter_py_files(repository_root))
    except RepositorySourceError as exc:
        report.add(
            severity="critical",
            kind="repository-source-inventory-error",
            path=".",
            line=None,
            message=str(exc),
            hint="Restore repository readability before canon analysis continues.",
        )
    else:
        check_second_brain_file_hints(report, repository_root, source_files=source_files)
        check_synonym_namespaces(report, repository_root, source_files=source_files)
        check_empty_non_init_files(report, repository_root, source_files=source_files)
        check_duplicate_config_roots(report, repository_root, source_files=source_files)
        check_ast_semantics(report, repository_root, source_files=source_files)

    report.recompute_ok()
    return report


def main() -> int:
    report = run_enforcer(REPO_ROOT)
    _write_text_stdout(report.render_text())
    _write_text_stdout("\nJSON REPORT:")
    _write_text_stdout(report.to_json())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
