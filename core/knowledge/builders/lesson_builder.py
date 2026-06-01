from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ..enums import LessonStatus
from ..errors import KnowledgeValidationError
from ..ids import new_lesson_id
from ..types import Lesson, LessonDraft


@dataclass(frozen=True)
class LessonBuilder:
    def build(self, draft: LessonDraft) -> Lesson:
        subject = draft.subject.strip().lower()
        title = draft.title.strip()
        narrative = draft.narrative.strip()
        source_ref = draft.source_ref.strip()
        created_by = draft.created_by.strip()

        if not subject:
            raise KnowledgeValidationError("Lesson subject is required.")
        if not title:
            raise KnowledgeValidationError("Lesson title is required.")
        if not narrative:
            raise KnowledgeValidationError("Lesson narrative is required.")
        if not source_ref:
            raise KnowledgeValidationError("Lesson source_ref is required.")
        if not created_by:
            raise KnowledgeValidationError("Lesson created_by is required.")
        if draft.observed_at.tzinfo is None:
            raise KnowledgeValidationError("Lesson observed_at must be timezone-aware.")

        created_at = datetime.now(tz=UTC)
        if draft.observed_at > created_at:
            raise KnowledgeValidationError("Lesson observed_at cannot be in the future.")

        evidence_refs = tuple(ref.strip() for ref in draft.evidence_refs if ref and ref.strip())
        outcome_refs = tuple(ref.strip() for ref in draft.outcome_refs if ref and ref.strip())

        return Lesson(
            lesson_id=new_lesson_id(),
            subject=subject,
            title=title,
            narrative=narrative,
            source_kind=draft.source_kind,
            source_ref=source_ref,
            tags=draft.tags,
            observed_at=draft.observed_at,
            created_at=created_at,
            created_by=created_by,
            status=LessonStatus.ACTIVE,
            evidence_refs=evidence_refs,
            outcome_refs=outcome_refs,
            metadata=dict(draft.metadata),
        )
