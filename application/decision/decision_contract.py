"""Neutral helpers for the non-sovereign recommendation application service.

This module owns deterministic request normalization and recommendation trace
construction only. It must never shape an executable action, issue a signed
decision, or define an execution contract.
"""

from __future__ import annotations

from core.constraints.decision import DecisionConstraints
from kernel.decision_request import DecisionRequest
from kernel.decision_trace import DecisionTrace

NON_SOVEREIGN_ENGINE_ROLE = "recommendation_only"
NON_SOVEREIGN_ENGINE_SURFACE = (
    "application.decision.decision_service.DecisionService"
)
CANON_RECOMMENDATION_CONTRACT_NO_EXECUTABLE_ACTION = True


def canonical_request(
    *,
    constraints: DecisionConstraints,
    request: DecisionRequest | None,
) -> DecisionRequest:
    resolved = request or DecisionRequest(
        business_id="unknown_business",
        objective=constraints.objective_name,
        input_bundle_id="bundle_unknown",
        metadata={
            "defaulted": True,
            "engine_role": NON_SOVEREIGN_ENGINE_ROLE,
        },
    )
    if resolved.objective != constraints.objective_name:
        raise ValueError(
            "request objective must match decision constraints objective"
        )
    if not resolved.business_id.strip():
        raise ValueError("request business_id must be non-empty")
    if not resolved.input_bundle_id.strip():
        raise ValueError("request input_bundle_id must be non-empty")
    return resolved


def start_trace(
    *,
    request: DecisionRequest,
    candidate_count: int,
) -> DecisionTrace:
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
            "executable": False,
        },
    )


__all__ = [
    "CANON_RECOMMENDATION_CONTRACT_NO_EXECUTABLE_ACTION",
    "NON_SOVEREIGN_ENGINE_ROLE",
    "NON_SOVEREIGN_ENGINE_SURFACE",
    "canonical_request",
    "start_trace",
]
