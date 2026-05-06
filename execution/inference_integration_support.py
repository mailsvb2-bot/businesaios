from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from execution.inference_capacity_contract import InferenceCapacityTier
from execution.inference_capacity_policy import InferenceCapacityPolicyContext
from execution.inference_execution_result_contract import InferenceExecutionRecord
from execution.inference_provider_contract import InferenceRequest


CANON_INFERENCE_INTEGRATION_SUPPORT = True


@dataclass(frozen=True)
class InferenceExecutionIntent:
    decision_id: str
    request_id: str
    model: str
    prompt: str
    max_output_tokens: int
    preferred_tier: InferenceCapacityTier
    tenant_id: str | None = None
    metadata: Mapping[str, Any] | None = None


def build_inference_policy_context(
    *,
    tenant_id: str | None,
    distributed_network_enabled: bool,
    premium_cloud_enabled: bool,
    max_allowed_tier: InferenceCapacityTier,
) -> InferenceCapacityPolicyContext:
    return InferenceCapacityPolicyContext(
        tenant_id=tenant_id,
        distributed_network_enabled=distributed_network_enabled,
        premium_cloud_enabled=premium_cloud_enabled,
        max_allowed_tier=max_allowed_tier,
    )


def build_inference_request(intent: InferenceExecutionIntent) -> InferenceRequest:
    return InferenceRequest(
        request_id=intent.request_id,
        model=intent.model,
        prompt=intent.prompt,
        max_output_tokens=intent.max_output_tokens,
        metadata=dict(intent.metadata or {}),
    )


def inference_record_to_audit_payload(record: InferenceExecutionRecord) -> dict[str, object]:
    return {
        'selected_provider': record.selected_provider,
        'selected_tier': record.selected_tier,
        'verification_accepted': record.verification.accepted,
        'verification_reason': record.verification.reason,
        'estimated_cost_usd': record.evidence.get('estimated_cost_usd', '0'),
        'latency_ms': record.response.latency_ms,
    }
