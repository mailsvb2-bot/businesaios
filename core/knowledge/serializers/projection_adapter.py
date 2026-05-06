from __future__ import annotations

from typing import Any

from ..projections.lesson_index_projection import LessonIndexProjection
from ..projections.memory_usage_projection import MemoryUsageProjection
from ..projections.pattern_index_projection import PatternIndexProjection


class ProjectionReadModelAdapter:
    def serialize_lesson_index(self, projection: LessonIndexProjection) -> dict[str, Any]:
        return {
            "lesson_id": projection.lesson_id,
            "subject": projection.subject,
            "title": projection.title,
            "tags": list(projection.tags),
        }

    def serialize_pattern_index(self, projection: PatternIndexProjection) -> dict[str, Any]:
        return {
            "pattern_id": projection.pattern_id,
            "subject": projection.subject,
            "hypothesis": projection.hypothesis,
            "confidence_score": projection.confidence_score,
            "support_count": projection.support_count,
        }

    def serialize_memory_usage(self, projection: MemoryUsageProjection) -> dict[str, Any]:
        return {
            "entity_id": projection.entity_id,
            "kind": projection.kind,
            "relevance_score": projection.relevance_score,
            "freshness_score": projection.freshness_score,
            "confidence_score": projection.confidence_score,
            "support_count": projection.support_count,
        }
