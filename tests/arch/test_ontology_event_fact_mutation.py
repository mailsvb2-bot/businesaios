from __future__ import annotations

import ast
from pathlib import Path

from application.ontology import CANON_ONTOLOGY_EVENT_FACT_MUTATION
from canon.business_ontology_inventory import BUSINESS_ONTOLOGY_OWNERSHIP_AUDIT

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm")
OWNER = Path("application/ontology/event_fact_lifecycle.py")
CUSTOMER_DIRECT_OWNER = Path("crm/customer_registry.py")
SHARED_EVENT_FACT_OWNERS = (
    Path("application/organization/registry.py"),
    Path("application/person/registry.py"),
    Path("application/lead/registry.py"),
    Path("application/partner/registry.py"),
    Path("application/employee/registry.py"),
    Path("application/business_service/registry.py"),
    Path("runtime/messaging/conversation_registry.py"),
    Path("runtime/messaging/message_registry.py"),
    Path("application/campaign/registry.py"),
    Path("application/opportunity.py"),
    Path("application/deal/registry.py"),
    Path("billing/invoice_registry.py"),
    Path("application/expense.py"),
    Path("application/revenue.py"),
    Path("application/asset.py"),
    Path("application/business_resource.py"),
    Path("application/business_goal.py"),
    Path("application/business_constraint.py"),
    Path("application/risk.py"),
    Path("application/task/registry.py"),
    Path("application/artifact/registry.py"),
    Path("application/document/registry.py"),
)
EXTERNAL_FACT_INGRESS = Path("application/business_autonomy/evidence_projection.py")
DIRECT_BUSINESS_FACT_MUTATION_OWNERS = (OWNER, CUSTOMER_DIRECT_OWNER)
SPECIAL_EVENT_STORE_WRITER_MODULES = (
    "crm.customer_registry",
    "runtime._internal.effects_actions.payments.selection",
    "runtime._internal.effects_actions.payments.reconciliation",
)
SPECIAL_EVENT_CHRONOLOGY_OWNERS = {
    "Hypothesis": (
        "core.growth.strategy.backlog_store",
        ("core.growth.strategy.backlog_store",),
    ),
}


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def _calls_constructor(tree: ast.AST, name: str) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == name:
            return True
        if isinstance(func, ast.Attribute) and func.attr == name:
            return True
    return False


def _constructor_consumers(name: str) -> list[Path]:
    consumers = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if _calls_constructor(tree, name):
            consumers.append(path.relative_to(ROOT))
    return sorted(consumers)


def test_ontology_event_fact_mutation_owner_marker_is_unique() -> None:
    assert CANON_ONTOLOGY_EVENT_FACT_MUTATION is True
    owners = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "CANON_ONTOLOGY_EVENT_FACT_MUTATION"
                for target in node.targets
            ):
                if isinstance(node.value, ast.Constant) and node.value.value is True:
                    owners.append(path.relative_to(ROOT))
    assert owners == [OWNER]


def test_shared_event_fact_writer_consumers_are_review_locked() -> None:
    assert _constructor_consumers("EventFactLifecycleWriter") == sorted(
        (*SHARED_EVENT_FACT_OWNERS, EXTERNAL_FACT_INGRESS)
    )


def test_event_store_ontology_writers_are_review_locked() -> None:
    shared_modules = {
        path.with_suffix("").as_posix().replace("/", ".") for path in SHARED_EVENT_FACT_OWNERS
    }
    expected = shared_modules | set(SPECIAL_EVENT_STORE_WRITER_MODULES)
    actual = {
        writer
        for row in BUSINESS_ONTOLOGY_OWNERSHIP_AUDIT
        if row.storage_owner == "runtime.platform.event_store"
        for writer in row.allowed_writers
    }
    assert actual == expected


def test_special_event_chronology_owners_are_review_locked() -> None:
    rows = {row.entity: row for row in BUSINESS_ONTOLOGY_OWNERSHIP_AUDIT}
    for entity, (storage_owner, writers) in SPECIAL_EVENT_CHRONOLOGY_OWNERS.items():
        row = rows[entity]
        assert row.storage_owner == storage_owner
        assert row.allowed_writers == writers


def test_direct_business_fact_mutation_is_review_locked() -> None:
    assert _constructor_consumers("BusinessFactV1") == sorted(DIRECT_BUSINESS_FACT_MUTATION_OWNERS)


def test_event_sourced_entity_registries_delegate_durable_mutation() -> None:
    for path in SHARED_EVENT_FACT_OWNERS:
        source = (ROOT / path).read_text(encoding="utf-8")
        assert "EventFactLifecycleWriter" in source
        assert "BusinessFactV1(" not in source
        assert "build_idempotency_key(" not in source
        assert "IdempotencyState" not in source
        assert "event_metadata" in source


def test_customer_direct_writer_reuses_canonical_event_metadata_contract() -> None:
    source = (ROOT / CUSTOMER_DIRECT_OWNER).read_text(encoding="utf-8")
    assert "BusinessFactV1(" in source
    assert "canonical_event_metadata" in source
    assert "assert_canonical_event_metadata" in source
    assert "event_metadata" in source


def test_business_autonomy_bootstrap_delegates_ontology_composition() -> None:
    bootstrap = (ROOT / "runtime/business_autonomy/bootstrap.py").read_text(encoding="utf-8")
    wiring = (ROOT / "runtime/business_autonomy/ontology_runtime.py").read_text(encoding="utf-8")
    registry_names = (
        "CustomerRegistry",
        "OrganizationRegistry",
        "PersonRegistry",
        "EmployeeRegistry",
        "PartnerRegistry",
        "BusinessServiceRegistry",
        "DurableTaskRegistry",
        "ArtifactRegistry",
        "DocumentRegistry",
    )
    assert "wire_business_ontology_runtime(" in bootstrap
    for name in registry_names:
        assert name not in bootstrap
        assert name in wiring
