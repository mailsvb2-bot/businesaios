from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from config.final_hidden_logic_policy import DEFAULT_KNOWLEDGE_DEDUPLICATION_POLICY

from ..types import LessonDraft
from .token_similarity import jaccard_similarity


@dataclass(frozen=True)
class LessonDeduplicator:
    duplicate_threshold: float = DEFAULT_KNOWLEDGE_DEDUPLICATION_POLICY.duplicate_threshold

    def find_similar_titles(self, draft: LessonDraft, existing_titles: Sequence[str]) -> tuple[str, ...]:
        hits: list[str] = []
        for title in existing_titles:
            if jaccard_similarity(draft.title, title) >= self.duplicate_threshold:
                hits.append(title)
        return tuple(hits)

    def is_probable_duplicate(self, draft: LessonDraft, existing_titles: Sequence[str]) -> bool:
        return bool(self.find_similar_titles(draft, existing_titles))
