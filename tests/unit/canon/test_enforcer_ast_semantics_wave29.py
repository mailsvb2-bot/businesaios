from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

import canon.enforcer.checks_docs as checks_docs
from canon.enforcer.ast_semantics import (
    full_attr_name,
    infra_name_regex,
    is_stub_function,
    looks_like_integration_stub,
    returns_literal_status_ok,
    returns_literal_true,
)
from canon.enforcer.reporting import EnforcerReport


def _function(source: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    node = ast.parse(source).body[0]
    assert isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    return node


def test_ast_semantics_classify_paths_stubs_and_literal_results() -> None:
    assert full_attr_name(ast.Name(id="service")) == "service"
    assert full_attr_name(ast.parse("service.client.send", mode="eval").body) == "service.client.send"
    assert full_attr_name(ast.parse("service.send()", mode="eval").body) == "service.send"
    assert full_attr_name(ast.Constant(value=1)) == ""

    not_function = ast.Pass()
    empty = ast.FunctionDef(
        name="empty",
        args=ast.arguments(
            posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]
        ),
        body=[],
        decorator_list=[],
    )
    assert is_stub_function(not_function) is False
    assert is_stub_function(empty) is True
    assert is_stub_function(_function("def send():\n    pass\n")) is True
    assert is_stub_function(_function('def send():\n    "doc"\n')) is True
    assert is_stub_function(_function("def send():\n    return 1\n")) is False

    status_ok = ast.parse('return {"status": "ok"}').body[0]
    status_bad = ast.parse('return {"status": "bad"}').body[0]
    mixed = ast.parse('return {name: "ok", "status": value}').body[0]
    assert returns_literal_status_ok(ast.Pass()) is False
    assert returns_literal_status_ok(ast.Return(value=ast.Constant(value=True))) is False
    assert returns_literal_status_ok(status_ok) is True
    assert returns_literal_status_ok(status_bad) is False
    assert returns_literal_status_ok(mixed) is False
    assert returns_literal_true(ast.parse("return True").body[0]) is True
    assert returns_literal_true(ast.parse("return False").body[0]) is False

    assert looks_like_integration_stub(ast.Pass()) is False
    assert looks_like_integration_stub(_function("def send():\n    pass\n")) is True
    assert looks_like_integration_stub(_function('def publish():\n    return {"status": "ok"}\n')) is True
    assert looks_like_integration_stub(_function("async def connect():\n    return True\n")) is True
    assert looks_like_integration_stub(_function("def calculate():\n    return True\n")) is False
    assert looks_like_integration_stub(_function("def send():\n    x = 1\n    return True\n")) is False

    pattern = infra_name_regex()
    assert pattern.search("service.connector.call") is not None
    assert pattern.search("service.connection.call") is None


@dataclass(frozen=True)
class _Finding:
    kind: str
    path: str
    message: str


def test_document_checks_preserve_severity_and_required_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = EnforcerReport(ok=True)
    checks_docs.check_readme_and_contributing(report, tmp_path)
    assert report.violations
    assert all(item.kind == "missing-canon-enforcement-file" for item in report.violations)

    required = [
        "docs/SYSTEM_TZ_CANONICAL.md",
        "docs/ARCHITECTURE_CANON_V20.md",
        "docs/CANON_MESSAGING_POLICY_V1.md",
        "CONTRIBUTING.md",
        "scripts/certify_repo.py",
        "scripts/check_world_model_integrity.py",
        "scripts/check_world_model_typing.py",
        "scripts/migrate_world_model_to_canonical.py",
    ]
    for relative in required:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ok", encoding="utf-8")
    complete = EnforcerReport(ok=True)
    checks_docs.check_readme_and_contributing(complete, tmp_path)
    assert complete.violations == []

    monkeypatch.setattr(
        checks_docs,
        "scan_world_model_canon_contract",
        lambda _root: (
            _Finding("missing-decision-core", "core/ai/decision_core.py", "missing"),
            _Finding("advisory", "docs/x.md", "review"),
        ),
    )
    world = EnforcerReport(ok=True)
    checks_docs.check_super_canon_world_model_contract(world, tmp_path)
    assert [item.severity for item in world.violations] == ["critical", "high"]
