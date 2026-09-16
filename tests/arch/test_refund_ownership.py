from __future__ import annotations

import ast
from pathlib import Path

from billing.recovery_contracts import CANON_BILLING_REFUND_CONTRACT, RefundResult
from billing.refund_orchestrator import CANON_BILLING_REFUND_LIFECYCLE_OWNER
from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity
from runtime.platform.billing_recovery_store import CANON_PLATFORM_BILLING_RECOVERY_STORE, SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = Path("billing/recovery_contracts.py")
WRITER = Path("billing/refund_orchestrator.py")


def _production_python_files():
    for root_name in ("billing", "runtime", "application", "core", "contracts"):
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_refund_inventory_names_single_contract_writer_and_durable_store() -> None:
    row = ontology_ownership_by_entity()["Refund"]
    assert CANON_BILLING_REFUND_CONTRACT is True
    assert CANON_BILLING_REFUND_LIFECYCLE_OWNER is True
    assert CANON_PLATFORM_BILLING_RECOVERY_STORE is True
    assert SCHEMA_VERSION == 1
    assert row.status is OwnershipAuditStatus.DONE
    assert row.authoritative_module == "billing.recovery_contracts"
    assert row.storage_owner == "runtime.platform.billing_recovery_store"
    assert row.allowed_writers == ("billing.refund_orchestrator",)
    assert row.allowed_readers == ("billing.recovery_store",)


def test_refund_result_contract_and_lifecycle_owner_are_unique() -> None:
    result_defs: list[Path] = []
    owners: list[Path] = []
    for path in _production_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == "RefundResult":
                result_defs.append(path.relative_to(ROOT))
            if (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "CANON_BILLING_REFUND_LIFECYCLE_OWNER"
                    for target in node.targets
                )
                and isinstance(node.value, ast.Constant)
                and node.value.value is True
            ):
                owners.append(path.relative_to(ROOT))
    assert result_defs == [CONTRACT]
    assert owners == [WRITER]


def test_refund_orchestrator_reexports_canonical_contract_for_compatibility() -> None:
    from billing import refund_orchestrator

    assert refund_orchestrator.RefundResult is RefundResult
