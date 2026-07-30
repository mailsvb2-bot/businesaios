from __future__ import annotations

import ast
from pathlib import Path


STRICT_FILES = (
    "reliability/idempotency_sqlite_backend.py",
    "runtime/execution/executor_reliability.py",
    "runtime/execution/outcome_persistence_lock.py",
    "runtime/execution/reliability_runtime.py",
)


def _broad_handlers(path: str) -> list[ast.ExceptHandler]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
    handlers: list[ast.ExceptHandler] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if node.type is None:
            handlers.append(node)
            continue
        if isinstance(node.type, ast.Name) and node.type.id in {"Exception", "BaseException"}:
            handlers.append(node)
    return handlers


def test_reliability_persistence_files_have_no_broad_exception_handlers() -> None:
    for path in STRICT_FILES:
        assert _broad_handlers(path) == [], path
        text = Path(path).read_text(encoding="utf-8")
        assert "suppress(Exception)" not in text
        assert "suppress(BaseException)" not in text


def test_executor_stage_keeps_only_reraising_dispatch_boundary() -> None:
    path = "runtime/execution/executor_stages.py"
    handlers = _broad_handlers(path)

    assert len(handlers) == 1
    handler = handlers[0]
    assert handler.lineno > 100
    assert any(isinstance(node, ast.Raise) and node.exc is None for node in ast.walk(handler))
    source = Path(path).read_text(encoding="utf-8")
    assert "top-level dispatch boundary: record failure, then re-raise unchanged" in source
