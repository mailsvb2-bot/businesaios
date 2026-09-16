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
from runtime.messaging.outbound_message import OutboundMessage

ROOT = Path(__file__).resolve().parents[2]
OWNER = Path("contracts/messaging_event_identity.py")


def _production_python_files():
    for root_name in ("contracts", "application", "runtime", "storage", "core", "adapters", "billing", "crm", "products"):
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_message_inventory_names_one_partial_semantic_owner() -> None:
    row = ontology_ownership_by_entity()["Message"]
    assert row.status is OwnershipAuditStatus.PARTIAL
    assert row.authoritative_module == "contracts.messaging_event_identity"
    assert row.storage_owner is None
    assert row.allowed_writers == ()
    assert row.allowed_readers == (
        "runtime.messaging.inbound_message",
        "runtime.messaging.outbound_message",
    )


def test_message_semantic_owner_marker_is_unique() -> None:
    owners: list[Path] = []
    for path in _production_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
                continue
            if node.value.value is not True:
                continue
            if any(isinstance(target, ast.Name) and target.id == "CANON_MESSAGE_SEMANTIC_OWNER" for target in node.targets):
                owners.append(path.relative_to(ROOT))
    assert CANON_MESSAGE_SEMANTIC_OWNER is True
    assert owners == [OWNER]


def test_message_identity_is_pii_free_and_schema_versioned() -> None:
    names = {field.name for field in fields(MessageIdentity)}
    assert names.isdisjoint({"text", "user_id", "email", "phone", "payload", "attachments"})
    assert MESSAGE_SCHEMA_VERSION == 1
    with pytest.raises(ValueError, match="MESSAGE_SCHEMA_VERSION_UNSUPPORTED"):
        MessageIdentity(
            message_id="m-1",
            tenant_id="tenant-1",
            channel="telegram",
            direction=MessageDirection.INBOUND,
            schema_version=2,
        )


def test_inbound_and_outbound_project_same_canonical_identity_type() -> None:
    inbound = InboundMessage(
        tenant_id="tenant-1",
        channel="telegram",
        user_id="user-1",
        text="hello",
        transport_message_id="provider-1",
    )
    outbound = OutboundMessage(
        decision_id="decision-1",
        correlation_id="corr-1",
        tenant_id="tenant-1",
        business_id="business-1",
        user_id="user-1",
        channel="telegram",
        text="reply",
    )
    inbound_identity = inbound.canonical_identity
    outbound_identity = outbound.canonical_identity
    assert type(inbound_identity) is MessageIdentity
    assert type(outbound_identity) is MessageIdentity
    assert inbound_identity.direction is MessageDirection.INBOUND
    assert inbound_identity.message_id == "provider-1"
    assert outbound_identity.direction is MessageDirection.OUTBOUND
    assert outbound_identity.business_id == "business-1"
    assert outbound_identity.message_id == outbound.delivery_key


def test_inbound_identity_fallback_is_stable_without_provider_id() -> None:
    message = InboundMessage(tenant_id="tenant-1", channel="vk", user_id="user-1", text="same")
    assert message.canonical_identity.message_id == message.canonical_identity.message_id
    assert message.canonical_identity.message_id.startswith("synthetic-vk-")
