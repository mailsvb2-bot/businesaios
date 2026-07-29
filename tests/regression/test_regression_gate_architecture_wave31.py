from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANONICAL_EXECUTION_OWNER = "boot/runtime_service_contracts.py"


def test_no_new_raw_action_executor_execute_calls_escape_canonical_gate() -> None:
    calls: list[tuple[str, str]] = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith("tests/"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            owner = node.func.value
            if (
                node.func.attr == "execute"
                and isinstance(owner, ast.Attribute)
                and isinstance(owner.value, ast.Name)
                and owner.value.id == "self"
                and owner.attr == "action_executor"
            ):
                argument = ast.unparse(node.args[0]) if node.args else ""
                calls.append((rel, argument))

    assert calls == [(CANONICAL_EXECUTION_OWNER, "envelope")]


def test_runtime_boot_observability_is_not_silent_or_partial() -> None:
    text = (ROOT / "boot" / "runtime_boot.py").read_text(encoding="utf-8")
    for required in ("event_bus", "metrics", "tracer", "decision_audit_log", "action_audit_log"):
        assert required in text
