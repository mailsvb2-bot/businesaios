from __future__ import annotations

import time
from typing import Any

from application.artifact.projector import ArtifactProjector
from application.document.facts import DOCUMENT_ARCHIVED, DOCUMENT_CREATED, DOCUMENT_REVISED
from application.document.projector import DocumentProjector
from application.ontology import EventFactLifecycleWriter
from contracts.artifact import ArtifactStatus
from contracts.document import Document, DocumentStatus
from reliability.idempotency_contract import IdempotencyStore

CANON_DOCUMENT_LIFECYCLE_OWNER = True


class DocumentRegistry:
    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._artifacts = ArtifactProjector(event_store)
        self._projector = DocumentProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store,
            idempotency_store=idempotency_store,
            namespace="document_fact",
            source="document_registry",
            id_prefix="document",
        )

    @staticmethod
    def _time(value: int | None) -> int:
        return int(time.time() * 1000) if value is None else max(0, int(value))

    def _active_artifact(self, *, tenant_id: str, business_id: str, artifact_id: str) -> str:
        artifact = self._artifacts.get(
            tenant_id=tenant_id, business_id=business_id, artifact_id=artifact_id
        )
        if artifact.status is not ArtifactStatus.ACTIVE:
            raise ValueError("document requires active artifact")
        return artifact.artifact_id

    def create(
        self, *, tenant_id: str, business_id: str, document_id: str, artifact_id: str,
        idempotency_key: str, document_kind: str | None = None, title: str | None = None,
        occurred_at_ms: int | None = None,
    ) -> Document:
        bound_artifact = self._active_artifact(
            tenant_id=tenant_id, business_id=business_id, artifact_id=artifact_id
        )
        when = self._time(occurred_at_ms)
        candidate = Document(
            document_id=document_id,
            tenant_id=tenant_id,
            business_id=business_id,
            artifact_id=bound_artifact,
            document_kind=document_kind,
            title=title,
            created_at_ms=when,
            updated_at_ms=when,
        )
        payload = {
            "artifact_id": candidate.artifact_id,
            "document_kind": candidate.document_kind,
            "title": candidate.title,
        }
        try:
            current = self._projector.get(
                tenant_id=tenant_id, business_id=business_id, document_id=document_id
            )
        except LookupError:
            current = None
        if current is not None:
            if (
                current.artifact_id != candidate.artifact_id
                or current.document_kind != candidate.document_kind
                or current.title != candidate.title
            ):
                raise ValueError("document already exists with different identity metadata")
            repaired = self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=document_id,
                operation="create", idempotency_key=idempotency_key,
                fact_type=DOCUMENT_CREATED, payload=payload,
            )
            if not repaired:
                raise ValueError("document already exists and create idempotency key does not match")
            return current
        self._writer.append_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=document_id,
            operation="create", idempotency_key=idempotency_key,
            fact_type=DOCUMENT_CREATED, payload=payload, occurred_at_ms=when,
        )
        return self._projector.get(
            tenant_id=tenant_id, business_id=business_id, document_id=document_id
        )

    def revise(
        self, *, tenant_id: str, business_id: str, document_id: str, artifact_id: str,
        idempotency_key: str, occurred_at_ms: int | None = None,
    ) -> Document:
        current = self._projector.get(
            tenant_id=tenant_id, business_id=business_id, document_id=document_id
        )
        if current.status is DocumentStatus.ARCHIVED:
            raise ValueError("archived document cannot be revised")
        bound_artifact = self._active_artifact(
            tenant_id=tenant_id, business_id=business_id, artifact_id=artifact_id
        )
        payload = {"artifact_id": bound_artifact}
        if current.artifact_id == bound_artifact:
            repaired = self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=document_id,
                operation="revise", idempotency_key=idempotency_key,
                fact_type=DOCUMENT_REVISED, payload=payload,
            )
            if repaired:
                return current
            raise ValueError("document already references artifact with another revision key")
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_transition_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=document_id,
            expected_state_token=f"active:{current.revision}:{current.artifact_id}:{current.updated_at_ms}",
            operation="revise",
            idempotency_key=idempotency_key,
            fact_type=DOCUMENT_REVISED,
            payload=payload,
            occurred_at_ms=when,
        )
        return self._projector.get(
            tenant_id=tenant_id, business_id=business_id, document_id=document_id
        )

    def archive(
        self, *, tenant_id: str, business_id: str, document_id: str, idempotency_key: str,
        occurred_at_ms: int | None = None,
    ) -> Document:
        current = self._projector.get(
            tenant_id=tenant_id, business_id=business_id, document_id=document_id
        )
        if current.status is DocumentStatus.ARCHIVED:
            repaired = self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=document_id,
                operation="archive", idempotency_key=idempotency_key,
                fact_type=DOCUMENT_ARCHIVED, payload={},
            )
            if not repaired:
                raise ValueError("document already archived with another idempotency key")
            return current
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_transition_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=document_id,
            expected_state_token=f"active:{current.revision}:{current.artifact_id}:{current.updated_at_ms}",
            operation="archive",
            idempotency_key=idempotency_key,
            fact_type=DOCUMENT_ARCHIVED,
            payload={},
            occurred_at_ms=when,
        )
        return self._projector.get(
            tenant_id=tenant_id, business_id=business_id, document_id=document_id
        )

    def get(self, *, tenant_id: str, business_id: str, document_id: str) -> Document:
        return self._projector.get(
            tenant_id=tenant_id, business_id=business_id, document_id=document_id
        )

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Document, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)


__all__ = ["CANON_DOCUMENT_LIFECYCLE_OWNER", "DocumentRegistry"]
