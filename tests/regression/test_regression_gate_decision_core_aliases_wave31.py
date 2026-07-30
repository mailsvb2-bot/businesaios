from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_decision_entrypoints_are_small_and_explicit() -> None:
    hits: list[str] = []
    for path in ROOT.rglob("*.py"):
        normalized = path.relative_to(ROOT).as_posix()
        if normalized.startswith("tests/"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "decide_and_execute":
                hits.append(normalized)
    assert hits == []


def test_runtime_action_dispatcher_is_a_pure_envelope_only_alias() -> None:
    text = (ROOT / "core" / "decision" / "action_dispatcher.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    assert "CANONICAL_OWNER_MODULE = \"application.decision.action_dispatcher\"" in text
    assert not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for node in tree.body)
    assert "decide_and_execute" not in text
    assert "action_executor.execute(" not in text


def test_runtime_decision_core_factory_is_the_only_constructor_alias() -> None:
    text = (ROOT / "boot" / "factories" / "decision_core_factory.py").read_text(encoding="utf-8")
    assert "build_decision_core" in text
    assert "runtime_construction_token()" in text
