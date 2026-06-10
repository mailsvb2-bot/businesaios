from __future__ import annotations

import time

from config.execution_contract import is_canonical_decision_path
from lead_outcomes import (
    LeadConversionTracker,
    LeadOutcomeRegistry,
    LeadRevenueTracker,
    LeadStatusTracker,
    OutcomeTimeline,
)
from observability.demand import emit_outcome_events as emit_outcome_event
from routing_execution.delivery_status import delivered_at_ms_for_status, persisted_delivery_status
from shared.numbers import coerce_float, coerce_int


class DemandOutcomeRecorder:
    def __init__(self, *, outcomes: LeadOutcomeRegistry, optimizer, event_log: object | None = None) -> None:
        self._outcomes = outcomes
        self._optimizer = optimizer
        self._status_tracker = LeadStatusTracker()
        self._conversion_tracker = LeadConversionTracker()
        self._revenue_tracker = LeadRevenueTracker()
        self._timeline = OutcomeTimeline()
        self._event_log = event_log

    def _append_timeline(self, request_id: str, event: str) -> None:
        self._timeline.append(self._outcomes, request_id, event)

    def seed(self, *, request, decision, delivery) -> None:
        trace = dict(getattr(decision, 'trace', {}) or {})
        trace_path = str(trace.get('decision_path') or '').strip()
        selected_business_id = str(getattr(decision, 'selected_business_id', '') or '').strip() or None
        if selected_business_id and (not trace_path or not is_canonical_decision_path(trace_path)):
            raise ValueError('outcome seed requires canonical decision trace for routed requests')
        delivery_status = persisted_delivery_status(
            getattr(delivery, 'delivery_status', None),
            delivery_missing=delivery is None,
        )
        delivered_at_ms = coerce_int(
            getattr(delivery, 'delivered_at_ms', 0) if delivery is not None else 0,
            0,
            minimum=0,
        )
        if delivery is not None and delivery_status == 'delivered' and delivered_at_ms <= 0:
            fallback_ts = delivered_at_ms_for_status(delivery_status, now_ms=int(time.time() * 1000))
            delivered_at_ms = int(fallback_ts or 0)
        if delivery_status != 'delivered':
            delivered_at_ms = 0
        seed_row = {
            'request_id': request.request_id,
            'customer_id': request.customer_id,
            'business_id': decision.selected_business_id,
            'requires_manual_review': bool(decision.requires_manual_review),
            'decision_trace': trace,
            'delivery_status': delivery_status,
            'channel': getattr(delivery, 'channel', ''),
            'created_at_ms': int(getattr(request, 'created_at_ms', 0) or 0),
            'delivered_at_ms': delivered_at_ms,
            'outcome_updated_at_ms': int(delivered_at_ms or getattr(request, 'created_at_ms', 0) or 0),
        }
        self._outcomes.update(request.request_id, seed_row)
        self._append_timeline(request.request_id, f'seed:{delivery_status}')
        if delivery_status in {'delivered', 'accepted', 'queued', 'duplicate'}:
            self._status_tracker.update(self._outcomes, request.request_id, delivery_status)
        elif delivery is None:
            self._status_tracker.update(self._outcomes, request.request_id, 'manual_review')

    def record(self, *, request_id: str, converted: bool, revenue: float = 0.0, quality_issue: bool = False, refunded: bool = False, lost: bool = False) -> dict[str, object]:
        if not self._outcomes.has(request_id):
            raise KeyError(str(request_id))
        current = self._outcomes.require(request_id)
        normalized_revenue = coerce_float(revenue, 0.0, minimum=0.0)
        if converted and lost:
            raise ValueError('outcome cannot be both converted and lost')
        if refunded and not converted and normalized_revenue <= 0.0:
            raise ValueError('refund requires a converted or revenue-bearing outcome')
        if bool(current.get('requires_manual_review')) or not current.get('business_id'):
            if converted or normalized_revenue > 0.0 or refunded or lost:
                raise ValueError('cannot record routed outcome for manual review request')
        self._conversion_tracker.update(self._outcomes, request_id, converted)
        self._revenue_tracker.update(self._outcomes, request_id, normalized_revenue)
        final_status = 'lost' if lost else ('converted' if converted else 'closed')
        self._status_tracker.update(self._outcomes, request_id, final_status)
        current = self._outcomes.require(request_id)
        previous_ts = int(current.get('outcome_updated_at_ms') or current.get('delivered_at_ms') or current.get('created_at_ms') or 0)
        now_ms = int(time.time() * 1000)
        timestamp = max(previous_ts + 1, now_ms)
        self._outcomes.update(request_id, {'quality_issue': bool(quality_issue), 'refunded': bool(refunded), 'lost': bool(lost), 'outcome_updated_at_ms': timestamp})
        self._append_timeline(request_id, f'final:{final_status}')
        rows = tuple(self._outcomes.snapshot().values())
        policy_state = self._optimizer.learn(rows)
        result = self._outcomes.require(request_id)
        emit_outcome_event(self._event_log, 'outcome_recorded', {'request_id': request_id, 'business_id': result.get('business_id', ''), 'converted': bool(converted), 'revenue': normalized_revenue})
        return {'outcome': result, 'policy_state': policy_state}
