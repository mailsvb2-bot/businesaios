from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from collections.abc import Mapping

from ..enums import SourceKind
from ..types import LessonDraft, TagSet


@dataclass(frozen=True)
class IncidentLessonDraftMapper:
    created_by: str = "knowledge-ingestion"

    def map(self, payload: Mapping[str, object]) -> LessonDraft:
        incident_id = str(payload.get("incident_id") or "unknown-incident")
        subject = str(payload.get("subject") or payload.get("service") or incident_id)
        observed_at = payload.get("observed_at")
        if not isinstance(observed_at, datetime):
            raise ValueError("observed_at datetime is required for incident ingestion")
        title = f"Incident lesson: {incident_id}"
        narrative = str(payload.get("summary") or payload.get("root_cause") or "incident recorded")
        tags = TagSet.from_iterable(("incident", str(payload.get("severity") or "unknown")))
        return LessonDraft(
            subject=subject,
            title=title,
            narrative=narrative,
            source_kind=SourceKind.INCIDENT,
            source_ref=incident_id,
            tags=tags,
            observed_at=observed_at,
            created_by=self.created_by,
            evidence_refs=tuple(str(item) for item in payload.get("evidence_refs", ()) if str(item).strip()),
            outcome_refs=tuple(str(item) for item in payload.get("outcome_refs", ()) if str(item).strip()),
            metadata={
                "severity": str(payload.get("severity") or ""),
                "service": str(payload.get("service") or ""),
            },
        )
