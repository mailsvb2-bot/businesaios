from __future__ import annotations

from runtime.decisioning import CandidateCollection
from runtime.decisioning import CandidateEnvelope
from runtime.growth import GrowthScoringContext
from runtime.growth import GrowthService

CANON_THIN_HANDLER = True


def handle_growth_score_candidates(payload: dict, service: GrowthService) -> dict:
    raw_items = payload.get("candidates", [])
    candidates = CandidateCollection.from_iterable(
        CandidateEnvelope(
            candidate_id=str(item["candidate_id"]),
            candidate_kind=str(item.get("candidate_kind", "growth_proposal")),
            payload=dict(item),
        )
        for item in raw_items
    )

    score_set = service.score_candidates(
        GrowthScoringContext(
            tenant_id=str(payload["tenant_id"]),
            correlation_id=str(payload["correlation_id"]),
            candidates=candidates,
        )
    )

    return {
        "tenant_id": payload["tenant_id"],
        "correlation_id": payload["correlation_id"],
        "scores": [
            {
                "candidate_id": item.candidate_id,
                "score_name": item.score_name,
                "score_value": item.score_value,
                "explanation": item.explanation,
            }
            for item in score_set.items
        ],
    }
