from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from ..enums import ConfidenceLevel, KnowledgeKind, LessonStatus, SourceKind
from ..types import Lesson, MemoryLink, Pattern, TagSet
from .datetime_codec import decode_datetime, encode_datetime


def serialize_lesson(lesson: Lesson) -> dict[str, Any]:
    return {
        "lesson_id": lesson.lesson_id,
        "subject": lesson.subject,
        "title": lesson.title,
        "narrative": lesson.narrative,
        "source_kind": lesson.source_kind.value,
        "source_ref": lesson.source_ref,
        "tags": list(lesson.tags.values),
        "observed_at": encode_datetime(lesson.observed_at),
        "created_at": encode_datetime(lesson.created_at),
        "created_by": lesson.created_by,
        "status": lesson.status.value,
        "evidence_refs": list(lesson.evidence_refs),
        "outcome_refs": list(lesson.outcome_refs),
        "metadata": dict(lesson.metadata),
    }


def deserialize_lesson(payload: Mapping[str, Any]) -> Lesson:
    return Lesson(
        lesson_id=str(payload["lesson_id"]),
        subject=str(payload["subject"]),
        title=str(payload["title"]),
        narrative=str(payload["narrative"]),
        source_kind=SourceKind(str(payload["source_kind"])),
        source_ref=str(payload["source_ref"]),
        tags=TagSet.from_iterable(payload.get("tags", ())),
        observed_at=decode_datetime(str(payload["observed_at"])),
        created_at=decode_datetime(str(payload["created_at"])),
        created_by=str(payload["created_by"]),
        status=LessonStatus(str(payload["status"])),
        evidence_refs=tuple(str(item) for item in payload.get("evidence_refs", ())),
        outcome_refs=tuple(str(item) for item in payload.get("outcome_refs", ())),
        metadata={str(k): str(v) for k, v in dict(payload.get("metadata", {})).items()},
    )


def serialize_pattern(pattern: Pattern) -> dict[str, Any]:
    return {
        "pattern_id": pattern.pattern_id,
        "subject": pattern.subject,
        "hypothesis": pattern.hypothesis,
        "lesson_ids": list(pattern.lesson_ids),
        "signal_count": pattern.signal_count,
        "contradictory_signal_count": pattern.contradictory_signal_count,
        "confidence_level": pattern.confidence_level.value,
        "confidence_score": pattern.confidence_score,
        "tags": list(pattern.tags.values),
        "created_at": encode_datetime(pattern.created_at),
        "created_by": pattern.created_by,
        "metadata": dict(pattern.metadata),
    }


def deserialize_pattern(payload: Mapping[str, Any]) -> Pattern:
    return Pattern(
        pattern_id=str(payload["pattern_id"]),
        subject=str(payload["subject"]),
        hypothesis=str(payload["hypothesis"]),
        lesson_ids=tuple(str(item) for item in payload.get("lesson_ids", ())),
        signal_count=int(payload["signal_count"]),
        contradictory_signal_count=int(payload["contradictory_signal_count"]),
        confidence_level=ConfidenceLevel(str(payload["confidence_level"])),
        confidence_score=float(payload["confidence_score"]),
        tags=TagSet.from_iterable(payload.get("tags", ())),
        created_at=decode_datetime(str(payload["created_at"])),
        created_by=str(payload["created_by"]),
        metadata={str(k): str(v) for k, v in dict(payload.get("metadata", {})).items()},
    )


def serialize_memory_link(link: MemoryLink) -> dict[str, Any]:
    return {
        "link_id": link.link_id,
        "source_kind": link.source_kind.value,
        "source_id": link.source_id,
        "target_kind": link.target_kind.value,
        "target_id": link.target_id,
        "rationale": link.rationale,
        "created_at": encode_datetime(link.created_at),
        "created_by": link.created_by,
    }


def deserialize_memory_link(payload: Mapping[str, Any]) -> MemoryLink:
    return MemoryLink(
        link_id=str(payload["link_id"]),
        source_kind=KnowledgeKind(str(payload["source_kind"])),
        source_id=str(payload["source_id"]),
        target_kind=KnowledgeKind(str(payload["target_kind"])),
        target_id=str(payload["target_id"]),
        rationale=str(payload["rationale"]),
        created_at=decode_datetime(str(payload["created_at"])),
        created_by=str(payload["created_by"]),
    )
