from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "advisory" / "__init__.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "application.decision",
    "application.decisioning",
    "application.memory",
    "application.task",
    "application.tasks",
    "attribution",
    "execution",
    "interfaces.messaging_runtime",
    "runtime",
)
FORBIDDEN_CLASS_TOKENS = (
    "DecisionCore",
    "Repository",
    "Outbox",
    "Scheduler",
    "Router",
    "Memory",
    "ExecutionEngine",
    "AttributionEngine",
    "ExperimentEngine",
)
FORBIDDEN_FUNCTION_PREFIXES = ("dispatch", "enqueue", "persist", "save", "schedule")


def _modules():
    return (ROOT,)


def test_funnel_intelligence_is_pure_advisory_not_a_second_brain() -> None:
    assert _modules()
    violations: list[str] = []
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith(FORBIDDEN_IMPORT_PREFIXES):
                    violations.append(f"{path.name}: forbidden import {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                        violations.append(f"{path.name}: forbidden import {alias.name}")
            elif isinstance(node, ast.ClassDef):
                if any(token in node.name for token in FORBIDDEN_CLASS_TOKENS):
                    violations.append(f"{path.name}: forbidden owner-like class {node.name}")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith(FORBIDDEN_FUNCTION_PREFIXES):
                    violations.append(f"{path.name}: forbidden side-effect-like function {node.name}")
    assert not violations, "\n".join(violations)


def test_funnel_intelligence_has_no_storage_or_provider_side_effect_primitives() -> None:
    forbidden_fragments = (
        "sqlite3",
        "psycopg",
        "sqlalchemy",
        "open(",
        ".write_text(",
        ".write_bytes(",
        "requests.",
        "httpx.",
        "urllib.request",
        "subprocess",
    )
    violations: list[str] = []
    for path in _modules():
        text = path.read_text(encoding="utf-8")
        for fragment in forbidden_fragments:
            if fragment in text:
                violations.append(f"{path.name}: {fragment}")
    assert not violations, "\n".join(violations)
