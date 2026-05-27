from __future__ import annotations

from runtime.messaging_policy_readmodel.inmemory_store import InMemoryMessagingPolicySnapshotStore
from runtime.messaging_policy_readmodel.projector import MessagingPolicyProjector
from runtime.messaging_policy_readmodel.read_service import MessagingPolicyReadService
from runtime.messaging_policy_readmodel.rebuild_service import MessagingPolicyRebuildService
from runtime.messaging_policy_readmodel.repository import MessagingPolicySnapshotRepository


def build_messaging_policy_read_services(*, event_store):
    store = InMemoryMessagingPolicySnapshotStore()
    projector = MessagingPolicyProjector()
    repository = MessagingPolicySnapshotRepository(store=store)
    rebuild_service = MessagingPolicyRebuildService(
        event_store=event_store,
        projector=projector,
        repository=repository,
    )
    read_service = MessagingPolicyReadService(repository=repository, rebuild_service=rebuild_service)
    return {
        'store': store,
        'projector': projector,
        'repository': repository,
        'rebuild_service': rebuild_service,
        'read_service': read_service,
    }
