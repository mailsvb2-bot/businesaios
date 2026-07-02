from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXECUTOR = ROOT / "runtime" / "executor.py"
HELPER = ROOT / "runtime" / "execution" / "executor_post_init_bindings.py"


def test_executor_delegates_post_init_bindings_to_helper() -> None:
    text = EXECUTOR.read_text(encoding="utf-8")

    assert "from runtime.execution.executor_post_init_bindings import bind_executor_post_init_surfaces" in text
    assert "bind_executor_post_init_surfaces(" in text
    assert "ActionBudgetEngine()" not in text
    assert "AutonomySafetyBundle(" not in text
    assert "build_executor_queue_support(" not in text


def test_executor_post_init_helper_is_bounded_owner() -> None:
    text = HELPER.read_text(encoding="utf-8")
    tree = ast.parse(text)
    functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]

    assert functions == ["bind_executor_post_init_surfaces"]
    assert "CANON_RUNTIME_EXECUTOR_POST_INIT_BINDINGS = True" in text
