from __future__ import annotations

import ast
from pathlib import Path

from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity
from core.economics.types import RevenueSignal
from core.finance.enums import RevenueLifecycleStatus
from core.finance.types import Revenue, RevenueRecord

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm", "contracts")


def _definitions(class_name: str) -> list[Path]:
    definitions: list[Path] = []
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            if any(isinstance(node, ast.ClassDef) and node.name == class_name for node in tree.body):
                definitions.append(path.relative_to(ROOT))
    return sorted(definitions)


def test_revenue_inventory_names_single_durable_owner() -> None:
    row = ontology_ownership_by_entity()["Revenue"]
    assert row.status is OwnershipAuditStatus.DONE
    assert row.authoritative_module == "core.finance.types"
    assert row.storage_owner == "runtime.platform.event_store"
    assert row.allowed_writers == ("application.revenue",)
    assert row.allowed_readers == (
        "application.revenue",
        "core.finance.contracts_readers",
        "core.economics.service",
    )


def test_revenue_entity_has_one_production_definition_and_explicit_lifecycle() -> None:
    assert _definitions("Revenue") == [Path("core/finance/types.py")]
    assert RevenueLifecycleStatus.RECOGNIZED.value == "recognized"
    assert RevenueLifecycleStatus.REVERSED.value == "reversed"
    assert "business_id" in Revenue.__dataclass_fields__
    assert "currency" in Revenue.__dataclass_fields__


def test_legacy_revenue_shapes_remain_read_projections() -> None:
    assert _definitions("RevenueSignal") == [Path("core/economics/types.py")]
    assert _definitions("RevenueRecord") == [Path("core/finance/types.py")]
    assert set(RevenueRecord.__dataclass_fields__) == {"occurred_at", "amount", "source"}
    assert set(RevenueSignal.__dataclass_fields__) == {
        "period_days", "gross_revenue", "net_revenue", "orders", "currency"
    }


def test_revenue_registry_is_single_eventstore_lifecycle_writer() -> None:
    text = (ROOT / "application/revenue.py").read_text(encoding="utf-8")
    assert "CANON_REVENUE_LIFECYCLE_OWNER = True" in text
    assert 'source="revenue_registry"' in text
    assert "EventFactLifecycleWriter(" in text
    assert "BusinessFactV1(" not in text
    assert 'REVENUE_RECOGNIZED = "revenue.recognized"' in text
    assert 'REVENUE_REVERSED = "revenue.reversed"' in text


def test_ontology_runtime_wires_revenue_to_existing_stores() -> None:
    text = (ROOT / "runtime/business_autonomy/ontology_runtime.py").read_text(encoding="utf-8")
    assert "from application.revenue import RevenueRegistry" in text
    assert '"_revenue_registry": RevenueRegistry(event_store=event_store, idempotency_store=idempotency_store)' in text


def test_economics_signal_does_not_claim_revenue_lifecycle_ownership() -> None:
    text = (ROOT / "core/economics/types.py").read_text(encoding="utf-8")
    assert "CANON_REVENUE_LIFECYCLE_OWNER" not in text


def test_payment_and_invoice_do_not_implicitly_recognize_revenue() -> None:
    for relative in (
        "runtime/_internal/effects_actions/payments/selection.py",
        "runtime/_internal/effects_actions/payments/reconciliation.py",
        "billing/invoice_registry.py",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "RevenueRegistry" not in text
        assert ".recognize(" not in text
