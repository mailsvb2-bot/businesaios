from __future__ import annotations

from dataclasses import replace
from typing import Any

from application.document.facts import (
    DOCUMENT_ARCHIVED,
    DOCUMENT_CREATED,
    DOCUMENT_FACT_TYPES,
    DOCUMENT_REVISED,
)
from contracts.document import Document, DocumentNotFound, DocumentStatus
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE

CANON_DOCUMENT_PROJECTOR = True


class DocumentHistoryInvariantViolation(RuntimeError):
    pass


class DocumentProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(
        self, *, tenant_id: str, business_id: str, document_id: str | None = None
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for append_order, event in enumerate(
            self._events.iter_events(
                tenant_id=str(tenant_id), start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE
            )
        ):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type = str(envelope.get("fact_type") or "")
            entity_id = str(envelope.get("entity_id") or "")
            if fact_type not in DOCUMENT_FACT_TYPES:
                continue
            if document_id is not None and entity_id != str(document_id):
                continue
            rows.append({
                "fact_id": str(event.get("event_id") or ""),
                "fact_type": fact_type,
                "entity_id": entity_id,
                "event_time_ms": int(envelope.get("event_time_ms") or event.get("timestamp_ms") or 0),
                "observed_at_ms": int(envelope.get("observed_at_ms") or event.get("timestamp_ms") or 0),
                "append_order": append_order,
                "payload": dict(envelope.get("payload") or {}),
            })
        rows.sort(
            key=lambda row: (
                row["event_time_ms"], row["observed_at_ms"], row["append_order"], row["fact_id"]
            )
        )
        return rows

    def get(self, *, tenant_id: str, business_id: str, document_id: str) -> Document:
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, document_id=document_id)
        created_rows = [row for row in facts if row["fact_type"] == DOCUMENT_CREATED]
        if not created_rows:
            raise DocumentNotFound(f"document not found: {document_id}")
        if len(created_rows) != 1:
            raise DocumentHistoryInvariantViolation("document history contains multiple create facts")
        created = created_rows[0]
        payload = dict(created["payload"])
        document = Document(
            document_id=str(document_id),
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            artifact_id=str(payload.get("artifact_id") or ""),
            document_kind=payload.get("document_kind"),
            title=payload.get("title"),
            created_at_ms=int(created["event_time_ms"]),
            updated_at_ms=int(created["event_time_ms"]),
        )
        for row in facts:
            if row is created:
                continue
            if document.status is DocumentStatus.ARCHIVED:
                raise DocumentHistoryInvariantViolation("document history continues after archive")
            fact_type = row["fact_type"]
            when = int(row["event_time_ms"])
            if when < document.created_at_ms:
                raise DocumentHistoryInvariantViolation("document mutation predates creation")
            if fact_type == DOCUMENT_CREATED:
                raise DocumentHistoryInvariantViolation("document history contains multiple create facts")
            if fact_type == DOCUMENT_REVISED:
                revision_payload = dict(row["payload"])
                artifact_id = str(revision_payload.get("artifact_id") or "").strip()
                if not artifact_id or artifact_id == document.artifact_id:
                    raise DocumentHistoryInvariantViolation("document revision must change artifact_id")
                document = replace(
                    document,
                    artifact_id=artifact_id,
                    revision=document.revision + 1,
                    updated_at_ms=max(document.updated_at_ms, when),
                )
            elif fact_type == DOCUMENT_ARCHIVED:
                document = replace(
                    document,
                    status=DocumentStatus.ARCHIVED,
                    updated_at_ms=max(document.updated_at_ms, when),
                    archived_at_ms=when,
                )
        return document

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Document, ...]:
        ids = sorted({str(row["entity_id"]) for row in self._facts(tenant_id=tenant_id, business_id=business_id)})
        return tuple(
            self.get(tenant_id=tenant_id, business_id=business_id, document_id=value)
            for value in ids
        )


__all__ = ["CANON_DOCUMENT_PROJECTOR", "DocumentHistoryInvariantViolation", "DocumentProjector"]
