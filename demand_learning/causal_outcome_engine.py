from __future__ import annotations

import math

from config.learning_thresholds import CAUSAL_RECENCY_WEIGHT, POLICY_MIN_PER_BUSINESS_ROWS
from shared.numbers import coerce_float, coerce_int


class CausalOutcomeEngine:
    """Leak-resistant uplift estimate using leave-one-business-out baselines."""

    def _row_score(self, row: dict[str, object]) -> float:
        revenue = max(0.0, coerce_float(row.get('revenue'), 0.0))
        converted = 1.0 if row.get('converted') else 0.0
        bad = 1.0 if (row.get('lost') or row.get('refunded') or row.get('quality_issue')) else 0.0
        manual_review = 1.0 if row.get('requires_manual_review') else 0.0
        revenue_component = min(0.75, math.log1p(revenue) * 0.08)
        return revenue_component + (converted * 0.5) - (bad * 0.4) - (manual_review * 0.05)

    def _ordered_rows(self, outcome_rows: tuple[dict[str, object], ...]) -> tuple[dict[str, object], ...]:
        latest_by_request: dict[str, dict[str, object]] = {}
        anonymous_rows: list[dict[str, object]] = []
        for row in outcome_rows:
            request_id = str(row.get('request_id') or '').strip()
            if not request_id:
                anonymous_rows.append(dict(row))
                continue
            current = latest_by_request.get(request_id)
            ts = coerce_int(row.get('outcome_updated_at_ms', row.get('created_at_ms', 0)), 0, minimum=0)
            current_ts = coerce_int((current or {}).get('outcome_updated_at_ms', (current or {}).get('created_at_ms', 0)), 0, minimum=0)
            if current is None or ts >= current_ts:
                latest_by_request[request_id] = dict(row)

        def sort_key(row: dict[str, object]) -> tuple[int, str]:
            ts = coerce_int(row.get('outcome_updated_at_ms', row.get('created_at_ms', 0)), 0, minimum=0)
            rid = str(row.get('request_id') or '')
            return ts, rid

        return tuple(sorted([*latest_by_request.values(), *anonymous_rows], key=sort_key))

    def uplift_by_business(self, outcome_rows: tuple[dict[str, object], ...]) -> dict[str, float]:
        totals: dict[str, list[float]] = {}
        ordered_rows = self._ordered_rows(outcome_rows)
        ordered: list[tuple[str, float]] = []
        for row in ordered_rows:
            business_id = str(row.get('business_id') or '')
            if not business_id or bool(row.get('requires_manual_review')):
                continue
            score = self._row_score(row)
            totals.setdefault(business_id, []).append(score)
            ordered.append((business_id, score))
        if not totals:
            return {}
        business_totals = {bid: sum(values) for bid, values in totals.items()}
        business_counts = {bid: len(values) for bid, values in totals.items()}
        global_total = sum(score for _, score in ordered)
        global_count = len(ordered)
        uplift: dict[str, float] = {}
        for business_id, values in totals.items():
            count = len(values)
            if count < POLICY_MIN_PER_BUSINESS_ROWS:
                uplift[business_id] = 0.0
                continue
            own_total = business_totals[business_id]
            baseline_count = max(1, global_count - business_counts[business_id])
            baseline_total = global_total - own_total
            baseline = baseline_total / baseline_count if baseline_count > 0 else 0.0
            recent = values[-min(5, count):]
            recent_mean = sum(recent) / max(1, len(recent))
            lifetime_mean = own_total / count
            stabilized_mean = (recent_mean * CAUSAL_RECENCY_WEIGHT) + (lifetime_mean * (1.0 - CAUSAL_RECENCY_WEIGHT))
            uplift[business_id] = float(round(stabilized_mean - baseline, 6))
        return uplift
