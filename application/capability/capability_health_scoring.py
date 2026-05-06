from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from application.capability.capability_health_policy import CapabilityHealthPolicy
from application.capability.capability_matrix import CapabilityMatrix


CANON_CAPABILITY_HEALTH_SCORING = True
CAPABILITY_HEALTH_SCHEMA_VERSION = 2



def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}



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



def _text(value: object) -> str:
    return str(value or '').strip()



def _safe_key(value: object, *, fallback: str) -> str:
    token = _text(value)
    if not token:
        return fallback
    return token.replace('\\', '_').replace('/', '_').replace(':', '_').replace(' ', '_')


@dataclass(frozen=True)
class CapabilityHealthCounters:
    attempts: int = 0
    executed: int = 0
    verified: int = 0
    transient_failures: int = 0
    terminal_failures: int = 0
    blocked: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> 'CapabilityHealthCounters':
        return cls(
            attempts=max(0, _safe_int(payload.get('attempts'))),
            executed=max(0, _safe_int(payload.get('executed'))),
            verified=max(0, _safe_int(payload.get('verified'))),
            transient_failures=max(0, _safe_int(payload.get('transient_failures'))),
            terminal_failures=max(0, _safe_int(payload.get('terminal_failures'))),
            blocked=max(0, _safe_int(payload.get('blocked'))),
        )


@dataclass(frozen=True)
class CapabilityHealthSnapshot:
    schema_version: int = CAPABILITY_HEALTH_SCHEMA_VERSION
    tenant_id: str = ''
    capability_key: str = ''
    counters: CapabilityHealthCounters = field(default_factory=CapabilityHealthCounters)
    success_rate: float = 0.0
    verification_rate: float = 0.0
    transient_failure_rate: float = 0.0
    block_rate: float = 0.0
    health_score: float = 0.0
    health_tier: str = 'unknown'
    degraded: bool = False
    routing_state: str = 'observe'
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

    def to_dict(self) -> dict[str, Any]:
        return {
            'schema_version': int(self.schema_version),
            'tenant_id': str(self.tenant_id),
            'capability_key': str(self.capability_key),
            'counters': self.counters.to_dict(),
            'success_rate': float(self.success_rate),
            'verification_rate': float(self.verification_rate),
            'transient_failure_rate': float(self.transient_failure_rate),
            'block_rate': float(self.block_rate),
            'health_score': float(self.health_score),
            'health_tier': str(self.health_tier),
            'degraded': bool(self.degraded),
            'routing_state': str(self.routing_state),
            'updated_at': str(self.updated_at),
            'last_feedback_reason': str(self.last_feedback_reason),
            'confidence_score': float(self.confidence_score),
            'staleness_state': str(self.staleness_state),
            'evidence_state': str(self.evidence_state),
            'freshness_score': float(self.freshness_score),
            'recommended_autonomy_tier': str(self.recommended_autonomy_tier),
            'observation_count': int(self.observation_count),
            'first_observed_at': str(self.first_observed_at),
            'last_observed_at': str(self.last_observed_at),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> 'CapabilityHealthSnapshot':
        return cls(
            schema_version=max(1, _safe_int(payload.get('schema_version'), default=CAPABILITY_HEALTH_SCHEMA_VERSION)),
            tenant_id=_text(payload.get('tenant_id')),
            capability_key=_text(payload.get('capability_key')),
            counters=CapabilityHealthCounters.from_dict(_safe_dict(payload.get('counters'))),
            success_rate=max(0.0, min(1.0, _safe_float(payload.get('success_rate')))),
            verification_rate=max(0.0, min(1.0, _safe_float(payload.get('verification_rate')))),
            transient_failure_rate=max(0.0, min(1.0, _safe_float(payload.get('transient_failure_rate')))),
            block_rate=max(0.0, min(1.0, _safe_float(payload.get('block_rate')))),
            health_score=max(0.0, min(1.0, _safe_float(payload.get('health_score')))),
            health_tier=_text(payload.get('health_tier') or 'unknown') or 'unknown',
            degraded=bool(payload.get('degraded')),
            routing_state=_text(payload.get('routing_state') or 'observe') or 'observe',
            updated_at=_text(payload.get('updated_at')),
            last_feedback_reason=_text(payload.get('last_feedback_reason')),
            confidence_score=max(0.0, min(1.0, _safe_float(payload.get('confidence_score')))),
            staleness_state=_text(payload.get('staleness_state') or 'unknown') or 'unknown',
            evidence_state=_text(payload.get('evidence_state') or 'unknown') or 'unknown',
            freshness_score=max(0.0, min(1.0, _safe_float(payload.get('freshness_score')))),
            recommended_autonomy_tier=_text(payload.get('recommended_autonomy_tier') or 'supervised') or 'supervised',
            observation_count=max(0, _safe_int(payload.get('observation_count'))),
            first_observed_at=_text(payload.get('first_observed_at')),
            last_observed_at=_text(payload.get('last_observed_at')),
        )


class FileCapabilityHealthStore:
    def __init__(self, *, root_dir: Path) -> None:
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, *, tenant_id: str, capability_key: str) -> Path:
        return self._root_dir / _safe_key(tenant_id, fallback='default') / f"{_safe_key(capability_key, fallback='unknown')}.json"

    def load(self, *, tenant_id: str, capability_key: str) -> CapabilityHealthSnapshot:
        path = self._path(tenant_id=tenant_id, capability_key=capability_key)
        if not path.exists():
            return CapabilityHealthSnapshot(tenant_id=str(tenant_id), capability_key=str(capability_key))
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return CapabilityHealthSnapshot(tenant_id=str(tenant_id), capability_key=str(capability_key))
        return CapabilityHealthSnapshot.from_dict(payload)

    def save(self, snapshot: CapabilityHealthSnapshot) -> Path:
        path = self._path(tenant_id=snapshot.tenant_id, capability_key=snapshot.capability_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        fd, temp_name = tempfile.mkstemp(prefix='.cap_health_', suffix='.json', dir=str(path.parent))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return path


class CapabilityHealthScoringService:
    def __init__(self, *, store: FileCapabilityHealthStore, policy: CapabilityHealthPolicy | None = None, matrix: CapabilityMatrix | None = None) -> None:
        self._store = store
        self._policy = policy or CapabilityHealthPolicy()
        self._matrix = matrix or CapabilityMatrix()

    def _canonical_capability_key(self, raw_key: str) -> str:
        normalized = _text(raw_key)
        if not normalized:
            return normalized
        try:
            descriptor = self._matrix.descriptor_for_action(normalized)
        except Exception:
            return normalized
        descriptor_action = _text(getattr(descriptor, 'action_type', ''))
        descriptor_capability = _text(getattr(descriptor, 'capability_key', ''))
        if descriptor_action == normalized and descriptor_capability:
            return descriptor_capability
        return normalized

    def _runtime_payload(self, snapshot: CapabilityHealthSnapshot, *, capability_key: str) -> dict[str, Any]:
        return {
            'enabled': snapshot.routing_state != 'disabled',
            'healthy': snapshot.health_tier == 'healthy',
            'degraded': bool(snapshot.degraded),
            'health_score': snapshot.health_score,
            'health_tier': snapshot.health_tier,
            'verification_rate': snapshot.verification_rate,
            'success_rate': snapshot.success_rate,
            'routing_state': snapshot.routing_state,
            'updated_at': snapshot.updated_at,
            'last_feedback_reason': snapshot.last_feedback_reason,
            'confidence_score': snapshot.confidence_score,
            'staleness_state': snapshot.staleness_state,
            'evidence_state': snapshot.evidence_state,
            'freshness_score': snapshot.freshness_score,
            'recommended_autonomy_tier': snapshot.recommended_autonomy_tier,
            'observation_count': snapshot.observation_count,
            'first_observed_at': snapshot.first_observed_at,
            'last_observed_at': snapshot.last_observed_at,
            'capability_key': capability_key,
            'source': 'capability_health_scoring',
        }

    def load_runtime_snapshot(self, *, tenant_id: str, capability_keys: list[str]) -> dict[str, Any]:
        if not _text(tenant_id):
            raise ValueError('tenant_id must not be empty')
        result: dict[str, Any] = {}
        seen: set[str] = set()
        for raw_key in capability_keys:
            key = _text(raw_key)
            if not key or key in seen:
                continue
            seen.add(key)
            canonical_key = self._canonical_capability_key(key)
            snapshot = self._store.load(tenant_id=tenant_id, capability_key=canonical_key)
            result[str(key)] = self._runtime_payload(snapshot, capability_key=canonical_key)
        return result

    def load_runtime_snapshot_for_actions(self, *, tenant_id: str, action_types: list[str]) -> dict[str, Any]:
        if not _text(tenant_id):
            raise ValueError('tenant_id must not be empty')
        result: dict[str, Any] = {}
        seen: set[str] = set()
        for raw_action_type in action_types:
            action_type = _text(raw_action_type)
            if not action_type or action_type in seen:
                continue
            seen.add(action_type)
            descriptor = self._matrix.descriptor_for_action(action_type)
            snapshot = self._store.load(tenant_id=tenant_id, capability_key=descriptor.capability_key)
            result[descriptor.action_type] = self._runtime_payload(snapshot, capability_key=descriptor.capability_key)
        return result

    def update_after_step(self, *, tenant_id: str, capability_key: str, feedback: Mapping[str, Any] | None) -> dict[str, Any]:
        if not _text(tenant_id):
            raise ValueError('tenant_id must not be empty')
        if not _text(capability_key):
            raise ValueError('capability_key must not be empty')
        payload = _safe_dict(feedback)
        canonical_key = self._canonical_capability_key(capability_key)
        current = self._store.load(tenant_id=tenant_id, capability_key=canonical_key)
        counters = current.counters
        retry = _safe_dict(payload.get('self_healing_retry'))
        retry_reason = _text(retry.get('reason')).lower()
        blocked = bool(payload.get('blocked_by_policy') or payload.get('approval_required'))
        executed = bool(payload.get('executed'))
        verified = bool(payload.get('verified'))
        transient = 'transient' in retry_reason or 'rate_limit' in retry_reason or 'retry' in retry_reason
        terminal_failure = bool(not executed and not blocked and not transient)
        observed_at = _text(payload.get('updated_at') or payload.get('finished_at') or payload.get('recorded_at') or current.updated_at)
        next_counters = CapabilityHealthCounters(
            attempts=counters.attempts + 1,
            executed=counters.executed + int(executed),
            verified=counters.verified + int(verified),
            transient_failures=counters.transient_failures + int(transient),
            terminal_failures=counters.terminal_failures + int(terminal_failure),
            blocked=counters.blocked + int(blocked),
        )
        policy_view = self._policy.build_view(counters=next_counters.to_dict(), updated_at=observed_at or current.updated_at)
        first_observed_at = current.first_observed_at or observed_at
        next_snapshot = CapabilityHealthSnapshot(
            schema_version=CAPABILITY_HEALTH_SCHEMA_VERSION,
            tenant_id=str(tenant_id),
            capability_key=str(canonical_key),
            counters=next_counters,
            success_rate=policy_view.success_rate,
            verification_rate=policy_view.verification_rate,
            transient_failure_rate=policy_view.transient_failure_rate,
            block_rate=policy_view.block_rate,
            health_score=policy_view.health_score,
            health_tier=policy_view.health_tier,
            degraded=policy_view.degraded,
            routing_state=policy_view.routing_state,
            updated_at=observed_at,
            last_feedback_reason=_text(payload.get('failure_reason') or payload.get('reason') or payload.get('policy_reason') or retry.get('reason') or payload.get('verification_status') or current.last_feedback_reason),
            confidence_score=policy_view.confidence_score,
            staleness_state=policy_view.staleness_state,
            evidence_state=policy_view.evidence_state,
            freshness_score=policy_view.freshness_score,
            recommended_autonomy_tier=policy_view.recommended_autonomy_tier,
            observation_count=current.observation_count + 1,
            first_observed_at=first_observed_at,
            last_observed_at=observed_at or current.last_observed_at,
        )
        self._store.save(next_snapshot)
        return next_snapshot.to_dict()

    def update_after_action_step(self, *, tenant_id: str, action_type: str, feedback: Mapping[str, Any] | None) -> dict[str, Any]:
        descriptor = self._matrix.descriptor_for_action(action_type)
        return self.update_after_step(tenant_id=tenant_id, capability_key=descriptor.capability_key, feedback=feedback)


__all__ = ['CANON_CAPABILITY_HEALTH_SCORING','CAPABILITY_HEALTH_SCHEMA_VERSION','CapabilityHealthCounters','CapabilityHealthSnapshot','FileCapabilityHealthStore','CapabilityHealthScoringService']
