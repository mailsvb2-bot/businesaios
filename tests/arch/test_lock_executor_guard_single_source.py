from __future__ import annotations

from tests._infra.repo_scan import format_hits, scan_lines


def test_lock_assert_called_from_executor_single_source() -> None:
    """Guard must be defined in exactly one canonical support module."""

    hits = scan_lines(
        patterns={
            "DEF_ASSERT_CALLED_FROM_EXECUTOR": r"^\s*def\s+assert_called_from_executor\s*\(",
        },
        include_glob="**/*.py",
        allowlist_relpaths=("runtime/execution/context.py",),
    )
    assert hits == [], "Executor guard must be single-source-of-truth.\n" + format_hits(hits)


def test_lock_no_contextvar_dupes_for_executor_marker() -> None:
    """Prevent alternative executor-context markers from appearing outside canonical support."""

    hits = scan_lines(
        patterns={
            "EXECUTOR_CTXVAR_NAME": r"runtime\.executor\._IN_EXECUTOR",
        },
        include_glob="**/*.py",
        allowlist_relpaths=("runtime/execution/context.py",),
    )
    assert hits == [], "Do not duplicate executor context markers.\n" + format_hits(hits)
