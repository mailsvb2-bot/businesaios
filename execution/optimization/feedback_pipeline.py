from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any
from collections.abc import Iterable, Mapping

from execution.optimization.adaptation_metrics import clamp, safe_float


FEEDBACK_PIPELINE_SCHEMA_VERSION = 2


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _text(value: object) -> str:
    return str(value or '').strip()


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    token = _text(value).lower()
    if token in {'1', 'true', 'yes', 'y', 'on'}:
        return True
    if token in {'0', 'false', 'no', 'n', 'off', ''}:
        return False
    return False


def _stable_json(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    except (TypeError, ValueError):
        return repr(value)


@dataclass(frozen=True)
class AdaptationObservation:
    tenant_id: str
    business_id: str
    capability_key: str
    route_key: str
    action_type: str
    executed: bool
    verified: bool
    achieved: bool
    verification_confidence: float
    cost: float
    revenue_delta: float
    latency_ms: float
    threshold_before: float
    threshold_after: float
    fingerprint: str
    raw_feedback: dict[str, Any]

    @property
    def roi_ratio(self) -> float:
        if self.cost <= 0.0:
            return 1.0 if self.revenue_delta > 0.0 else 0.0
        return max(0.0, self.revenue_delta / self.cost)

    @property
    def identity_complete(self) -> bool:
        return bool(self.tenant_id and self.business_id and self.capability_key and self.route_key and self.action_type)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload['roi_ratio'] = float(self.roi_ratio)
        payload['identity_complete'] = bool(self.identity_complete)
        return payload


class FeedbackPipeline:
    @staticmethod
    def _fingerprint(payload: Mapping[str, Any]) -> str:
        base = {
            'tenant_id': _text(payload.get('tenant_id')),
            'business_id': _text(payload.get('business_id')),
            'capability_key': _text(payload.get('capability_key')),
            'route_key': _text(payload.get('route_key')),
            'action_type': _text(payload.get('action_type')),
            'decision_id': _text(payload.get('decision_id')),
            'correlation_id': _text(payload.get('correlation_id')),
            'external_refs': sorted(_text(item) for item in (payload.get('external_refs') or [])),
            'economic': _stable_json(payload.get('economic') or {}),
            'thresholds': _stable_json(payload.get('thresholds') or {}),
        }
        raw = json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        return sha256(raw.encode('utf-8')).hexdigest()

    def normalize(self, *, feedback: Mapping[str, Any]) -> AdaptationObservation:
        payload = _safe_dict(feedback)
        economic = _safe_dict(payload.get('economic'))
        thresholds = _safe_dict(payload.get('thresholds'))
        capability_key = _text(payload.get('capability_key') or payload.get('action_type') or 'unknown')
        route_key = _text(payload.get('route_key') or capability_key or 'default')
        return AdaptationObservation(
            tenant_id=_text(payload.get('tenant_id')),
            business_id=_text(payload.get('business_id')),
            capability_key=capability_key,
            route_key=route_key,
            action_type=_text(payload.get('action_type') or 'unknown'),
            executed=_bool(payload.get('executed')),
            verified=_bool(payload.get('verified')),
            achieved=_bool(payload.get('achieved') if 'achieved' in payload else payload.get('goal_reached')),
            verification_confidence=clamp(safe_float(payload.get('verification_confidence'), default=0.0)),
            cost=max(0.0, safe_float(economic.get('cost'), default=payload.get('cost') or 0.0)),
            revenue_delta=safe_float(economic.get('revenue_delta'), default=payload.get('revenue_delta') or 0.0),
            latency_ms=max(0.0, safe_float(payload.get('latency_ms'), default=0.0)),
            threshold_before=clamp(safe_float(thresholds.get('before'), default=0.60)),
            threshold_after=clamp(safe_float(thresholds.get('after'), default=0.60)),
            fingerprint=self._fingerprint(payload),
            raw_feedback=payload,
        )

    def batch(self, *, items: Iterable[Mapping[str, Any]]) -> list[AdaptationObservation]:
        return [self.normalize(feedback=item) for item in items]


__all__ = ['AdaptationObservation', 'FeedbackPipeline', 'FEEDBACK_PIPELINE_SCHEMA_VERSION']
