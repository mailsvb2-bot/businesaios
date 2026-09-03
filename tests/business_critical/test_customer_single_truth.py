from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from contracts.customer import CustomerIdentityConflict, CustomerIdentityStatus, CustomerNotFound, CustomerStatus
from contracts.event_store import BusinessFactV1
from crm import CustomerRegistry, CustomerTimelineProjector
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from security.secret_vault import InMemorySecretVault


def _registry():
    events = MemoryEventStore()
    return CustomerRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore(), pii_vault=InMemorySecretVault()), events


def test_same_identity_is_idempotent_and_single_customer_truth() -> None:
    registry, events = _registry()
    first = registry.ensure_customer_identity(tenant_id="t-1", business_id="b-1", channel="telegram", external_subject="123", display_name="Anna", occurred_at_ms=100)
    second = registry.ensure_customer_identity(tenant_id="t-1", business_id="b-1", channel="telegram", external_subject="123", display_name="Changed", occurred_at_ms=200)
    assert second.customer.customer_id == first.customer.customer_id
    assert len(second.identities) == 1
    facts = list(events.iter_events(tenant_id="t-1", start_ms=0))
    assert [row["payload"]["fact_type"] for row in facts] == ["customer.created", "customer.identity.attached"]


def test_identity_conflict_fails_closed_and_cross_business_is_independent() -> None:
    registry, _ = _registry()
    first = registry.ensure_customer_identity(tenant_id="t-1", business_id="b-1", channel="vk", external_subject="u-1", occurred_at_ms=100)
    other = registry.ensure_customer_identity(tenant_id="t-1", business_id="b-2", channel="vk", external_subject="u-1", occurred_at_ms=100)
    assert other.customer.customer_id != first.customer.customer_id
    second_customer = registry.ensure_customer_identity(tenant_id="t-1", business_id="b-1", channel="vk", external_subject="u-2", occurred_at_ms=101)
    with pytest.raises(CustomerIdentityConflict):
        registry.attach_identity(tenant_id="t-1", business_id="b-1", customer_id=second_customer.customer.customer_id, channel="vk", external_subject="u-1", occurred_at_ms=102)


def test_identity_normalization_and_explicit_cross_channel_link() -> None:
    registry, _ = _registry()
    record = registry.ensure_customer_identity(tenant_id="t-1", business_id="b-1", channel="EMAIL", external_subject="Person@Example.COM", occurred_at_ms=100)
    same = registry.find_by_identity(tenant_id="t-1", business_id="b-1", channel="email", external_subject="person@example.com")
    assert same.customer.customer_id == record.customer.customer_id
    phone = registry.attach_identity(tenant_id="t-1", business_id="b-1", customer_id=record.customer.customer_id, channel="phone", external_subject="+372 (555) 1234", occurred_at_ms=110)
    assert phone.external_subject == "3725551234"
    assert {item.channel for item in registry.get_customer(tenant_id="t-1", business_id="b-1", customer_id=record.customer.customer_id).identities} == {"email", "phone"}


def test_contact_is_idempotent_and_archive_revokes_all_identity_routes() -> None:
    registry, _ = _registry()
    record = registry.ensure_customer_identity(tenant_id="t-1", business_id="b-1", channel="max", external_subject="42", occurred_at_ms=100)
    customer_id = record.customer.customer_id
    registry.record_contact(tenant_id="t-1", business_id="b-1", customer_id=customer_id, channel="max", external_subject="42", contact_id="msg-1", display_name="A", occurred_at_ms=120)
    registry.record_contact(tenant_id="t-1", business_id="b-1", customer_id=customer_id, channel="max", external_subject="42", contact_id="msg-1", display_name="B", occurred_at_ms=130)
    current = registry.get_customer(tenant_id="t-1", business_id="b-1", customer_id=customer_id)
    assert current.identities[0].last_contact_at_ms == 120
    archived = registry.archive_customer(tenant_id="t-1", business_id="b-1", customer_id=customer_id, occurred_at_ms=140)
    assert archived.status is CustomerStatus.ARCHIVED
    current = registry.get_customer(tenant_id="t-1", business_id="b-1", customer_id=customer_id)
    assert all(identity.status is CustomerIdentityStatus.REVOKED for identity in current.identities)
    with pytest.raises(CustomerIdentityConflict):
        registry.attach_identity(tenant_id="t-1", business_id="b-1", customer_id=customer_id, channel="telegram", external_subject="99", occurred_at_ms=150)


def test_timeline_is_read_only_tenant_business_scoped_projection() -> None:
    registry, events = _registry()
    record = registry.ensure_customer_identity(tenant_id="t-1", business_id="b-1", channel="telegram", external_subject="1", occurred_at_ms=100)
    customer_id = record.customer.customer_id
    registry.record_contact(tenant_id="t-1", business_id="b-1", customer_id=customer_id, channel="telegram", external_subject="1", contact_id="m-1", occurred_at_ms=110)
    events.append_event({"event_id": "pay-1", "tenant_id": "t-1", "source": "payments", "event_type": "payment_succeeded", "timestamp_ms": 120, "payload": {"business_id": "b-1", "customer_id": customer_id, "amount_minor": 2500, "currency": "eur"}})
    events.append_event({"event_id": "foreign", "tenant_id": "t-1", "source": "payments", "event_type": "payment_succeeded", "timestamp_ms": 125, "payload": {"business_id": "b-2", "customer_id": customer_id, "amount_minor": 9999, "currency": "EUR"}})
    before = len(events)
    timeline = CustomerTimelineProjector(events).get(tenant_id="t-1", business_id="b-1", customer_id=customer_id)
    assert len(events) == before
    assert [entry.source_id for entry in timeline.entries][-1] == "pay-1"
    assert all(entry.source_id != "foreign" for entry in timeline.entries)
    assert timeline.entries[-1].amount_minor == 2500
    assert timeline.entries[-1].currency == "EUR"
    with pytest.raises(CustomerNotFound):
        CustomerTimelineProjector(events).get(tenant_id="t-1", business_id="missing", customer_id=customer_id)


def test_timeline_rejects_malformed_money_instead_of_inventing_value() -> None:
    registry, events = _registry()
    record = registry.ensure_customer_identity(tenant_id="t", business_id="b", channel="telegram", external_subject="1", occurred_at_ms=100)
    events.append_event({"event_id": "bad-money", "tenant_id": "t", "source": "payments", "event_type": "payment_succeeded", "timestamp_ms": 120, "payload": {"business_id": "b", "customer_id": record.customer.customer_id, "amount_minor": 5, "currency": ""}})
    with pytest.raises(RuntimeError):
        CustomerTimelineProjector(events).get(tenant_id="t", business_id="b", customer_id=record.customer.customer_id)


def test_customer_facts_remain_business_fact_spine_events() -> None:
    registry, events = _registry()
    record = registry.ensure_customer_identity(tenant_id="t", business_id="b", channel="telegram", external_subject="1", occurred_at_ms=100)
    raw = list(events.iter_events(tenant_id="t", start_ms=0))
    assert all(row["event_type"] == "business_fact.v1" for row in raw)
    # This constructor remains the semantic event contract; the registry adds no second event schema.
    assert BusinessFactV1.__module__ == "contracts.event_store"
    assert record.customer.business_id == "b"


def test_concurrent_identity_ingress_never_splits_customer_truth() -> None:
    from contracts.customer import CustomerIdentityBusy

    registry, events = _registry()

    def ensure(_: int):
        try:
            return registry.ensure_customer_identity(tenant_id="t-race", business_id="b-race", channel="telegram", external_subject="same", occurred_at_ms=100).customer.customer_id
        except CustomerIdentityBusy:
            return None

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(ensure, range(40)))
    final = registry.ensure_customer_identity(tenant_id="t-race", business_id="b-race", channel="telegram", external_subject="same", occurred_at_ms=101)
    successful = {value for value in results if value is not None}
    assert successful <= {final.customer.customer_id}
    facts = [row["payload"]["fact_type"] for row in events.iter_events(tenant_id="t-race", start_ms=0)]
    assert facts.count("customer.created") == 1
    assert facts.count("customer.identity.attached") == 1


def test_archived_identity_cannot_silently_reactivate_on_new_ingress() -> None:
    registry, _ = _registry()
    record = registry.ensure_customer_identity(tenant_id="t", business_id="b", channel="vk", external_subject="archived", occurred_at_ms=100)
    registry.archive_customer(tenant_id="t", business_id="b", customer_id=record.customer.customer_id, occurred_at_ms=110)
    with pytest.raises(CustomerIdentityConflict):
        registry.ensure_customer_identity(tenant_id="t", business_id="b", channel="vk", external_subject="archived", occurred_at_ms=120)
    with pytest.raises(CustomerIdentityConflict):
        registry.record_contact(tenant_id="t", business_id="b", customer_id=record.customer.customer_id, channel="vk", external_subject="archived", contact_id="after-archive", occurred_at_ms=120)


def test_customer_raw_pii_never_enters_event_spine_and_vault_hydrates_identity() -> None:
    import json

    events = MemoryEventStore()
    vault = InMemorySecretVault()
    registry = CustomerRegistry(
        event_store=events,
        idempotency_store=InMemoryIdempotencyStore(),
        pii_vault=vault,
    )
    record = registry.ensure_customer_identity(
        tenant_id="t-private",
        business_id="b-private",
        channel="email",
        external_subject="Person.Private@Example.COM",
        username="private_handle",
        display_name="Private Person",
        occurred_at_ms=100,
    )
    registry.record_contact(
        tenant_id="t-private",
        business_id="b-private",
        customer_id=record.customer.customer_id,
        channel="email",
        external_subject="person.private@example.com",
        contact_id="message-private-1",
        username="updated_private_handle",
        display_name="Updated Private Person",
        occurred_at_ms=110,
    )
    event_text = json.dumps(list(events), ensure_ascii=False, sort_keys=True)
    for raw_pii in (
        "Person.Private@Example.COM",
        "person.private@example.com",
        "private_handle",
        "updated_private_handle",
        "Private Person",
        "Updated Private Person",
    ):
        assert raw_pii not in event_text
    current = registry.get_customer(
        tenant_id="t-private",
        business_id="b-private",
        customer_id=record.customer.customer_id,
    )
    assert current.identities[0].external_subject == "person.private@example.com"
    assert current.identities[0].username == "updated_private_handle"
    assert current.identities[0].display_name == "Updated Private Person"
    stored = vault.list_records()
    assert len(stored) == 1
    assert b"person.private@example.com" not in stored[0].ciphertext
    assert b"updated_private_handle" not in stored[0].ciphertext


def test_customer_pii_revocation_deactivates_routing_material_and_projection_fails_closed() -> None:
    from contracts.customer import CustomerIdentityUnavailable

    events = MemoryEventStore()
    vault = InMemorySecretVault()
    registry = CustomerRegistry(
        event_store=events,
        idempotency_store=InMemoryIdempotencyStore(),
        pii_vault=vault,
    )
    record = registry.ensure_customer_identity(
        tenant_id="t-erase",
        business_id="b-erase",
        channel="phone",
        external_subject="+372 555 9911",
        display_name="Erase Me",
        occurred_at_ms=100,
    )
    assert registry.revoke_customer_pii(
        tenant_id="t-erase",
        business_id="b-erase",
        customer_id=record.customer.customer_id,
    ) == 1
    with pytest.raises(CustomerIdentityUnavailable):
        registry.get_customer(
            tenant_id="t-erase",
            business_id="b-erase",
            customer_id=record.customer.customer_id,
        )
    event_text = str(list(events))
    assert "3725559911" not in event_text
    assert "Erase Me" not in event_text
