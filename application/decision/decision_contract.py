"""Neutral helper contract for the non-sovereign decision application service.

This module owns deterministic request normalization, trace construction, and
executable-action payload shaping for the recommendation-only application layer.
It is intentionally not a sovereign decision issuer.
"""

from __future__ import annotations

import shared.types as _shared_types
from core.constraints.decision import DecisionConstraints
from kernel.decision_candidate import DecisionCandidate
from kernel.decision_request import DecisionRequest
from kernel.decision_trace import DecisionTrace

NON_SOVEREIGN_ENGINE_ROLE = "recommendation_only"
NON_SOVEREIGN_ENGINE_SURFACE = "core.application.decision_service.DecisionService"


def canonical_request(
    *,
    constraints: DecisionConstraints,
    request: DecisionRequest | None,
) -> DecisionRequest:
    resolved = request or DecisionRequest(
        business_id="unknown_business",
        objective=constraints.objective_name,
        input_bundle_id="bundle_unknown",
        metadata={"defaulted": True, "engine_role": NON_SOVEREIGN_ENGINE_ROLE},
    )
    if resolved.objective != constraints.objective_name:
        raise ValueError("request objective must match decision constraints objective")
    if not resolved.business_id.strip():
        raise ValueError("request business_id must be non-empty")
    if not resolved.input_bundle_id.strip():
        raise ValueError("request input_bundle_id must be non-empty")
    return resolved


def start_trace(*, request: DecisionRequest, candidate_count: int) -> DecisionTrace:
    return DecisionTrace(
        request_id=request.request_id,
        steps=["decision_space_received"],
        metadata={
            "candidate_count": int(candidate_count),
            "business_id": request.business_id,
            "objective_name": request.objective,
            "input_bundle_id": request.input_bundle_id,
            "decision_engine_role": NON_SOVEREIGN_ENGINE_ROLE,
            "decision_surface": NON_SOVEREIGN_ENGINE_SURFACE,
        },
    )


def build_executable_action_payload(
    *,
    candidate: DecisionCandidate,
    trace: DecisionTrace,
    request: DecisionRequest,
    constraints: DecisionConstraints,
) -> dict[str, object]:
    return {
        "action_id": trace.decision_id.replace("decision_", "action_"),
        "action_type": candidate.action_type,
        "channel": candidate.channel,
        "payload": _shared_types.frozen_dict(candidate.payload, candidate_id=candidate.candidate_id),
        "decision_id": trace.decision_id,
        "correlation_id": request.request_id,
        "objective_name": constraints.objective_name,
    }


def build_executable_action(
    *,
    candidate: DecisionCandidate,
    trace: DecisionTrace,
    request: DecisionRequest,
    constraints: DecisionConstraints,
):
    from contracts import executable_action as executable_action_contract

    action_cls = getattr(executable_action_contract, 'ExecutableAction')
    return action_cls(
        **build_executable_action_payload(
            candidate=candidate,
            trace=trace,
            request=request,
            constraints=constraints,
        )
    )


__all__ = [
    "NON_SOVEREIGN_ENGINE_ROLE",
    "NON_SOVEREIGN_ENGINE_SURFACE",
    "build_executable_action",
    "build_executable_action_payload",
    "canonical_request",
    "start_trace",
]
