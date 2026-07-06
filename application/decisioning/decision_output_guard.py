from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from kernel.decisioning.decision_types import RecommendationSet


class DecisionPayloadViolation(TypeError):
    pass


def assert_non_decision_payload(value: object) -> RecommendationSet:
    if isinstance(value, Mapping):
        _reject_decision_like_mapping(value)
        return [dict(value)]
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        out: RecommendationSet = []
        for item in value:
            if not isinstance(item, Mapping):
                raise DecisionPayloadViolation('RecommendationSet items must be mappings')
            _reject_decision_like_mapping(item)
            out.append(dict(item))
        return out
    raise DecisionPayloadViolation('Expected recommendation mapping or sequence of mappings')


def _reject_decision_like_mapping(item: Mapping[str, Any]) -> None:
    decision_keys = {'decision_id', 'issuer_id', 'action', 'issued_at_ms', 'expires_at_ms'}
    if decision_keys.issubset(set(item.keys())):
        raise DecisionPayloadViolation('Decision-like payload is forbidden in recommendation-only boundary')
    forbidden_keys = {
        'winner',
        'winning_candidate',
        'candidate_ids',
        'allowed_candidates',
        'filtered_candidates',
        'executor_command',
        'final_decision',
    }
    overlap = forbidden_keys.intersection(set(item.keys()))
    if overlap:
        raise DecisionPayloadViolation(f'Forbidden action-space fields in recommendation boundary: {sorted(overlap)}')
