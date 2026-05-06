from __future__ import annotations

from dataclasses import dataclass

from ..types import MemorySummary


@dataclass(frozen=True)
class MemoryTraceExplainer:
    def explain(self, summary: MemorySummary) -> str:
        lines = [
            "Memory trace explanation:",
            f"- subject: {summary.retrieval.target_subject}",
            f"- task: {summary.retrieval.task}",
            f"- items: {len(summary.entries)}",
            f"- coverage_score: {summary.coverage_score:.2f}",
            f"- quality_score: {summary.quality_score:.2f}",
            f"- safety: {summary.safety.value}",
        ]
        for entry in summary.entries:
            lines.append(
                f"- {entry.kind.value}:{entry.entity_id} -> {entry.summary} "
                f"[rel={entry.relevance_score:.2f}, fresh={entry.freshness_score:.2f}, "
                f"conf={entry.confidence_score:.2f}, support={entry.support_count}]"
            )
        return "\n".join(lines)
