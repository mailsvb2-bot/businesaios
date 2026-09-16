from __future__ import annotations

import pytest

from application.artifact import (
    ArtifactHistoryInvariantViolation,
    ArtifactProjector,
    ArtifactRegistry,
)
from contracts.artifact import ArtifactNotFound, ArtifactStatus
from contracts.event_store import BusinessFactV1
from reliability.idempotency_store import InMemoryIdempotencyStore


class MemoryEventStore:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def append_event(self, event: dict) -> None:
        self.events.append(dict(event))

    def iter_events(
        self, *, tenant_id: str, start_ms: int, end_ms=None, user_id=None, event_type=None
    ):
        for event in self.events:
            if str(event.get("tenant_id") or "") != str(tenant_id):
                continue
            if int(event.get("timestamp_ms") or 0) < int(start_ms):
                continue
            if end_ms is not None and int(event.get("timestamp_ms") or 0) > int(end_ms):
                continue
            if event_type is not None and str(event.get("event_type") or "") != str(event_type):
                continue
            yield dict(event)

    def count_events(
        self, *, tenant_id: str, start_ms: int, end_ms: int, user_id=None, event_type=None
    ) -> int:
        return sum(
            1
            for _ in self.iter_events(
                tenant_id=tenant_id,
                start_ms=start_ms,
                end_ms=end_ms,
                user_id=user_id,
                event_type=event_type,
            )
        )


def _registry() -> tuple[ArtifactRegistry, MemoryEventStore]:
    events = MemoryEventStore()
    return ArtifactRegistry(
        event_store=events, idempotency_store=InMemoryIdempotencyStore()
    ), events


def test_artifact_create_is_immutable_scoped_metadata_with_exact_replay() -> None:
    registry, events = _registry()
    digest = "A" * 64
    created = registry.create(
        tenant_id="tenant-a",
        business_id="business-a",
        artifact_id="artifact-a",
        idempotency_key="create-a",
        artifact_kind="report",
        storage_ref="blob:reports/2026/a.pdf",
        content_sha256=digest,
        media_type="application/pdf",
        occurred_at_ms=100,
    )
    assert created.status is ArtifactStatus.ACTIVE
    assert created.content_sha256 == digest.lower()
    assert len(events.events) == 1

    replay = registry.create(
        tenant_id="tenant-a",
        business_id="business-a",
        artifact_id="artifact-a",
        idempotency_key="create-a",
        artifact_kind="report",
        storage_ref="blob:reports/2026/a.pdf",
        content_sha256=digest.lower(),
        media_type="application/pdf",
        occurred_at_ms=999,
    )
    assert replay == created
    assert len(events.events) == 1


def test_artifact_rejects_silent_overwrite_and_new_create_key() -> None:
    registry, events = _registry()
    registry.create(
        tenant_id="tenant-a", business_id="business-a", artifact_id="artifact-a",
        idempotency_key="create-a", storage_ref="blob:a", occurred_at_ms=100,
    )
    with pytest.raises(ValueError, match="different immutable metadata"):
        registry.create(
            tenant_id="tenant-a", business_id="business-a", artifact_id="artifact-a",
            idempotency_key="create-a", storage_ref="blob:b", occurred_at_ms=200,
        )
    with pytest.raises(ValueError, match="create idempotency key"):
        registry.create(
            tenant_id="tenant-a", business_id="business-a", artifact_id="artifact-a",
            idempotency_key="create-b", storage_ref="blob:a", occurred_at_ms=200,
        )
    assert len(events.events) == 1


def test_artifact_archive_is_terminal_and_exactly_replayable() -> None:
    registry, events = _registry()
    registry.create(
        tenant_id="tenant-a", business_id="business-a", artifact_id="artifact-a",
        idempotency_key="create", occurred_at_ms=100,
    )
    archived = registry.archive(
        tenant_id="tenant-a", business_id="business-a", artifact_id="artifact-a",
        idempotency_key="archive", occurred_at_ms=200,
    )
    assert archived.status is ArtifactStatus.ARCHIVED
    assert archived.archived_at_ms == 200
    replay = registry.archive(
        tenant_id="tenant-a", business_id="business-a", artifact_id="artifact-a",
        idempotency_key="archive", occurred_at_ms=999,
    )
    assert replay == archived
    with pytest.raises(ValueError, match="another idempotency key"):
        registry.archive(
            tenant_id="tenant-a", business_id="business-a", artifact_id="artifact-a",
            idempotency_key="archive-other", occurred_at_ms=1000,
        )
    assert len(events.events) == 2


def test_artifact_projection_is_tenant_and_business_scoped() -> None:
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    registry = ArtifactRegistry(event_store=events, idempotency_store=claims)
    registry.create(
        tenant_id="tenant-a", business_id="business-a", artifact_id="shared",
        idempotency_key="a", artifact_kind="report", occurred_at_ms=100,
    )
    registry.create(
        tenant_id="tenant-b", business_id="business-b", artifact_id="shared",
        idempotency_key="b", artifact_kind="model", occurred_at_ms=100,
    )
    projector = ArtifactProjector(events)
    assert projector.get(
        tenant_id="tenant-a", business_id="business-a", artifact_id="shared"
    ).artifact_kind == "report"
    assert projector.get(
        tenant_id="tenant-b", business_id="business-b", artifact_id="shared"
    ).artifact_kind == "model"
    with pytest.raises(ArtifactNotFound):
        projector.get(tenant_id="tenant-a", business_id="business-b", artifact_id="shared")


def test_artifact_sha256_validation_is_fail_closed() -> None:
    registry, _ = _registry()
    with pytest.raises(ValueError, match="64-character hexadecimal"):
        registry.create(
            tenant_id="tenant-a", business_id="business-a", artifact_id="artifact-a",
            idempotency_key="create", content_sha256="not-a-digest", occurred_at_ms=100,
        )


def test_artifact_projector_rejects_duplicate_create_history() -> None:
    events = MemoryEventStore()
    for fact_id, when in (("a:create:1", 100), ("a:create:2", 101)):
        events.append_event(BusinessFactV1(
            fact_id=fact_id, tenant_id="tenant-a", business_id="business-a",
            fact_type="artifact.created", entity_id="artifact-a",
            event_time_ms=when, observed_at_ms=when, source="artifact_registry",
            payload={"artifact_kind": "report"},
        ).as_event())
    with pytest.raises(ArtifactHistoryInvariantViolation, match="multiple create"):
        ArtifactProjector(events).get(
            tenant_id="tenant-a", business_id="business-a", artifact_id="artifact-a"
        )


def test_artifact_projector_rejects_history_after_archive() -> None:
    events = MemoryEventStore()
    for fact_id, fact_type, when in (
        ("a:create", "artifact.created", 100),
        ("a:archive", "artifact.archived", 200),
        ("a:archive:duplicate", "artifact.archived", 300),
    ):
        events.append_event(BusinessFactV1(
            fact_id=fact_id, tenant_id="tenant-a", business_id="business-a",
            fact_type=fact_type, entity_id="artifact-a", event_time_ms=when,
            observed_at_ms=when, source="artifact_registry",
            payload={"artifact_kind": "report"} if fact_type == "artifact.created" else {},
        ).as_event())
    with pytest.raises(ArtifactHistoryInvariantViolation, match="after archive"):
        ArtifactProjector(events).get(
            tenant_id="tenant-a", business_id="business-a", artifact_id="artifact-a"
        )
