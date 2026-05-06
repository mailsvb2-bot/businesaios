from __future__ import annotations

from shared.numbers import coerce_float


class BusinessQualityLearningLoop:
    def propose_quality_updates(self, feedback_rows: tuple[dict[str, object], ...]) -> dict[str, float]:
        scores = [coerce_float(row.get('quality_score'), 0.0, minimum=0.0, maximum=1.0) for row in feedback_rows if 'quality_score' in row]
        return {'quality_mean': sum(scores) / max(1, len(scores))}
