from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _iter_py_files():
    for py in ROOT.rglob("*.py"):
        rel = py.relative_to(ROOT).as_posix()
        if rel.startswith((".venv/", "docs/", "scripts/", "tests/")):
            continue
        yield py, rel


def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_single_decision_center_decisioncore_import_allowlist() -> None:
    """DecisionCore import is allowed only in the runtime boot assembly."""
    allowed = {"runtime/boot/boot_core_assembly.py", "runtime/boot/boot_decision_core.py", "core/decision_core.py"}
    offenders: list[str] = []
    for py, rel in _iter_py_files():
        tree = _parse(py)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "") == "core.ai.decision_core":
                if any(alias.name == "DecisionCore" for alias in node.names) and rel not in allowed:
                    offenders.append(rel)
    assert offenders == [], f"DecisionCore imported outside allowlist: {sorted(set(offenders))}"


def test_no_decision_bypass_runtime_execute_callsites_allowlist() -> None:
    """Runtime executor execute(...) calls must stay in explicit orchestration points."""
    allowed = {
        "runtime/execution/decision_execution_service.py",
        "runtime/scheduler_parts/decision_request.py",
        "runtime/scheduler_parts/deploy_flow.py",
        "runtime/scheduler_parts/monitoring.py",
        "runtime/self_driving_scheduler.py",
    }
    offenders: list[str] = []
    for py, rel in _iter_py_files():
        if not rel.startswith("runtime/"):
            continue
        text = py.read_text(encoding="utf-8")
        if "executor.execute(" not in text:
            continue
        if rel not in allowed:
            offenders.append(rel)
    assert offenders == [], f"executor.execute call outside allowlist: {sorted(set(offenders))}"


def test_no_second_brain_runtime_handlers_cannot_use_decision_api_directly() -> None:
    """Handlers must execute pre-decided actions and never decide/optimize themselves."""
    handlers_root = ROOT / "runtime" / "handlers"
    offenders: list[str] = []
    for py in handlers_root.rglob("*.py"):
        rel = py.relative_to(ROOT).as_posix()
        text = py.read_text(encoding="utf-8")
        if ".issue(" in text or ".optimize(" in text:
            offenders.append(rel)
    assert offenders == [], f"Decision API usage found in runtime handlers: {sorted(set(offenders))}"
