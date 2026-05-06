from __future__ import annotations

from core.world_model.types import CompletenessReport


class StateGapExplainer:
    def explain(self, *, completeness: CompletenessReport) -> dict:
        return {
            "missing_fields": list(completeness.missing_fields),
            "present_fields": list(completeness.present_fields),
            "completeness_score": completeness.score,
        }
