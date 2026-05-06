from __future__ import annotations

from contracts.event_store import EventStore as EventStorePort
from contracts.event_store import EventStore as EventStoreProtocol
from runtime.platform.event_store.contract import EventStore, supports_event_store
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def test_event_store_contract_aliases_are_canonical() -> None:
    assert EventStorePort is EventStore
    assert EventStoreProtocol is EventStore


def test_memory_event_store_satisfies_canonical_contract() -> None:
    store = MemoryEventStore()
    assert supports_event_store(store) is True
