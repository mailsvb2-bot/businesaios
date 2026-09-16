from __future__ import annotations

import ast
from pathlib import Path

from canon.business_ontology_inventory import ontology_ownership_by_entity
from runtime.messaging.conversation_registry import CANON_CONVERSATION_LIFECYCLE_OWNER

ROOT = Path(__file__).resolve().parents[2]
OWNER = Path("runtime/messaging/conversation_registry.py")
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm")


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_conversation_inventory_names_single_durable_owner() -> None:
    row = ontology_ownership_by_entity()["Conversation"]
    assert row.status.value == "done"
    assert row.authoritative_module == "runtime.messaging.conversation_registry"
    assert row.storage_owner == "runtime.platform.event_store"
    assert row.allowed_writers == ("runtime.messaging.conversation_registry",)
    assert row.allowed_readers == (
        "runtime.business_autonomy.provider_inbound_webhook_service",
        "runtime.messaging.router_contract",
    )


def test_conversation_lifecycle_owner_marker_is_unique() -> None:
    owners: list[Path] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if any(
                isinstance(target, ast.Name)
                and target.id == "CANON_CONVERSATION_LIFECYCLE_OWNER"
                for target in node.targets
            ) and isinstance(node.value, ast.Constant) and node.value.value is True:
                owners.append(path.relative_to(ROOT))
    assert CANON_CONVERSATION_LIFECYCLE_OWNER is True
    assert owners == [OWNER]


def test_conversation_owner_reuses_canonical_event_fact_mutation() -> None:
    source = (ROOT / OWNER).read_text(encoding="utf-8")
    assert "EventFactLifecycleWriter" in source
    assert "BUSINESS_FACT_EVENT_TYPE" in source
    assert 'source="conversation_registry"' in source
    assert "CONVERSATION_SCHEMA_VERSION = 1" in source


def test_unified_conversation_router_remains_pure_projection() -> None:
    router = (ROOT / "runtime/messaging/router.py").read_text(encoding="utf-8")
    contract = (ROOT / "runtime/messaging/router_contract.py").read_text(encoding="utf-8")
    combined = router + contract
    assert "ConversationRegistry" not in combined
    assert "EventFactLifecycleWriter" not in combined
    assert "event_store" not in combined
    assert "ConversationRoute" in combined


def test_business_ontology_runtime_wires_conversation_to_existing_stores_and_customer() -> None:
    wiring = (ROOT / "runtime/business_autonomy/ontology_runtime.py").read_text(encoding="utf-8")
    assert '"_conversation_registry"' in wiring
    assert "ConversationRegistry(" in wiring
    assert "event_store=event_store" in wiring
    assert "idempotency_store=idempotency_store" in wiring
    assert "customer_registry=customer_registry" in wiring


def test_provider_ingress_records_customer_then_conversation_before_decision_handoff() -> None:
    source = (ROOT / "runtime/business_autonomy/provider_inbound_webhook_service.py").read_text(encoding="utf-8")
    customer = source.index("self.customer_registry.record_contact(")
    conversation = source.index("self.conversation_registry.ensure_ingress(")
    decision = source.index("self.inbound_processor.process(handoff=handoff)")
    assert customer < conversation < decision
    assert "'conversation_id': conversation_id" in source
