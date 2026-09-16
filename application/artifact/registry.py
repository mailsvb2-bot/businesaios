from __future__ import annotations

import time
from typing import Any

from application.artifact.projector import ARTIFACT_ARCHIVED, ARTIFACT_CREATED, ArtifactProjector
from application.ontology import EventFactLifecycleWriter
from contracts.artifact import Artifact, ArtifactStatus
from reliability.idempotency_contract import IdempotencyStore

CANON_ARTIFACT_LIFECYCLE_OWNER = True


class ArtifactRegistry:
    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = ArtifactProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store,
            idempotency_store=idempotency_store,
            namespace="artifact_fact",
            source="artifact_registry",
            id_prefix="artifact",
        )

    @staticmethod
    def _time(value: int | None) -> int:
        return int(time.time() * 1000) if value is None else max(0, int(value))

    def create(
        self, *, tenant_id: str, business_id: str, artifact_id: str, idempotency_key: str,
        artifact_kind: str | None = None, storage_ref: str | None = None,
        content_sha256: str | None = None, media_type: str | None = None,
        occurred_at_ms: int | None = None,
    ) -> Artifact:
        when = self._time(occurred_at_ms)
        candidate = Artifact(
            artifact_id=artifact_id,
            tenant_id=tenant_id,
            business_id=business_id,
            artifact_kind=artifact_kind,
            storage_ref=storage_ref,
            content_sha256=content_sha256,
            media_type=media_type,
            created_at_ms=when,
            updated_at_ms=when,
        )
        payload = {
            "artifact_kind": candidate.artifact_kind,
            "storage_ref": candidate.storage_ref,
            "content_sha256": candidate.content_sha256,
            "media_type": candidate.media_type,
        }
        try:
            current = self._projector.get(
                tenant_id=tenant_id, business_id=business_id, artifact_id=artifact_id
            )
        except LookupError:
            current = None
        if current is not None:
            if (
                current.artifact_kind != candidate.artifact_kind
                or current.storage_ref != candidate.storage_ref
                or current.content_sha256 != candidate.content_sha256
                or current.media_type != candidate.media_type
            ):
                raise ValueError("artifact already exists with different immutable metadata")
            repaired = self._writer.repair_existing(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=artifact_id,
                operation="create",
                idempotency_key=idempotency_key,
                fact_type=ARTIFACT_CREATED,
                payload=payload,
            )
            if not repaired:
                raise ValueError("artifact already exists and create idempotency key does not match")
            return current
        self._writer.append_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=artifact_id,
            operation="create",
            idempotency_key=idempotency_key,
            fact_type=ARTIFACT_CREATED,
            payload=payload,
            occurred_at_ms=when,
        )
        return self._projector.get(
            tenant_id=tenant_id, business_id=business_id, artifact_id=artifact_id
        )

    def archive(
        self, *, tenant_id: str, business_id: str, artifact_id: str, idempotency_key: str,
        occurred_at_ms: int | None = None,
    ) -> Artifact:
        current = self._projector.get(
            tenant_id=tenant_id, business_id=business_id, artifact_id=artifact_id
        )
        if current.status is ArtifactStatus.ARCHIVED:
            repaired = self._writer.repair_existing(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=artifact_id,
                operation="archive",
                idempotency_key=idempotency_key,
                fact_type=ARTIFACT_ARCHIVED,
                payload={},
            )
            if not repaired:
                raise ValueError("artifact already archived with another idempotency key")
            return current
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_transition_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=artifact_id,
            expected_state_token=f"{current.status.value}:{current.updated_at_ms}",
            operation="archive",
            idempotency_key=idempotency_key,
            fact_type=ARTIFACT_ARCHIVED,
            payload={},
            occurred_at_ms=when,
        )
        return self._projector.get(
            tenant_id=tenant_id, business_id=business_id, artifact_id=artifact_id
        )

    def get(self, *, tenant_id: str, business_id: str, artifact_id: str) -> Artifact:
        return self._projector.get(
            tenant_id=tenant_id, business_id=business_id, artifact_id=artifact_id
        )

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Artifact, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)


__all__ = ["ArtifactRegistry", "CANON_ARTIFACT_LIFECYCLE_OWNER"]
