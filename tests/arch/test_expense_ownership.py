from __future__ import annotations

import ast
from pathlib import Path

from application.expense import CANON_EXPENSE_LIFECYCLE_OWNER
from canon.business_ontology_inventory import ontology_ownership_by_entity

ROOT = Path(__file__).resolve().parents[2]
OWNER = Path("application/expense.py")
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm")


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_expense_inventory_names_one_durable_owner() -> None:
    row = ontology_ownership_by_entity()["Expense"]
    assert row.status.value == "done"
    assert row.authoritative_module == "core.finance.types"
    assert row.storage_owner == "runtime.platform.event_store"
    assert row.allowed_writers == ("application.expense",)


def test_expense_lifecycle_owner_marker_is_unique() -> None:
    owners: list[Path] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if any(
                isinstance(target, ast.Name) and target.id == "CANON_EXPENSE_LIFECYCLE_OWNER"
                for target in node.targets
            ) and isinstance(node.value, ast.Constant) and node.value.value is True:
                owners.append(path.relative_to(ROOT))
    assert CANON_EXPENSE_LIFECYCLE_OWNER is True
    assert owners == [OWNER]


def test_expense_owner_uses_shared_event_fact_writer_without_pii_text() -> None:
    source = (ROOT / OWNER).read_text(encoding="utf-8")
    assert "EventFactLifecycleWriter" in source
    assert 'source="expense_registry"' in source
    assert '"description"' not in source
    assert "expense.recorded" in source and "expense.voided" in source


def test_business_ontology_runtime_wires_expense_registry_to_existing_stores() -> None:
    wiring = (ROOT / "runtime/business_autonomy/ontology_runtime.py").read_text(encoding="utf-8")
    assert "from application.expense import ExpenseRegistry" in wiring
    assert '"_expense_registry"' in wiring
    assert "ExpenseRegistry(event_store=event_store, idempotency_store=idempotency_store)" in wiring


def test_expense_semantic_contract_is_unique_from_legacy_read_record() -> None:
    source = (ROOT / "core/finance/types.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
    assert names.count("Expense") == 1
    assert names.count("ExpenseRecord") == 1
    expense = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Expense")
    fields = {
        node.target.id
        for node in expense.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert {"expense_id", "tenant_id", "business_id", "amount", "currency", "category"} <= fields
