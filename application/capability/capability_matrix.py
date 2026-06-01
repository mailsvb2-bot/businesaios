from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from application.capability.action_capability_matrix import (
    ActionCapability,
    build_action_capability_matrix,
    get_action_capability,
)

CANON_CAPABILITY_MATRIX = True



def _text(value: object) -> str:
    return str(value or '').strip()



def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)



def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)



def _safe_bool(value: object, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    token = _text(value).lower()
    if token in {'1', 'true', 'yes', 'on'}:
        return True
    if token in {'0', 'false', 'no', 'off'}:
        return False
    return bool(default)



def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(frozen=True)
class CapabilityDescriptor:
    action_type: str
    capability_key: str
    decisionable: bool
    routable: bool
    executable: bool
    externally_verified: bool
    idempotent: bool
    reversible: bool
    approval_required: bool
    bounded_by_blast_radius: bool
    prod_ready: bool
    notes: tuple[str, ...] = ()

    @classmethod
    def from_action_capability(cls, value: ActionCapability) -> CapabilityDescriptor:
        return cls(
            action_type=str(value.action_type),
            capability_key=str(value.action_class),
            decisionable=bool(value.decisionable),
            routable=bool(value.routable),
            executable=bool(value.executable),
            externally_verified=bool(value.externally_verified),
            idempotent=bool(value.idempotent),
            reversible=bool(value.reversible),
            approval_required=bool(value.approval_required),
            bounded_by_blast_radius=bool(value.bounded_by_blast_radius),
            prod_ready=bool(value.prod_ready),
            notes=tuple(str(item) for item in value.notes),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'action_type': self.action_type,
            'capability_key': self.capability_key,
            'decisionable': self.decisionable,
            'routable': self.routable,
            'executable': self.executable,
            'externally_verified': self.externally_verified,
            'idempotent': self.idempotent,
            'reversible': self.reversible,
            'approval_required': self.approval_required,
            'bounded_by_blast_radius': self.bounded_by_blast_radius,
            'prod_ready': self.prod_ready,
            'notes': list(self.notes),
        }


@dataclass(frozen=True)
class RuntimeCapabilitySnapshot:
    action_type: str
    capability_key: str
    enabled: bool = True
    healthy: bool = True
    degraded: bool = False
    health_score: float = 1.0
    health_tier: str = 'unknown'
    routing_state: str = 'observe'
    verification_rate: float = 0.0
    success_rate: float = 0.0
    estimated_cost: float = 0.0
    base_cost: float = 0.0
    base_latency_ms: float = 0.0
    base_proofability: float = 0.0
    source: str = 'runtime'
    updated_at: str = ''
    last_feedback_reason: str = ''
    confidence_score: float = 0.0
    staleness_state: str = 'unknown'
    evidence_state: str = 'unknown'
    freshness_score: float = 0.0
    recommended_autonomy_tier: str = 'supervised'
    observation_count: int = 0
    first_observed_at: str = ''
    last_observed_at: str = ''
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, *, action_type: str, capability_key: str, payload: Mapping[str, Any] | None) -> RuntimeCapabilitySnapshot:
        raw = _safe_dict(payload)
        health_score = max(0.0, min(1.0, _safe_float(raw.get('health_score'), default=1.0)))
        enabled = _safe_bool(raw.get('enabled'), default=True)
        observation_count = max(0, _safe_int(raw.get('observation_count')))
        staleness_state = _text(raw.get('staleness_state') or 'unknown') or 'unknown'
        healthy_raw = raw.get('healthy')
        if healthy_raw is None:
            healthy = health_score >= 0.80 and staleness_state != 'stale'
        else:
            healthy = _safe_bool(healthy_raw, default=health_score >= 0.80)
        degraded = _safe_bool(raw.get('degraded'), default=(enabled and not healthy and health_score >= 0.35))
        health_tier = _text(raw.get('health_tier') or '')
        if not health_tier or (healthy and health_tier in {'unknown', 'unhealthy'}) or (not healthy and health_tier == 'healthy'):
            if not enabled:
                health_tier = 'disabled'
            elif healthy:
                health_tier = 'healthy'
            elif degraded or health_score >= 0.35:
                health_tier = 'degraded'
            else:
                health_tier = 'unhealthy'
        routing_state = _text(raw.get('routing_state') or '')
        if not routing_state or (healthy and routing_state in {'observe', 'fallback_preferred'}) or (not enabled and routing_state != 'disabled'):
            if not enabled:
                routing_state = 'disabled'
            elif healthy:
                routing_state = 'enabled'
            elif degraded or health_score >= 0.35:
                routing_state = 'fallback_preferred'
            else:
                routing_state = 'observe'
        confidence_score = max(0.0, min(1.0, _safe_float(raw.get('confidence_score'), default=0.0)))
        if healthy:
            confidence_floor = 0.50 if observation_count > 0 else 0.35
            confidence_score = max(confidence_score, min(1.0, max(health_score, confidence_floor)))
        evidence_state = _text(raw.get('evidence_state') or 'unknown') or 'unknown'
        has_verified_observations = observation_count > 0 or _safe_float(raw.get('verification_rate')) > 0.0 or _safe_float(raw.get('success_rate')) > 0.0
        if healthy and evidence_state in {'unknown', 'insufficient'} and has_verified_observations:
            evidence_state = 'sufficient'
        elif evidence_state == 'unknown' and observation_count == 0 and healthy:
            evidence_state = 'insufficient'
        recommended_autonomy_tier = _text(raw.get('recommended_autonomy_tier') or 'supervised') or 'supervised'
        if healthy and recommended_autonomy_tier == 'supervised':
            recommended_autonomy_tier = 'bounded_autonomy'
        if evidence_state in {'unknown', 'insufficient'} and recommended_autonomy_tier == 'full_autonomy':
            recommended_autonomy_tier = 'bounded_autonomy'
        return cls(
            action_type=_text(action_type),
            capability_key=_text(capability_key),
            enabled=enabled,
            healthy=bool(healthy),
            degraded=degraded,
            health_score=health_score,
            health_tier=health_tier,
            routing_state=routing_state,
            verification_rate=max(0.0, min(1.0, _safe_float(raw.get('verification_rate')))),
            success_rate=max(0.0, min(1.0, _safe_float(raw.get('success_rate')))),
            estimated_cost=max(0.0, _safe_float(raw.get('estimated_cost'))),
            base_cost=max(0.0, _safe_float(raw.get('base_cost'))),
            base_latency_ms=max(0.0, _safe_float(raw.get('base_latency_ms'))),
            base_proofability=max(0.0, min(1.0, _safe_float(raw.get('base_proofability')))),
            source=_text(raw.get('source') or 'runtime') or 'runtime',
            updated_at=_text(raw.get('updated_at')),
            last_feedback_reason=_text(raw.get('last_feedback_reason')),
            confidence_score=confidence_score,
            staleness_state=staleness_state,
            evidence_state=evidence_state,
            freshness_score=max(0.0, min(1.0, _safe_float(raw.get('freshness_score')))),
            recommended_autonomy_tier=recommended_autonomy_tier,
            observation_count=observation_count,
            first_observed_at=_text(raw.get('first_observed_at')),
            last_observed_at=_text(raw.get('last_observed_at')),
            metadata={k: v for k, v in raw.items() if k not in {'enabled','healthy','degraded','health_score','health_tier','routing_state','verification_rate','success_rate','estimated_cost','base_cost','base_latency_ms','base_proofability','source','updated_at','last_feedback_reason','confidence_score','staleness_state','evidence_state','freshness_score','recommended_autonomy_tier','observation_count','first_observed_at','last_observed_at'}},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'action_type': self.action_type,
            'capability_key': self.capability_key,
            'enabled': self.enabled,
            'healthy': self.healthy,
            'degraded': self.degraded,
            'health_score': self.health_score,
            'health_tier': self.health_tier,
            'routing_state': self.routing_state,
            'verification_rate': self.verification_rate,
            'success_rate': self.success_rate,
            'estimated_cost': self.estimated_cost,
            'base_cost': self.base_cost,
            'base_latency_ms': self.base_latency_ms,
            'base_proofability': self.base_proofability,
            'source': self.source,
            'updated_at': self.updated_at,
            'last_feedback_reason': self.last_feedback_reason,
            'confidence_score': self.confidence_score,
            'staleness_state': self.staleness_state,
            'evidence_state': self.evidence_state,
            'freshness_score': self.freshness_score,
            'recommended_autonomy_tier': self.recommended_autonomy_tier,
            'observation_count': self.observation_count,
            'first_observed_at': self.first_observed_at,
            'last_observed_at': self.last_observed_at,
            'metadata': dict(self.metadata),
        }


@dataclass(frozen=True)
class CapabilityRecord:
    descriptor: CapabilityDescriptor
    runtime: RuntimeCapabilitySnapshot

    @property
    def action_type(self) -> str:
        return self.descriptor.action_type

    @property
    def capability_key(self) -> str:
        return self.descriptor.capability_key

    def advisory_flags(self) -> dict[str, Any]:
        flags = {
            'decisionable': self.descriptor.decisionable,
            'routable': self.descriptor.routable,
            'executable': self.descriptor.executable,
            'approval_required': self.descriptor.approval_required,
            'prod_ready': self.descriptor.prod_ready,
            'externally_verified': self.descriptor.externally_verified,
            'bounded_by_blast_radius': self.descriptor.bounded_by_blast_radius,
            'enabled': self.runtime.enabled,
            'healthy': self.runtime.healthy,
            'degraded': self.runtime.degraded,
            'routing_state': self.runtime.routing_state,
        }
        if self.runtime.health_score < 0.35:
            flags['fallback_preferred'] = True
        if self.runtime.staleness_state == 'stale':
            flags['stale_evidence'] = True
        if self.runtime.evidence_state in {'unknown', 'insufficient'}:
            flags['insufficient_evidence'] = True
        if self.runtime.confidence_score < 0.35:
            flags['low_confidence'] = True
        if self.descriptor.approval_required:
            flags['approval_gate_required'] = True
        if not self.descriptor.prod_ready:
            flags['non_prod_ready'] = True
        return flags

    def to_dict(self) -> dict[str, Any]:
        return {
            'descriptor': self.descriptor.to_dict(),
            'runtime': self.runtime.to_dict(),
            'advisory_flags': self.advisory_flags(),
        }


class CapabilityMatrix:
    def __init__(self) -> None:
        self._by_action_type: dict[str, CapabilityDescriptor] = {}
        self._action_types_by_capability: dict[str, tuple[str, ...]] = {}
        temp: dict[str, list[str]] = {}
        for item in build_action_capability_matrix():
            descriptor = CapabilityDescriptor.from_action_capability(item)
            self._by_action_type[descriptor.action_type] = descriptor
            temp.setdefault(descriptor.capability_key, []).append(descriptor.action_type)
        self._action_types_by_capability = {k: tuple(sorted(set(v))) for k, v in temp.items()}

    def known_action_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_action_type.keys()))

    def action_types_for_capability(self, capability_key: str) -> tuple[str, ...]:
        return self._action_types_by_capability.get(_text(capability_key), ())

    def descriptor_for_action(self, action_type: str) -> CapabilityDescriptor:
        normalized = _text(action_type)
        if normalized in self._by_action_type:
            return self._by_action_type[normalized]
        return CapabilityDescriptor.from_action_capability(get_action_capability(normalized))

    def runtime_snapshot_for_action(self, *, action_type: str, runtime_capabilities: Mapping[str, Any] | None) -> RuntimeCapabilitySnapshot:
        descriptor = self.descriptor_for_action(action_type)
        runtime_map = _safe_dict(runtime_capabilities)
        payload = _safe_dict(runtime_map.get(descriptor.action_type))
        if not payload:
            payload = _safe_dict(runtime_map.get(descriptor.action_type.lower()))
        return RuntimeCapabilitySnapshot.from_payload(action_type=descriptor.action_type, capability_key=descriptor.capability_key, payload=payload)

    def record_for_action(self, *, action_type: str, runtime_capabilities: Mapping[str, Any] | None) -> CapabilityRecord:
        descriptor = self.descriptor_for_action(action_type)
        runtime = self.runtime_snapshot_for_action(action_type=descriptor.action_type, runtime_capabilities=runtime_capabilities)
        return CapabilityRecord(descriptor=descriptor, runtime=runtime)

    def records_for_actions(self, *, action_types: Iterable[str], runtime_capabilities: Mapping[str, Any] | None) -> tuple[CapabilityRecord, ...]:
        result: list[CapabilityRecord] = []
        seen: set[str] = set()
        for raw_action_type in action_types:
            action_type = _text(raw_action_type)
            if not action_type or action_type in seen:
                continue
            seen.add(action_type)
            result.append(self.record_for_action(action_type=action_type, runtime_capabilities=runtime_capabilities))
        return tuple(result)


__all__ = ['CANON_CAPABILITY_MATRIX', 'CapabilityDescriptor', 'RuntimeCapabilitySnapshot', 'CapabilityRecord', 'CapabilityMatrix']
