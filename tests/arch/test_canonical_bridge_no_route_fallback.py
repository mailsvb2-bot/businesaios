from __future__ import annotations

import ast
from pathlib import Path


def test_canonical_bridge_does_not_accept_route_fallback() -> None:
    path = Path("demand_decision/canonical_decision_bridge.py")
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)

    assert "from runtime.decision_gateway import issue_runtime_decision" in text
    assert "hasattr(self._decision_core, 'route')" not in text
    assert 'hasattr(self._decision_core, "route")' not in text

    route_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "route"
    ]
    assert route_calls == []

    issue_method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_issue_route_decision"
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "issue_runtime_decision"
        for node in ast.walk(issue_method)
    )
