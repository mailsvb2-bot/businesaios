from __future__ import annotations

from dataclasses import replace
from typing import Any

from contracts.artifact import Artifact, ArtifactNotFound, ArtifactStatus
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE

ARTIFACT_CREATED = "artifact.created"
ARTIFACT_ARCHIVED = "artifact.archived"
ARTIFACT_FACT_TYPES = frozenset({ARTIFACT_CREATED, ARTIFACT_ARCHIVED})

CANON_ARTIFACT_PROJECTOR = True


class ArtifactHistoryInvariantViolation(RuntimeError):
    pass


class ArtifactProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(
        self, *, tenant_id: str, business_id: str, artifact_id: str | None = None
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
            if fact_type not in ARTIFACT_FACT_TYPES:
                continue
            if artifact_id is not None and entity_id != str(artifact_id):
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

    def get(self, *, tenant_id: str, business_id: str, artifact_id: str) -> Artifact:
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, artifact_id=artifact_id)
        created_rows = [row for row in facts if row["fact_type"] == ARTIFACT_CREATED]
        if not created_rows:
            raise ArtifactNotFound(f"artifact not found: {artifact_id}")
        if len(created_rows) != 1:
            raise ArtifactHistoryInvariantViolation("artifact history contains multiple create facts")
        created = created_rows[0]
        payload = dict(created["payload"])
        artifact = Artifact(
            artifact_id=str(artifact_id),
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            artifact_kind=payload.get("artifact_kind"),
            storage_ref=payload.get("storage_ref"),
            content_sha256=payload.get("content_sha256"),
            media_type=payload.get("media_type"),
            created_at_ms=int(created["event_time_ms"]),
            updated_at_ms=int(created["event_time_ms"]),
        )
        for row in facts:
            if row is created:
                continue
            if artifact.status is ArtifactStatus.ARCHIVED:
                raise ArtifactHistoryInvariantViolation("artifact history continues after archive")
            if row["fact_type"] == ARTIFACT_CREATED:
                raise ArtifactHistoryInvariantViolation("artifact history contains multiple create facts")
            if row["fact_type"] == ARTIFACT_ARCHIVED:
                when = int(row["event_time_ms"])
                if when < artifact.created_at_ms:
                    raise ArtifactHistoryInvariantViolation("artifact archive predates creation")
                artifact = replace(
                    artifact,
                    status=ArtifactStatus.ARCHIVED,
                    updated_at_ms=max(artifact.updated_at_ms, when),
                    archived_at_ms=when,
                )
        return artifact

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Artifact, ...]:
        ids = sorted({str(row["entity_id"]) for row in self._facts(tenant_id=tenant_id, business_id=business_id)})
        return tuple(
            self.get(tenant_id=tenant_id, business_id=business_id, artifact_id=value)
            for value in ids
        )


__all__ = ["ArtifactHistoryInvariantViolation", "ArtifactProjector", "CANON_ARTIFACT_PROJECTOR"]
