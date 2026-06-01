from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALLOWED_DECISION_METHOD_FILES = {
    "boot/registrations/register_decision_core.py",
}


def test_runtime_decision_entrypoints_are_small_and_explicit() -> None:
    hits: list[str] = []
    for path in ROOT.rglob("*.py"):
        normalized = path.relative_to(ROOT).as_posix()
        if normalized.startswith("tests/"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "decide_and_execute":
                hits.append(normalized)
    assert set(hits) == ALLOWED_DECISION_METHOD_FILES


def test_runtime_action_dispatcher_uses_decision_execution_port_only() -> None:
    text = (ROOT / "core" / "decision" / "action_dispatcher.py").read_text(encoding="utf-8")
    assert ".decide_and_execute(action)" in text
    assert "action_executor.execute(" not in text


def test_runtime_decision_core_factory_is_the_only_constructor_alias() -> None:
    text = (ROOT / "boot" / "factories" / "decision_core_factory.py").read_text(encoding="utf-8")
    assert "build_decision_core" in text
    assert "runtime_construction_token()" in text
