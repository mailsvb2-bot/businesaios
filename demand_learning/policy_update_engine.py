from __future__ import annotations

from config.demand_thresholds import MONOPOLY_LIMIT
from config.learning_thresholds import (
    MIN_REPLAY_SAMPLE_SIZE,
    POLICY_MAX_ABSOLUTE_ADJUSTMENT,
    POLICY_MIN_OUTCOME_ROWS_FOR_UPDATE,
    POLICY_MIN_PER_BUSINESS_ROWS,
)
from demand_learning.causal_outcome_engine import CausalOutcomeEngine
from demand_learning.policy_state import PolicyState
from shared.numbers import coerce_float, coerce_int


class PolicyUpdateEngine:
    def __init__(self) -> None:
        self._causal = CausalOutcomeEngine()

    def _clip(self, value: float) -> float:
        limit = float(POLICY_MAX_ABSOLUTE_ADJUSTMENT)
        return float(round(max(-limit, min(limit, value)), 6))

    def _effective_rows(self, outcome_rows: tuple[dict[str, object], ...]) -> tuple[dict[str, object], ...]:
        latest_by_request: dict[str, dict[str, object]] = {}
        anonymous_rows: list[dict[str, object]] = []
        for row in outcome_rows:
            request_id = str(row.get('request_id') or '').strip()
            business_id = str(row.get('business_id') or '').strip()
            if not business_id or bool(row.get('requires_manual_review')):
                continue
            if not request_id:
                anonymous_rows.append(dict(row))
                continue
            ts = coerce_int(row.get('outcome_updated_at_ms', row.get('created_at_ms', 0)), 0, minimum=0)
            current = latest_by_request.get(request_id)
            current_ts = coerce_int((current or {}).get('outcome_updated_at_ms', (current or {}).get('created_at_ms', 0)), 0, minimum=0)
            if current is None or ts >= current_ts:
                latest_by_request[request_id] = dict(row)
        return tuple([*latest_by_request.values(), *anonymous_rows])

    def update(self, outcome_rows: tuple[dict[str, object], ...]) -> PolicyState:
        state = PolicyState(last_updated_from_rows=len(outcome_rows))
        effective_rows = self._effective_rows(outcome_rows)
        total = len(effective_rows)
        if total < POLICY_MIN_OUTCOME_ROWS_FOR_UPDATE:
            return state
        counts: dict[str, int] = {}
        bad_rates: dict[str, list[float]] = {}
        converted_rates: dict[str, list[float]] = {}
        for row in effective_rows:
            business_id = str(row.get('business_id') or '')
            counts[business_id] = counts.get(business_id, 0) + 1
            refunded = bool(row.get('refunded'))
            quality_issue = bool(row.get('quality_issue'))
            lost = bool(row.get('lost'))
            converted = bool(row.get('converted'))
            revenue = coerce_float(row.get('revenue'), 0.0, minimum=0.0)
            contradictory = refunded and (not converted) and revenue <= 0.0
            bad_rates.setdefault(business_id, []).append(1.0 if (lost or refunded or quality_issue or contradictory) else 0.0)
            converted_rates.setdefault(business_id, []).append(1.0 if converted else 0.0)
        uplift = self._causal.uplift_by_business(effective_rows)
        active_businesses = max(1, len(counts))
        expected_share = 1.0 / active_businesses
        for business_id, count in counts.items():
            state.sample_size[business_id] = count
            share = count / max(1, total)
            bad_rate = sum(bad_rates.get(business_id, [0.0])) / max(1, len(bad_rates.get(business_id, [])))
            conversion_rate = sum(converted_rates.get(business_id, [0.0])) / max(1, len(converted_rates.get(business_id, [])))
            fairness_adjustment = 0.0
            if count >= MIN_REPLAY_SAMPLE_SIZE and share > MONOPOLY_LIMIT:
                fairness_adjustment = -(share - MONOPOLY_LIMIT)
            elif (
                count >= POLICY_MIN_PER_BUSINESS_ROWS
                and share < expected_share * 0.5
                and bad_rate <= 0.25
                and conversion_rate >= 0.15
            ):
                fairness_adjustment = min(expected_share - share, MONOPOLY_LIMIT * 0.25)
            state.fairness_boost[business_id] = self._clip(fairness_adjustment)
            if count < POLICY_MIN_PER_BUSINESS_ROWS:
                state.risk_penalty[business_id] = 0.0
                state.causal_bonus[business_id] = 0.0
                continue
            risk = (bad_rate * 0.35) + (max(0.0, 0.35 - conversion_rate) * 0.25)
            state.risk_penalty[business_id] = self._clip(risk)
            state.causal_bonus[business_id] = self._clip(float(uplift.get(business_id, 0.0)))
        return state
