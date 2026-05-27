from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = [
    ROOT / "execution" / "budget_guard.py",
    ROOT / "execution" / "spend_limit_policy.py",
    ROOT / "execution" / "revenue_verification.py",
]


def test_economic_safety_modules_do_not_import_decision_core() -> None:
    offenders: list[str] = []
    for path in TARGETS:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("core.ai.decision_core"):
                offenders.append(str(path.relative_to(ROOT)))
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("core.ai.decision_core"):
                        offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, "Economic safety layer must not import DecisionCore directly: " + ", ".join(sorted(set(offenders)))


def test_economic_safety_modules_do_not_define_decide_like_api() -> None:
    offenders: list[str] = []
    forbidden = {"decide", "choose_action", "issue_decision"}
    for path in TARGETS:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in forbidden:
                offenders.append(f"{path.relative_to(ROOT)}:{node.name}")
            if isinstance(node, ast.AsyncFunctionDef) and node.name in forbidden:
                offenders.append(f"{path.relative_to(ROOT)}:{node.name}")
    assert not offenders, "Economic safety layer must stay execution/governance-only and not become a second brain: " + ", ".join(offenders)
