from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from application.capability.capability_health_policy import CapabilityHealthPolicy
from application.capability.capability_health_scoring import (
    CapabilityHealthCounters,
    CapabilityHealthSnapshot,
    FileCapabilityHealthStore,
)
from application.capability.capability_matrix import CapabilityMatrix

CANON_CAPABILITY_HEALTH_REGISTRY = True



def _text(value: object) -> str:
    return str(value or '').strip()



def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(frozen=True)
class CapabilityHealthRegistryEntry:
    tenant_id: str
    action_type: str
    capability_key: str
    snapshot: CapabilityHealthSnapshot

    def to_runtime_payload(self) -> dict[str, Any]:
        return {
            'enabled': self.snapshot.routing_state != 'disabled',
            'healthy': self.snapshot.health_tier == 'healthy',
            'degraded': bool(self.snapshot.degraded),
            'health_score': float(self.snapshot.health_score),
            'health_tier': str(self.snapshot.health_tier),
            'routing_state': str(self.snapshot.routing_state),
            'verification_rate': float(self.snapshot.verification_rate),
            'success_rate': float(self.snapshot.success_rate),
            'updated_at': str(self.snapshot.updated_at),
            'last_feedback_reason': str(self.snapshot.last_feedback_reason),
            'confidence_score': float(self.snapshot.confidence_score),
            'staleness_state': str(self.snapshot.staleness_state),
            'evidence_state': str(self.snapshot.evidence_state),
            'freshness_score': float(self.snapshot.freshness_score),
            'recommended_autonomy_tier': str(self.snapshot.recommended_autonomy_tier),
            'observation_count': int(self.snapshot.observation_count),
            'first_observed_at': str(self.snapshot.first_observed_at),
            'last_observed_at': str(self.snapshot.last_observed_at),
            'source': 'capability_health_registry',
            'capability_key': self.capability_key,
        }


class CapabilityHealthRegistry:
    def __init__(self, *, store: FileCapabilityHealthStore | None = None, root_dir: str | Path | None = None, matrix: CapabilityMatrix | None = None, policy: CapabilityHealthPolicy | None = None) -> None:
        if store is not None and root_dir is not None:
            raise ValueError('pass either store or root_dir, not both')
        self._store = store or FileCapabilityHealthStore(root_dir=Path(root_dir or '.runtime/capability_health'))
        self._matrix = matrix or CapabilityMatrix()
        self._policy = policy or CapabilityHealthPolicy()

    def _descriptor(self, action_type: str):
        descriptor = self._matrix.descriptor_for_action(action_type)
        if not _text(descriptor.action_type):
            raise ValueError('action_type must not be empty')
        if not _text(descriptor.capability_key):
            raise ValueError('capability_key must not be empty')
        return descriptor

    def get_entry(self, *, tenant_id: str, action_type: str) -> CapabilityHealthRegistryEntry:
        normalized_tenant = _text(tenant_id)
        if not normalized_tenant:
            raise ValueError('tenant_id must not be empty')
        descriptor = self._descriptor(action_type)
        snapshot = self._store.load(tenant_id=normalized_tenant, capability_key=descriptor.capability_key)
        return CapabilityHealthRegistryEntry(tenant_id=normalized_tenant, action_type=descriptor.action_type, capability_key=descriptor.capability_key, snapshot=snapshot)

    def runtime_payload_for_action(self, *, tenant_id: str, action_type: str) -> dict[str, Any]:
        return self.get_entry(tenant_id=tenant_id, action_type=action_type).to_runtime_payload()

    def runtime_capabilities_for_actions(self, *, tenant_id: str, action_types: Iterable[str], existing_runtime_capabilities: Mapping[str, Any] | None = None) -> dict[str, Any]:
        merged = dict(_safe_dict(existing_runtime_capabilities))
        seen: set[str] = set()
        for raw_action_type in action_types:
            action_type = _text(raw_action_type)
            if not action_type or action_type in seen:
                continue
            seen.add(action_type)
            entry = self.get_entry(tenant_id=tenant_id, action_type=action_type)
            base_payload = _safe_dict(merged.get(entry.action_type))
            merged[entry.action_type] = {**entry.to_runtime_payload(), **base_payload}
        return merged

    def warmup_actions(self, *, tenant_id: str, action_types: Iterable[str]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for raw_action_type in action_types:
            action_type = _text(raw_action_type)
            if not action_type:
                continue
            entry = self.get_entry(tenant_id=tenant_id, action_type=action_type)
            result[entry.action_type] = entry.to_runtime_payload()
        return result

    def update_after_feedback(self, *, tenant_id: str, action_type: str, feedback: Mapping[str, Any] | None) -> CapabilityHealthRegistryEntry:
        normalized_tenant = _text(tenant_id)
        if not normalized_tenant:
            raise ValueError('tenant_id must not be empty')
        descriptor = self._descriptor(action_type)
        payload = _safe_dict(feedback)
        current = self._store.load(tenant_id=normalized_tenant, capability_key=descriptor.capability_key)
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
        next_snapshot = CapabilityHealthSnapshot(
            schema_version=max(current.schema_version, 2),
            tenant_id=normalized_tenant,
            capability_key=descriptor.capability_key,
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
            first_observed_at=current.first_observed_at or observed_at,
            last_observed_at=observed_at or current.last_observed_at,
        )
        self._store.save(next_snapshot)
        return CapabilityHealthRegistryEntry(tenant_id=normalized_tenant, action_type=descriptor.action_type, capability_key=descriptor.capability_key, snapshot=next_snapshot)


__all__ = ['CANON_CAPABILITY_HEALTH_REGISTRY','CapabilityHealthRegistryEntry','CapabilityHealthRegistry']
