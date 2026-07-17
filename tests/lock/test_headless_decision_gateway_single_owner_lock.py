from __future__ import annotations

import ast
from pathlib import Path

from application.headless import decision_gateway as headless_gateway


def _issue_helper_node() -> ast.FunctionDef:
    path = Path(headless_gateway.__file__).resolve()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "issue_headless_decision":
            return node
    raise AssertionError("issue_headless_decision is missing")


def test_headless_issue_helper_delegates_to_the_runtime_owner_directly() -> None:
    node = _issue_helper_node()
    called_names = {
        child.func.id
        for child in ast.walk(node)
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
    }
    issue_attributes = [
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Attribute) and child.attr == "issue"
    ]

    assert headless_gateway.CANON_HEADLESS_DECISION_GATEWAY_ISSUE_OWNER is False
    assert "issue_runtime_decision" in called_names
    assert "build_headless_decision_ingress" not in called_names
    assert issue_attributes == []
