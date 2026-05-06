from __future__ import annotations

from shared.numbers import coerce_float


class RevenueOutcomeLearningLoop:
    def propose_revenue_updates(self, feedback_rows: tuple[dict[str, object], ...]) -> dict[str, float]:
        total_revenue = sum(coerce_float(row.get('revenue'), 0.0, minimum=0.0) for row in feedback_rows)
        return {'total_revenue': total_revenue}
