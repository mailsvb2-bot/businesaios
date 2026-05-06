from __future__ import annotations

from config.execution_contract import (
    CANONICAL_OPTIMIZATION_TARGET,
    DEFAULT_MANUAL_REVIEW_CHANNEL,
    DELIVERY_ALLOWED_CHANNELS,
    is_canonical_decision_path,
)


class DeliveryContractValidator:
    def validate(self, *, request, decision, channel: str) -> None:
        trace = getattr(decision, 'trace', None)
        if not isinstance(trace, dict):
            raise ValueError('delivery requires canonical demand decision trace')
        selected_business_id = str(getattr(decision, 'selected_business_id', '') or '').strip() or None
        requires_manual_review = bool(getattr(decision, 'requires_manual_review', False))
        runner_ups = tuple(str(item or '').strip() for item in getattr(decision, 'runner_up_business_ids', ()) or ())
        if selected_business_id is None and not requires_manual_review:
            raise ValueError('delivery cannot execute empty non-manual decision')
        if requires_manual_review and selected_business_id is not None:
            raise ValueError('manual review decision cannot carry selected business')
        decision_path = str(trace.get('decision_path') or '').strip()
        if not decision_path or not is_canonical_decision_path(decision_path):
            raise ValueError('delivery requires canonical demand decision trace')
        optimization_target = str(trace.get('optimization_target') or '').strip()
        if not optimization_target or optimization_target != CANONICAL_OPTIMIZATION_TARGET:
            raise ValueError('delivery requires canonical optimization target')
        request_id = str(getattr(request, 'request_id', '') or '')
        if not request_id:
            raise ValueError('request_id is required')
        trace_request_id = str(trace.get('request_id') or '')
        if trace_request_id and trace_request_id != request_id:
            raise ValueError('delivery requires request_id-consistent decision trace')
        if selected_business_id and selected_business_id in runner_ups:
            raise ValueError('selected business cannot also be a runner-up')
        if len(runner_ups) != len(tuple(item for item in runner_ups if item)):
            raise ValueError('runner-up business ids must be non-empty')
        if len(set(runner_ups)) != len(runner_ups):
            raise ValueError('runner-up business ids must be unique')
        if requires_manual_review:
            if str(channel) != DEFAULT_MANUAL_REVIEW_CHANNEL:
                raise ValueError('manual review decisions must use manual_review channel')
        elif str(channel) not in DELIVERY_ALLOWED_CHANNELS:
            raise ValueError(f'unsupported delivery channel: {channel}')
