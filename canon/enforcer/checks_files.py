from __future__ import annotations

from pathlib import Path

from canon.enforcer.rules import ALLOWED_EMPTY_FILES, REPO_ROOT, iter_py_files, relative_path


def check_empty_non_init_files(
    report,
    root: Path = REPO_ROOT,
    *,
    source_files: tuple[Path, ...] | None = None,
) -> None:
    paths = source_files if source_files is not None else tuple(iter_py_files(root))
    for path in paths:
        if path.name in ALLOWED_EMPTY_FILES:
            continue
        rel = relative_path(root, path)
        try:
            if path.stat().st_size == 0:
                report.add(
                    severity="high",
                    kind="empty-production-file",
                    path=rel,
                    line=None,
                    message="Empty Python file in production tree.",
                    hint="Delete it, implement it, or replace with explicit Unsupported* error.",
                )
        except OSError:
            report.add(
                severity="high",
                kind="filesystem-error",
                path=rel,
                line=None,
                message="Cannot stat in-scope Python source.",
                hint="Restore repository readability before canon analysis continues.",
            )


def check_duplicate_config_roots(
    report,
    root: Path = REPO_ROOT,
    *,
    source_files: tuple[Path, ...] | None = None,
) -> None:
    paths = source_files if source_files is not None else tuple(iter_py_files(root))
    config_prefixes = ("config/", "core/config/", "runtime/config/", "runtime/platform/config/")
    seen: dict[str, str] = {}
    for path in paths:
        rel = relative_path(root, path)
        if path.name == "__init__.py" or not rel.startswith(config_prefixes):
            continue
        key = path.name
        if key in seen:
            report.add(
                severity="medium",
                kind="config-duplication-risk",
                path=rel,
                line=None,
                message=f"Config filename duplicated across roots: {key}",
                hint=f"Also exists at {seen[key]}. Ensure ownership is explicit.",
            )
        else:
            seen[key] = rel
