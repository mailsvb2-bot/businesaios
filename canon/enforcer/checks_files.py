from __future__ import annotations

from pathlib import Path

from canon.enforcer.rules import ALLOWED_EMPTY_FILES, REPO_ROOT, path_str


def check_empty_non_init_files(report, root: Path = REPO_ROOT) -> None:
    for path in root.rglob("*.py"):
        if path.name in ALLOWED_EMPTY_FILES:
            continue
        try:
            if path.stat().st_size == 0:
                report.add(severity="high", kind="empty-production-file", path=path_str(path), line=None, message="Empty Python file in production tree.", hint="Delete it, implement it, or replace with explicit Unsupported* error.")
        except OSError:
            report.add(severity="medium", kind="filesystem-error", path=path_str(path), line=None, message="Cannot stat file.")


def check_duplicate_config_roots(report, root: Path = REPO_ROOT) -> None:
    config_roots = [root / "config", root / "core/config", root / "runtime/config", root / "runtime" / "platform" / "config"]
    existing = [p for p in config_roots if p.exists()]
    seen: dict[str, str] = {}
    for base in existing:
        for path in base.rglob("*.py"):
            if path.name == "__init__.py":
                continue
            key = path.name
            rel = path_str(path)
            if key in seen:
                report.add(severity="medium", kind="config-duplication-risk", path=rel, line=None, message=f"Config filename duplicated across roots: {key}", hint=f"Also exists at {seen[key]}. Ensure ownership is explicit.")
            else:
                seen[key] = rel
