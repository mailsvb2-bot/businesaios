from __future__ import annotations

from config.routing_limits import MANUAL_REVIEW_REASON
from routing.router_preparation_validator import RouterPreparationValidator


class RouterFallback:
    def __init__(self) -> None:
        self._validator = RouterPreparationValidator()

    def fallback(self, *, request_id: str, trace: dict[str, object] | None = None) -> dict[str, object]:
        package = {
            'request_id': str(request_id),
            'requires_manual_review': True,
            'reason': MANUAL_REVIEW_REASON,
            'ranked_candidates': (),
            'trace': {'manual_review_reason': MANUAL_REVIEW_REASON, 'decision_path': 'routing', **dict(trace or {})},
        }
        return self._validator.validate(package)
