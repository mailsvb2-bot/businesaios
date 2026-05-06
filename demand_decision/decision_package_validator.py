from __future__ import annotations

from config.execution_contract import CANONICAL_OPTIMIZATION_TARGET
from routing.router_preparation_validator import RouterPreparationValidator


class DecisionPackageValidator:
    def __init__(self) -> None:
        self._validator = RouterPreparationValidator()

    def validate(self, routing_preparation: dict[str, object]) -> dict[str, object]:
        trace = dict(routing_preparation.get('trace') or {})
        incoming_target = trace.get('optimization_target')
        if incoming_target and incoming_target != CANONICAL_OPTIMIZATION_TARGET:
            raise ValueError('optimization_target must be canonical')
        preferred_channels = trace.get('preferred_channels')
        if preferred_channels is not None and not isinstance(preferred_channels, dict):
            raise ValueError('preferred_channels must be a dict')
        package = self._validator.validate(routing_preparation)
        manual_review = package.get('requires_manual_review')
        if manual_review is not None and not isinstance(manual_review, bool):
            raise ValueError('requires_manual_review must be a bool')
        candidates = tuple(package.get('ranked_candidates') or ())
        if not candidates and manual_review is not True:
            raise ValueError('empty routing preparation must explicitly require manual review')
        if manual_review is True and candidates:
            raise ValueError('manual review path cannot expose decision candidates')
        return package
