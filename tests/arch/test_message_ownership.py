from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

import pytest

from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity
from contracts.messaging_event_identity import (
    CANON_MESSAGE_SEMANTIC_OWNER,
    MESSAGE_SCHEMA_VERSION,
    MessageDirection,
    MessageIdentity,
)
from runtime.messaging.inbound_message import InboundMessage
from runtime.messaging.message_registry import CANON_MESSAGE_LIFECYCLE_OWNER, Message
from runtime.messaging.outbound_message import OutboundMessage

ROOT = Path(__file__).resolve().parents[2]
SEMANTIC_OWNER = Path("contracts/messaging_event_identity.py")
LIFECYCLE_OWNER = Path("runtime/messaging/message_registry.py")
PRODUCTION_ROOTS = ("contracts", "application", "runtime", "storage", "core", "adapters", "billing", "crm", "products")


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def _marker_owners(marker: str) -> list[Path]:
    owners: list[Path] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
                continue
            if node.value.value is True and any(isinstance(t, ast.Name) and t.id == marker for t in node.targets):
                owners.append(path.relative_to(ROOT))
    return owners


def test_message_inventory_names_single_durable_owner() -> None:
    row = ontology_ownership_by_entity()["Message"]
    assert row.status is OwnershipAuditStatus.DONE
    assert row.authoritative_module == "runtime.messaging.message_registry"
    assert row.storage_owner == "runtime.platform.event_store"
    assert row.allowed_writers == ("runtime.messaging.message_registry",)
    assert row.allowed_readers == (
        "runtime.messaging.inbound_message",
        "runtime.messaging.outbound_message",
        "runtime.business_autonomy.provider_inbound_webhook_service",
        "runtime._internal.effects_actions.telegram.messaging_parts.transport",
    )


def test_message_semantic_and_lifecycle_owner_markers_are_unique() -> None:
    assert CANON_MESSAGE_SEMANTIC_OWNER is True
    assert CANON_MESSAGE_LIFECYCLE_OWNER is True
    assert _marker_owners("CANON_MESSAGE_SEMANTIC_OWNER") == [SEMANTIC_OWNER]
    assert _marker_owners("CANON_MESSAGE_LIFECYCLE_OWNER") == [LIFECYCLE_OWNER]


def test_message_contract_and_durable_entity_are_pii_free_and_schema_versioned() -> None:
    identity_names = {field.name for field in fields(MessageIdentity)}
    entity_names = {field.name for field in fields(Message)}
    forbidden = {"text", "user_id", "email", "phone", "payload", "attachments", "body"}
    assert identity_names.isdisjoint(forbidden)
    assert entity_names.isdisjoint(forbidden)
    assert MESSAGE_SCHEMA_VERSION == 1
    with pytest.raises(ValueError, match="MESSAGE_SCHEMA_VERSION_UNSUPPORTED"):
        MessageIdentity(message_id="m", tenant_id="t", channel="telegram", direction=MessageDirection.INBOUND, schema_version=2)


def test_inbound_and_outbound_project_same_identity_type() -> None:
    inbound = InboundMessage(tenant_id="t", channel="telegram", user_id="u", text="hello", transport_message_id="provider-1")
    outbound = OutboundMessage(decision_id="d", correlation_id="c", tenant_id="t", business_id="b", user_id="u", channel="telegram", text="reply")
    assert type(inbound.canonical_identity) is MessageIdentity
    assert type(outbound.canonical_identity) is MessageIdentity
    assert inbound.canonical_identity.direction is MessageDirection.INBOUND
    assert outbound.canonical_identity.direction is MessageDirection.OUTBOUND
    assert outbound.canonical_identity.message_id == outbound.delivery_key


def test_message_owner_reuses_canonical_event_fact_mutation() -> None:
    source = (ROOT / LIFECYCLE_OWNER).read_text(encoding="utf-8")
    assert "EventFactLifecycleWriter" in source
    assert "BUSINESS_FACT_EVENT_TYPE" in source
    assert 'source="message_registry"' in source
    assert "MESSAGE_SCHEMA_VERSION" in source
    assert '"text"' not in source


def test_business_ontology_runtime_wires_message_to_existing_stores() -> None:
    wiring = (ROOT / "runtime/business_autonomy/ontology_runtime.py").read_text(encoding="utf-8")
    assert '"_message_registry"' in wiring
    assert "MessageRegistry(" in wiring
    assert "event_store=event_store" in wiring
    assert "idempotency_store=idempotency_store" in wiring


def test_live_inbound_and_outbound_persist_before_semantic_side_effects() -> None:
    inbound = (ROOT / "runtime/business_autonomy/provider_inbound_webhook_service.py").read_text(encoding="utf-8")
    customer = inbound.index("self.customer_registry.record_contact(")
    conversation = inbound.index("self.conversation_registry.ensure_ingress(")
    message = inbound.index("self.message_registry.record(")
    decision = inbound.index("self.inbound_processor.process(handoff=handoff)")
    assert customer < conversation < message < decision

    outbound = (ROOT / "runtime/_internal/effects_actions/telegram/messaging_parts/transport.py").read_text(encoding="utf-8")
    record = outbound.index("_record_business_message(self, selected_msg)")
    telegram = outbound.index("telegram_delivery(self, msg=selected_msg)", record)
    multichannel = outbound.index("multichannel_delivery(self, msg=selected_msg", record)
    assert record < telegram and record < multichannel
