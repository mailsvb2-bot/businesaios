from __future__ import annotations

import ast
from pathlib import Path

from runtime.demand_gravity.public_api import __all__ as public_symbols


FORBIDDEN_NAMES = {
    "approve",
    "bid",
    "decide",
    "execute",
    "mutate",
    "optimize_budget",
    "publish",
    "rank",
    "select_channel",
    "select_strategy",
    "spend",
}

FORBIDDEN_IMPORTS = {
    "subprocess",
    "requests",
    "httpx",
    "sqlite3",
    "psycopg",
    "runtime.execution",
    "runtime.payments",
}


def test_demand_gravity_public_api_exports_only_candidate_surfaces() -> None:
    forbidden = {"DecisionCore", "Executor", "BudgetGuard", "SpendLimitPolicy", "AutonomyPolicy"}
    assert not (set(public_symbols) & forbidden)


def test_demand_gravity_has_no_forbidden_symbols_or_raw_side_effect_imports() -> None:
    root = Path("runtime/demand_gravity")
    findings: list[str] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name in FORBIDDEN_NAMES:
                    findings.append(f"{path}:{node.lineno}:forbidden_symbol:{node.name}")
            if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
                findings.append(f"{path}:{node.lineno}:forbidden_name:{node.id}")
            if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_NAMES:
                findings.append(f"{path}:{node.lineno}:forbidden_attribute:{node.attr}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in FORBIDDEN_IMPORTS:
                        findings.append(f"{path}:{node.lineno}:forbidden_import:{alias.name}")
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module in FORBIDDEN_IMPORTS:
                    findings.append(f"{path}:{node.lineno}:forbidden_import:{module}")
    assert findings == []
