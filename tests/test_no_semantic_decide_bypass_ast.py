from __future__ import annotations

import ast
import pathlib

"""Semantic bypass guardrails.

Goal:
  - DecisionCore.optimize(...) must be the ONLY "decide" implementation in production code.
  - No other production module may call obj.optimize(...), to prevent "second brains" and
    hinge semantics.

Notes:
  - Tests are excluded from this scan by design (they may use minimal stubs).
  - A small facade/proxy MAY call DecisionCore.decide; currently we allow main.py.
"""


ROOT = pathlib.Path(__file__).resolve().parents[1]

# --- Allow-lists ---

ALLOWED_DECIDE_DEF_FILES = {
    ROOT / "core" / "ai" / "decision_core.py",
}

ALLOWED_DOT_DECIDE_CALL_FILES = {
    ROOT / "main.py",
    ROOT / "core" / "ai" / "decision_core.py",
}


EXCLUDED_DIRS = {
    ROOT / "tests",
    ROOT / "experimental",
    ROOT / "docs",
    ROOT / "ci",
    ROOT / ".github",
}


def _is_excluded(path: pathlib.Path) -> bool:
    for d in EXCLUDED_DIRS:
        try:
            path.relative_to(d)
            return True
        except ValueError:
            pass
    return False


def _iter_production_py_files() -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for p in ROOT.rglob("*.py"):
        if _is_excluded(p):
            continue
        files.append(p)
    return files


def test_no_decide_definitions_outside_decision_core():
    offenders: list[str] = []
    for path in _iter_production_py_files():
        if path in ALLOWED_DECIDE_DEF_FILES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == "decide":
                offenders.append(f"{path}:{node.lineno}: def decide")
    assert not offenders, "Forbidden decide() definitions found:\n" + "\n".join(offenders)


def test_no_dot_decide_calls_outside_facade():
    offenders: list[str] = []
    for path in _iter_production_py_files():
        if path in ALLOWED_DOT_DECIDE_CALL_FILES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "decide":
                offenders.append(f"{path}:{node.lineno}: .optimize(...) call")
    assert not offenders, "Forbidden .optimize(...) calls found:\n" + "\n".join(offenders)
