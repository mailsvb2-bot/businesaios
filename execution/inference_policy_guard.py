from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

from execution.inference_capacity_contract import InferenceCapacityTier


CANON_INFERENCE_POLICY_GUARD = True


def _safe_text(value: Any) -> str:
    return str(value or '').strip()


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class InferencePolicyEnvelope:
    tenant_id: str | None
    requested_tier: InferenceCapacityTier
    estimated_cost_usd: float
    expected_benefit_usd: float
    verification_mode: str
    distributed_network_enabled: bool
    premium_cloud_enabled: bool

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any] | None) -> 'InferencePolicyEnvelope':
        normalized = dict(payload or {})
        tier_text = _safe_text(normalized.get('inference_requested_tier') or normalized.get('requested_tier'))
        try:
            requested_tier = InferenceCapacityTier(tier_text) if tier_text else InferenceCapacityTier.LOCAL_GPU
        except ValueError:
            requested_tier = InferenceCapacityTier.LOCAL_GPU
        return cls(
            tenant_id=_safe_text(normalized.get('tenant_id')) or None,
            requested_tier=requested_tier,
            estimated_cost_usd=max(0.0, _safe_float(normalized.get('inference_estimated_cost_usd'))),
            expected_benefit_usd=max(0.0, _safe_float(normalized.get('inference_expected_benefit_usd'))),
            verification_mode=_safe_text(normalized.get('inference_verification_mode')) or 'standard',
            distributed_network_enabled=str(normalized.get('inference_distributed_enabled') or '').strip().lower() in {'1', 'true', 'yes', 'on'},
            premium_cloud_enabled=str(normalized.get('inference_premium_enabled') or '').strip().lower() in {'1', 'true', 'yes', 'on'},
        )


@dataclass(frozen=True)
class InferencePolicyVerdict:
    allowed: bool
    reason: str
    requires_human_review: bool
    metadata: Mapping[str, Any]


class InferencePolicyGuard:
    def evaluate(self, envelope: InferencePolicyEnvelope) -> InferencePolicyVerdict:
        reasons: list[str] = []
        requires_human_review = False
        if envelope.requested_tier == InferenceCapacityTier.DISTRIBUTED_GPU_NETWORK and not envelope.distributed_network_enabled:
            reasons.append('distributed_network_disabled')
        if envelope.requested_tier == InferenceCapacityTier.PREMIUM_EXTERNAL_CLOUD and not envelope.premium_cloud_enabled:
            reasons.append('premium_cloud_disabled')
        if envelope.requested_tier in {InferenceCapacityTier.DISTRIBUTED_GPU_NETWORK, InferenceCapacityTier.PREMIUM_EXTERNAL_CLOUD}:
            requires_human_review = envelope.estimated_cost_usd > 25.0
        if envelope.verification_mode == 'strict' and envelope.requested_tier == InferenceCapacityTier.CPU_FALLBACK:
            reasons.append('strict_verification_requires_stronger_tier')
        allowed = not reasons
        return InferencePolicyVerdict(
            allowed=allowed,
            reason='allowed' if allowed else ','.join(reasons),
            requires_human_review=requires_human_review,
            metadata={
                'requested_tier': envelope.requested_tier.value,
                'estimated_cost_usd': round(envelope.estimated_cost_usd, 6),
                'expected_benefit_usd': round(envelope.expected_benefit_usd, 6),
                'verification_mode': envelope.verification_mode,
            },
        )
