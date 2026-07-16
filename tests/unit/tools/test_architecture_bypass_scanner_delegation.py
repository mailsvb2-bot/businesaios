from __future__ import annotations

import ast
from pathlib import Path

import tools.architecture_bypass_scanner as scanner
from tools.decision_authority_indirect_scanner import Finding as DecisionFinding

ROOT = Path(__file__).resolve().parents[3]


def test_generic_scanner_delegates_decision_authority_semantics(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[str] = []

    def delegated(*, rel: str, tree: ast.AST):
        assert isinstance(tree, ast.AST)
        calls.append(rel)
        return [
            DecisionFinding(
                code="decision_authority_call",
                path=rel,
                line=2,
                detail="decision_core.decide() outside a canonical owner",
            )
        ]

    monkeypatch.setattr(scanner, "_scan_decision_authority_ast", delegated)
    source = "def run(decision_core, state):\n    return state\n"
    path = tmp_path / "service.py"

    findings = scanner._scan_ast(
        root=tmp_path,
        path=path,
        rel="application/feature/service.py",
        tree=ast.parse(source),
    )

    assert calls == ["application/feature/service.py"]
    assert [item.code for item in findings] == [
        "possible_decision_core_bypass"
    ]


def test_generic_scanner_contains_no_competing_decision_rule_helpers() -> None:
    path = ROOT / "tools" / "architecture_bypass_scanner.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    function_names = {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }

    assert {
        "_is_possible_decision_bypass",
        "_dynamic_authority_lookup",
        "_dynamic_authority_mutation",
        "_subscript_authority_lookup",
        "_receiver_looks_like_decision_authority",
    }.isdisjoint(function_names)
    assert "_delegated_decision_findings" in function_names


def test_nested_product_data_directory_is_scanned_for_raw_effects(
    tmp_path: Path,
) -> None:
    path = tmp_path / "product" / "data" / "service.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "import requests\n"
        "def load():\n"
        "    return requests.get('https://example.test')\n",
        encoding="utf-8",
    )

    findings = scanner.scan(tmp_path)

    assert [item.path for item in findings] == [
        "product/data/service.py"
    ]
    assert [item.code for item in findings] == [
        "raw_side_effect_call_outside_owner"
    ]


def test_root_mutable_data_directory_remains_pruned(tmp_path: Path) -> None:
    path = tmp_path / "data" / "state.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "import requests\n"
        "requests.get('https://example.test')\n",
        encoding="utf-8",
    )

    assert scanner.scan(tmp_path) == ()
