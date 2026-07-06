from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from ..enums import SourceKind
from ..types import LessonDraft, TagSet


@dataclass(frozen=True)
class CampaignOutcomeLessonDraftMapper:
    created_by: str = "knowledge-ingestion"

    def map(self, payload: Mapping[str, object]) -> LessonDraft:
        campaign_id = str(payload.get("campaign_id") or "unknown-campaign")
        subject = str(payload.get("subject") or payload.get("channel") or campaign_id)
        observed_at = payload.get("observed_at")
        if not isinstance(observed_at, datetime):
            raise ValueError("observed_at datetime is required for campaign outcome ingestion")
        title = f"Campaign lesson: {campaign_id}"
        narrative = str(payload.get("summary") or payload.get("insight") or "campaign outcome recorded")
        tags = TagSet.from_iterable(("campaign", str(payload.get("channel") or "unknown")))
        return LessonDraft(
            subject=subject,
            title=title,
            narrative=narrative,
            source_kind=SourceKind.CAMPAIGN,
            source_ref=campaign_id,
            tags=tags,
            observed_at=observed_at,
            created_by=self.created_by,
            evidence_refs=tuple(str(item) for item in payload.get("creative_refs", ()) if str(item).strip()),
            outcome_refs=tuple(str(item) for item in payload.get("outcome_refs", ()) if str(item).strip()),
            metadata={
                "channel": str(payload.get("channel") or ""),
                "objective": str(payload.get("objective") or ""),
            },
        )
