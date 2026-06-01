from __future__ import annotations

from runtime.decisioning import CandidateCollection, CandidateEnvelope
from runtime.reward import RewardObservationContext, RewardService

CANON_THIN_HANDLER = True


def handle_reward_observe_candidates(payload: dict, service: RewardService) -> dict:
    raw_items = payload.get("candidates", [])
    candidates = CandidateCollection.from_iterable(
        CandidateEnvelope(
            candidate_id=str(item["candidate_id"]),
            candidate_kind=str(item.get("candidate_kind", "reward_candidate")),
            payload=dict(item),
        )
        for item in raw_items
    )

    observations = service.observe_candidates(
        RewardObservationContext(
            tenant_id=str(payload["tenant_id"]),
            correlation_id=str(payload["correlation_id"]),
            candidates=candidates,
        )
    )

    return {
        "tenant_id": payload["tenant_id"],
        "correlation_id": payload["correlation_id"],
        "observations": [
            {
                "candidate_id": item.candidate_id,
                "observation_name": item.observation_name,
                "observation_value": item.observation_value,
                "details": dict(item.details),
            }
            for item in observations.items
        ],
    }
