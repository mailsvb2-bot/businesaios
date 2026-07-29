from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
_EVENT_STORE_RECEIVERS = {"event_store", "store", "es"}
_EVENT_STORE_METHODS = {"iter_events", "count_events"}
_EXCLUDED_PARTS = {".git", ".venv", "venv", "__pycache__", "node_modules", "target"}


@dataclass(frozen=True)
class _Violation:
    path: str
    line: int
    rule: str
    source: str


def _production_python_files() -> tuple[Path, ...]:
    files: list[Path] = []
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT)
        if relative.parts and relative.parts[0] == "tests":
            continue
        if any(part in _EXCLUDED_PARTS for part in relative.parts):
            continue
        files.append(path)
    return tuple(sorted(files))


def _source_line(source: str, line: int) -> str:
    lines = source.splitlines()
    return lines[line - 1].strip() if 0 < line <= len(lines) else ""


def _format(violations: list[_Violation]) -> str:
    return "\n".join(
        f"  {item.path}:{item.line}: {item.source} [{item.rule}]"
        for item in violations
    )


@pytest.mark.lock
def test_lock_eventstore_calls_require_tenant_id_kwarg() -> None:
    """Every production EventStore read must declare its tenant explicitly."""

    violations: list[_Violation] = []
    for path in _production_python_files():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            receiver = node.func.value
            if not isinstance(receiver, ast.Name) or receiver.id not in _EVENT_STORE_RECEIVERS:
                continue
            if node.func.attr not in _EVENT_STORE_METHODS:
                continue
            if any(keyword.arg == "tenant_id" for keyword in node.keywords):
                continue
            violations.append(
                _Violation(
                    path=path.relative_to(ROOT).as_posix(),
                    line=node.lineno,
                    rule=f"{node.func.attr}_missing_tenant_id",
                    source=_source_line(source, node.lineno),
                )
            )

    assert not violations, (
        "EventStore calls must be tenant-explicit (tenant_id=...).\n"
        + _format(violations)
    )


@pytest.mark.lock
def test_lock_no_empty_tenant_id_literals() -> None:
    """Production calls must never receive a blank literal tenant identifier."""

    allowed = {"runtime/boot/tenant_hard_gate.py"}
    violations: list[_Violation] = []
    for path in _production_python_files():
        relative = path.relative_to(ROOT).as_posix()
        if relative in allowed:
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg != "tenant_id":
                    continue
                value = keyword.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str) and not value.value.strip():
                    violations.append(
                        _Violation(
                            path=relative,
                            line=value.lineno,
                            rule="tenant_id_empty_str",
                            source=_source_line(source, value.lineno),
                        )
                    )

    assert not violations, "Empty tenant_id literals are forbidden in production code.\n" + _format(violations)
