from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from ..enums import SourceKind
from ..types import LessonDraft, TagSet


@dataclass(frozen=True)
class ExperimentOutcomeLessonDraftMapper:
    created_by: str = "knowledge-ingestion"

    def map(self, payload: Mapping[str, object]) -> LessonDraft:
        experiment_id = str(payload.get("experiment_id") or "unknown-experiment")
        subject = str(payload.get("subject") or payload.get("primary_metric_key") or experiment_id)
        observed_at = payload.get("observed_at")
        if not isinstance(observed_at, datetime):
            raise ValueError("observed_at datetime is required for experiment outcome ingestion")
        title = f"Experiment lesson: {experiment_id}"
        narrative = str(payload.get("summary") or payload.get("notes") or "experiment outcome recorded")
        tags = TagSet.from_iterable(("experiment", str(payload.get("primary_metric_key") or "metric")))
        return LessonDraft(
            subject=subject,
            title=title,
            narrative=narrative,
            source_kind=SourceKind.EXPERIMENT,
            source_ref=experiment_id,
            tags=tags,
            observed_at=observed_at,
            created_by=self.created_by,
            evidence_refs=tuple(str(item) for item in payload.get("variant_ids", ()) if str(item).strip()),
            outcome_refs=tuple(str(item) for item in payload.get("result_ids", ()) if str(item).strip()),
            metadata={
                "primary_metric_key": str(payload.get("primary_metric_key") or ""),
                "rollout_decision": str(payload.get("rollout_decision") or ""),
            },
        )
