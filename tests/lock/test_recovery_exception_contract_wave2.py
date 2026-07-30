from __future__ import annotations

import ast
from pathlib import Path


def _broad_handlers(path: str) -> list[ast.ExceptHandler]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
    handlers: list[ast.ExceptHandler] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if node.type is None:
            handlers.append(node)
        elif isinstance(node.type, ast.Name) and node.type.id in {"Exception", "BaseException"}:
            handlers.append(node)
    return handlers


def test_recovery_uses_fail_closed_proof_lookup_surface() -> None:
    recovery = Path("runtime/executor_recovery_flow.py").read_text(encoding="utf-8")
    public_helper = recovery[recovery.index("def has_proof_event("):recovery.index("def execute_recovery_flow(")]
    recovery_flow = recovery[recovery.index("def execute_recovery_flow("):]

    assert "except Exception" not in public_helper
    assert "return bool(event_log.has_event" in public_helper
    assert "if has_proof_event(" in recovery_flow
    assert "executor._has_proof_event(" not in recovery_flow


def test_recovery_flow_keeps_only_documented_reraising_boundaries() -> None:
    path = "runtime/executor_recovery_flow.py"
    source = Path(path).read_text(encoding="utf-8")
    handlers = _broad_handlers(path)

    assert len(handlers) == 3
    assert "documented failure-recording boundary" in source
    assert "recovery cannot re-dispatch an irreversible effect on a false negative" in source
    assert "Do not duplicate those writes here" in source

    dispatch_handlers = [
        handler
        for handler in handlers
        if any(isinstance(node, ast.Raise) and node.exc is None for node in ast.walk(handler))
    ]
    assert len(dispatch_handlers) == 1
