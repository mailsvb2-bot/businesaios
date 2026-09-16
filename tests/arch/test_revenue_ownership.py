from __future__ import annotations

import ast
from pathlib import Path

from canon.business_ontology_inventory import ontology_ownership_by_entity

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm", "contracts")


def _revenue_signal_definitions() -> list[Path]:
    definitions: list[Path] = []
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            if any(isinstance(node, ast.ClassDef) and node.name == "RevenueSignal" for node in tree.body):
                definitions.append(path.relative_to(ROOT))
    return sorted(definitions)


def test_revenue_inventory_is_partial_after_duplicate_contract_collapse() -> None:
    row = ontology_ownership_by_entity()["Revenue"]
    assert row.status.value == "partial"
    assert row.authoritative_module == "core.economics.types"
    assert row.storage_owner is None
    assert row.allowed_readers == ("core.economics.service",)


def test_revenue_signal_has_one_production_semantic_definition() -> None:
    assert not (ROOT / "contracts/revenue_signal.py").exists()
    assert _revenue_signal_definitions() == [Path("core/economics/types.py")]


def test_economics_contract_reuses_canonical_revenue_signal() -> None:
    text = (ROOT / "core/economics/contracts.py").read_text(encoding="utf-8")
    assert "from core.economics.types import" in text
    assert "RevenueSignal," in text
    assert "class RevenueReader(Protocol):" in text
