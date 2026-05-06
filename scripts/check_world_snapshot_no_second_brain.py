from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORLD_MODEL_DIR = ROOT / "core" / "world_model"
FORBIDDEN_IMPORT_PARTS = (
    "decision_core",
    "ai_ceo",
    "autopilot",
    "executor",
    "execution",
    "campaign_apply",
    "pricing_select",
)
FORBIDDEN_CALL_NAMES = (
    "decide",
    "issue_decision",
    "execute",
    "apply_campaign",
    "select_strategy",
    "choose_action",
)


def _iter_py_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _dotted_name(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def _check_file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.lower()
                if any(part in name for part in FORBIDDEN_IMPORT_PARTS):
                    errors.append(f"{path}: forbidden import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").lower()
            if any(part in module for part in FORBIDDEN_IMPORT_PARTS):
                errors.append(f"{path}: forbidden import-from {node.module}")
        elif isinstance(node, ast.Call):
            name = _dotted_name(node.func).lower()
            if any(name.endswith(part) or f".{part}" in name for part in FORBIDDEN_CALL_NAMES):
                errors.append(f"{path}: forbidden call {name}")
    return errors


def main() -> int:
    errors: list[str] = []
    for path in _iter_py_files(WORLD_MODEL_DIR):
        errors.extend(_check_file(path))
    if errors:
        for item in errors:
            print(item)
        return 1
    print("world_model no-second-brain check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
