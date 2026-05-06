from __future__ import annotations

from config.execution_contract import CANONICAL_OPTIMIZATION_TARGET

FORBIDDEN_FINAL_KEYS = (
    'selected_business_id',
    'decision',
    'winner_business_id',
    'final_business_id',
)


class RouterPreparationValidator:
    def validate(self, routing_preparation: dict[str, object]) -> dict[str, object]:
        package = dict(routing_preparation)
        for key in FORBIDDEN_FINAL_KEYS:
            if key in package:
                raise ValueError(f'routing layer cannot emit {key}')
        request_id = str(package.get('request_id') or '')
        if not request_id:
            raise ValueError('routing preparation requires request_id')
        candidates = tuple(package.get('ranked_candidates') or ())
        seen_business_ids: set[str] = set()
        for candidate in candidates:
            business_id = str(getattr(candidate, 'business_id', '') or '').strip()
            if not business_id:
                raise ValueError('routing candidates require business_id')
            if business_id in seen_business_ids:
                raise ValueError('routing candidates must be unique by business_id')
            seen_business_ids.add(business_id)
        trace = dict(package.get('trace') or {})
        incoming_path = str(trace.get('decision_path') or '')
        if incoming_path and incoming_path != 'routing':
            raise ValueError('routing preparation cannot impersonate final decision path')
        incoming_request_id = str(trace.get('request_id') or '')
        if incoming_request_id and incoming_request_id != request_id:
            raise ValueError('routing trace request_id must match package request_id')
        trace['decision_path'] = 'routing'
        trace['request_id'] = request_id
        trace.setdefault('candidate_count', len(candidates))
        trace['optimization_target'] = CANONICAL_OPTIMIZATION_TARGET
        package['ranked_candidates'] = candidates
        package['trace'] = trace
        package['request_id'] = request_id
        if package.get('requires_manual_review') is True and candidates:
            raise ValueError('manual review package cannot carry executable candidates')
        return package
