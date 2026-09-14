from __future__ import annotations

import ast
from pathlib import Path

from application.business_autonomy.distributed_capability_trust_registry import (
    CANON_BUSINESS_LIFECYCLE_OWNER,
)

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm")
OWNER = Path("application/business_autonomy/distributed_capability_trust_registry.py")


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_distributed_business_registry_is_the_single_declared_lifecycle_owner() -> None:
    assert CANON_BUSINESS_LIFECYCLE_OWNER is True
    declarations = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if any(isinstance(target, ast.Name) and target.id == "CANON_BUSINESS_LIFECYCLE_OWNER" for target in node.targets):
                if isinstance(node.value, ast.Constant) and node.value.value is True:
                    declarations.append(path.relative_to(ROOT))
    assert declarations == [OWNER]


def test_no_production_code_writes_business_registry_collection_directly() -> None:
    offenders = []
    for path in _python_files():
        if path.relative_to(ROOT) == OWNER:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "put":
                continue
            for keyword in node.keywords:
                if keyword.arg == "collection" and isinstance(keyword.value, ast.Constant) and keyword.value.value == "business_registry":
                    offenders.append((path.relative_to(ROOT), node.lineno))
    assert offenders == []


def test_business_registry_mutation_callers_match_canonical_writer_inventory() -> None:
    from canon.business_ontology_inventory import ontology_ownership_by_entity

    expected = set(ontology_ownership_by_entity()["Business"].allowed_writers)
    actual = set()
    for path in _python_files():
        if path.relative_to(ROOT) == OWNER:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "register_or_update":
                continue
            module = ".".join(path.relative_to(ROOT).with_suffix("").parts)
            actual.add(module)
    assert actual == expected
