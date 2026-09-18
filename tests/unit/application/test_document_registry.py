from __future__ import annotations

import pytest

from application.artifact import ArtifactRegistry
from application.document import DocumentHistoryInvariantViolation, DocumentProjector, DocumentRegistry
from contracts.document import DocumentNotFound, DocumentStatus
from contracts.event_store import BusinessFactV1, canonical_business_event_contract
from reliability.idempotency_store import InMemoryIdempotencyStore


class MemoryEventStore:
    def __init__(self) -> None:
        self.events: list[dict] = []
    def append_event(self, event: dict) -> None:
        self.events.append(dict(event))
    def iter_events(self, *, tenant_id: str, start_ms: int, end_ms=None, user_id=None, event_type=None):
        for event in self.events:
            if str(event.get('tenant_id') or '') != str(tenant_id):
                continue
            if int(event.get('timestamp_ms') or 0) < int(start_ms):
                continue
            if end_ms is not None and int(event.get('timestamp_ms') or 0) > int(end_ms):
                continue
            if event_type is not None and str(event.get('event_type') or '') != str(event_type):
                continue
            yield dict(event)
    def count_events(self, *, tenant_id: str, start_ms: int, end_ms: int, user_id=None, event_type=None) -> int:
        return sum(1 for _ in self.iter_events(tenant_id=tenant_id, start_ms=start_ms, end_ms=end_ms, user_id=user_id, event_type=event_type))


def _setup():
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    artifacts = ArtifactRegistry(event_store=events, idempotency_store=claims)
    documents = DocumentRegistry(event_store=events, idempotency_store=claims)
    return events, artifacts, documents


def test_document_revision_points_to_new_immutable_artifact() -> None:
    events, artifacts, documents = _setup()
    artifacts.create(tenant_id='t', business_id='b', artifact_id='a1', idempotency_key='a1', occurred_at_ms=100)
    artifacts.create(tenant_id='t', business_id='b', artifact_id='a2', idempotency_key='a2', occurred_at_ms=110)
    created = documents.create(tenant_id='t', business_id='b', document_id='d1', artifact_id='a1', idempotency_key='d1', title='Policy', occurred_at_ms=120)
    assert created.revision == 1 and created.artifact_id == 'a1'
    revised = documents.revise(tenant_id='t', business_id='b', document_id='d1', artifact_id='a2', idempotency_key='r1', occurred_at_ms=200)
    assert revised.revision == 2 and revised.artifact_id == 'a2'
    replay = documents.revise(tenant_id='t', business_id='b', document_id='d1', artifact_id='a2', idempotency_key='r1', occurred_at_ms=999)
    assert replay == revised
    assert len([e for e in events.events if str(dict(e.get('payload') or {}).get('fact_type') or '').startswith('document.')]) == 2


def test_document_metadata_propagates_and_exact_replay_rejects_change() -> None:
    events, artifacts, documents = _setup()
    artifacts.create( tenant_id="t", business_id="b", artifact_id="a1", idempotency_key="a1", occurred_at_ms=100, )
    artifacts.create( tenant_id="t", business_id="b", artifact_id="a2", idempotency_key="a2", occurred_at_ms=110, )
    create_metadata = {"actor_id": "owner-1", "decision_id": "decision-create"}
    created = documents.create( tenant_id="t", business_id="b", document_id="d", artifact_id="a1", idempotency_key="create-meta", title="Policy", occurred_at_ms=120, event_metadata=create_metadata, )
    assert documents.create( tenant_id="t", business_id="b", document_id="d", artifact_id="a1", idempotency_key="create-meta", title="Policy", occurred_at_ms=999, event_metadata=create_metadata, ) == created
    document_created = next( event for event in events.events if str(dict(event.get("payload") or {}).get("fact_type") or "") == "document.created" )
    assert canonical_business_event_contract(document_created)["actor_id"] == "owner-1"
    with pytest.raises(ValueError, match="event metadata"):
        documents.create( tenant_id="t", business_id="b", document_id="d", artifact_id="a1", idempotency_key="create-meta", title="Policy", occurred_at_ms=120, event_metadata={**create_metadata, "actor_id": "owner-2"}, )
    revise_metadata = {"actor_id": "owner-1", "decision_id": "decision-revise"}
    revised = documents.revise( tenant_id="t", business_id="b", document_id="d", artifact_id="a2", idempotency_key="revise-meta", occurred_at_ms=200, event_metadata=revise_metadata, )
    assert documents.revise( tenant_id="t", business_id="b", document_id="d", artifact_id="a2", idempotency_key="revise-meta", occurred_at_ms=999, event_metadata=revise_metadata, ) == revised
    with pytest.raises(ValueError, match="event metadata"):
        documents.revise( tenant_id="t", business_id="b", document_id="d", artifact_id="a2", idempotency_key="revise-meta", occurred_at_ms=200, event_metadata={**revise_metadata, "actor_id": "owner-2"}, )
    archive_metadata = {"actor_id": "owner-1", "decision_id": "decision-archive"}
    archived = documents.archive( tenant_id="t", business_id="b", document_id="d", idempotency_key="archive-meta", occurred_at_ms=300, event_metadata=archive_metadata, )
    assert documents.archive( tenant_id="t", business_id="b", document_id="d", idempotency_key="archive-meta", occurred_at_ms=999, event_metadata=archive_metadata, ) == archived
    with pytest.raises(ValueError, match="event metadata"):
        documents.archive( tenant_id="t", business_id="b", document_id="d", idempotency_key="archive-meta", occurred_at_ms=300, event_metadata={**archive_metadata, "actor_id": "owner-2"}, )


def test_document_rejects_missing_or_archived_artifact() -> None:
    _, artifacts, documents = _setup()
    with pytest.raises(Exception):
        documents.create(tenant_id='t', business_id='b', document_id='d', artifact_id='missing', idempotency_key='d')
    artifacts.create(tenant_id='t', business_id='b', artifact_id='a', idempotency_key='a', occurred_at_ms=100)
    artifacts.archive(tenant_id='t', business_id='b', artifact_id='a', idempotency_key='aa', occurred_at_ms=110)
    with pytest.raises(ValueError, match='active artifact'):
        documents.create(tenant_id='t', business_id='b', document_id='d', artifact_id='a', idempotency_key='d')


def test_document_archive_is_terminal_and_exactly_replayable() -> None:
    _, artifacts, documents = _setup()
    artifacts.create(tenant_id='t', business_id='b', artifact_id='a', idempotency_key='a', occurred_at_ms=100)
    documents.create(tenant_id='t', business_id='b', document_id='d', artifact_id='a', idempotency_key='d', occurred_at_ms=110)
    archived = documents.archive(tenant_id='t', business_id='b', document_id='d', idempotency_key='x', occurred_at_ms=200)
    assert archived.status is DocumentStatus.ARCHIVED
    assert documents.archive(tenant_id='t', business_id='b', document_id='d', idempotency_key='x', occurred_at_ms=999) == archived
    with pytest.raises(ValueError, match='another idempotency key'):
        documents.archive(tenant_id='t', business_id='b', document_id='d', idempotency_key='y', occurred_at_ms=1000)
    with pytest.raises(ValueError, match='archived document'):
        documents.revise(tenant_id='t', business_id='b', document_id='d', artifact_id='a', idempotency_key='z')


def test_document_projection_is_tenant_business_scoped() -> None:
    events, artifacts, documents = _setup()
    artifacts.create(tenant_id='t1', business_id='b1', artifact_id='a', idempotency_key='a1')
    artifacts.create(tenant_id='t2', business_id='b2', artifact_id='a', idempotency_key='a2')
    documents.create(tenant_id='t1', business_id='b1', document_id='d', artifact_id='a', idempotency_key='d1')
    documents.create(tenant_id='t2', business_id='b2', document_id='d', artifact_id='a', idempotency_key='d2')
    projector = DocumentProjector(events)
    assert projector.get(tenant_id='t1', business_id='b1', document_id='d').tenant_id == 't1'
    with pytest.raises(DocumentNotFound):
        projector.get(tenant_id='t1', business_id='b2', document_id='d')


def test_document_projector_rejects_invalid_revision_history() -> None:
    events = MemoryEventStore()
    for fact_id, fact_type, payload, when in (
        ('d:create', 'document.created', {'artifact_id': 'a1'}, 100),
        ('d:revise', 'document.revised', {'artifact_id': 'a1'}, 200),
    ):
        events.append_event(BusinessFactV1(fact_id=fact_id, tenant_id='t', business_id='b', fact_type=fact_type, entity_id='d', event_time_ms=when, observed_at_ms=when, source='document_registry', payload=payload).as_event())
    with pytest.raises(DocumentHistoryInvariantViolation, match='must change artifact_id'):
        DocumentProjector(events).get(tenant_id='t', business_id='b', document_id='d')
