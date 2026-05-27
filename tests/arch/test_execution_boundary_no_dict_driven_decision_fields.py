from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "runtime" / "handlers" / "ads_autopilot_flow.py"

BANNED_KEYS = {
    "action",
    "route",
    "issuer_id",
    "decision_id",
    "command",
    "commands",
}


def _is_string_key(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def test_execution_boundary_does_not_extract_decision_fields_from_dicts() -> None:
    if not TARGET.exists():
        return

    tree = ast.parse(TARGET.read_text(encoding="utf-8"))
    offenders: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if "execution" not in node.name:
            continue

        violated = False

        for inner in ast.walk(node):
            if isinstance(inner, ast.Subscript):
                key = _is_string_key(inner.slice)
                if key in BANNED_KEYS:
                    violated = True
                    break

        if violated:
            offenders.append(node.name)

    assert not offenders, (
        "Execution boundary functions may not reconstruct decision semantics from dict-like payloads. "
        f"Offenders: {offenders}"
    )
