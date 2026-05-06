from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_IMPORT_TOKENS = (
    "runtime.platform.event_store.postgres_event_store_part1",
    "runtime.platform.event_store.postgres_event_store_part2",
    "runtime.platform.event_store.sqlite_read_queries_part1",
    "runtime.platform.event_store.sqlite_read_queries_part2",
    "runtime.platform.behavior_graph.sqlite_behavior_graph_store_part1",
    "runtime.platform.behavior_graph.sqlite_behavior_graph_store_part2",
)

ALLOWED_PREFIXES = (
    "runtime/platform/event_store/",
    "runtime/platform/behavior_graph/",
    "tests/",
)


def test_split_storage_modules_are_internal_only() -> None:
    violations: list[str] = []

    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(ALLOWED_PREFIXES):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in FORBIDDEN_IMPORT_TOKENS:
            if token in text:
                violations.append(f"{rel}:forbidden-split-import:{token}")

    assert violations == [], violations
