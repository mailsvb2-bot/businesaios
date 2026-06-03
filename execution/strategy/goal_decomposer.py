from __future__ import annotations
from typing import Any
from collections.abc import Mapping
CANON_GOAL_DECOMPOSER = True
class GoalDecomposer:
    def decompose(self, *, goal: str, metadata: Mapping[str, Any] | None = None) -> tuple[str, ...]:
        payload = dict(metadata or {})
        explicit = payload.get('action_hints') or payload.get('steps') or payload.get('remaining_action_hints')
        if isinstance(explicit, (list, tuple)):
            normalized = tuple(str(item).strip() for item in explicit if str(item).strip())
            if normalized:
                return normalized
        text = str(goal or '').lower()
        if 'revenue' in text:
            return ('launch_campaign', 'verify_conversion', 'tune_budget')
        if 'retention' in text:
            return ('segment_customers', 'send_followup', 'measure_repeat_rate')
        if 'review' in text or 'reputation' in text:
            return ('request_review', 'verify_publication', 'measure_reply_rate')
        if 'demand' in text or 'lead' in text:
            return ('publish_service_page', 'launch_campaign', 'capture_leads')
        return ('assess_state', 'select_next_action', 'verify_outcome')
