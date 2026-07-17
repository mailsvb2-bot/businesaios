"""Canonical policy for selecting a demand-network lead route.

Candidate preparation remains outside DecisionCore, but the final winner and the
signed ``route_lead@v1`` action are produced only while this policy is executing
inside the canonical DecisionCore ring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.actions.names import ACTION_ROUTE_LEAD_V1
from core.constraints.decision import DecisionConstraints
from core.policies.telegram.helpers import ProposedAction
from core.policy.decision_validator import DecisionValidator
from core.scorers.selector import DecisionSelector
from kernel.decision_candidate import DecisionCandidate
from kernel.world_state import WorldStateV1
from shared.numbers import coerce_float

CANON_DEMAND_ROUTE_POLICY = True


def _candidate_from_mapping(
    raw: dict[str, Any],
    *,
    request_id: str,
) -> DecisionCandidate:
    business_id = str(raw.get("business_id") or "").strip()
    return DecisionCandidate(
        action_type="route_lead",
        channel=str(raw.get("channel") or "").strip(),
        score=coerce_float(raw.get("score"), 0.0, minimum=0.0),
        expected_value=coerce_float(
            raw.get("expected_value"),
            0.0,
            minimum=0.0,
        ),
        confidence=coerce_float(
            raw.get("confidence"),
            0.0,
            minimum=0.0,
            maximum=1.0,
        ),
        reasons=[str(item) for item in raw.get("reasons") or ()],
        payload=dict(raw.get("payload") or {}),
        candidate_id=str(
            raw.get("candidate_id")
            or f"demand-route:{request_id}:{business_id}"
        ),
    )


def _route_input(state: WorldStateV1) -> dict[str, Any]:
    meta = getattr(state, "meta", None) or {}
    if not isinstance(meta, dict):
        return {}
    route = meta.get("demand_route")
    return dict(route) if isinstance(route, dict) else {}


@dataclass(frozen=True)
class DemandRoutePolicyV1:
    id: str = "demand_route@v1"

    def propose(self, state: WorldStateV1) -> ProposedAction:
        route = _route_input(state)
        request_id = str(route.get("request_id") or "").strip()
        raw_constraints = route.get("constraints")
        constraints = DecisionConstraints(
            **(
                dict(raw_constraints)
                if isinstance(raw_constraints, dict)
                else {}
            )
        )
        constraints.validate()

        raw_candidates = tuple(route.get("candidates") or ())
        candidates: list[DecisionCandidate] = []
        rejected: list[dict[str, str]] = []
        validator = DecisionValidator()
        for item in raw_candidates:
            if not isinstance(item, dict):
                rejected.append(
                    {"candidate_id": "", "reason": "candidate_not_object"}
                )
                continue
            candidate = _candidate_from_mapping(
                dict(item),
                request_id=request_id,
            )
            validation_issues = candidate.validate()
            if validation_issues:
                rejected.extend(
                    {
                        "candidate_id": candidate.candidate_id,
                        "reason": reason,
                    }
                    for reason in validation_issues
                )
                continue
            valid, reason = validator.validate(candidate, constraints)
            if not valid:
                rejected.append(
                    {
                        "candidate_id": candidate.candidate_id,
                        "reason": reason,
                    }
                )
                continue
            candidates.append(candidate)

        selected = DecisionSelector().select(candidates)
        payload: dict[str, Any] = {
            "idempotency_key": f"demand-route:{request_id}",
            "request_id": request_id,
            "requires_manual_review": selected is None,
            # Historical public trace counted all prepared, non-blocked inputs.
            "candidate_count": len(raw_candidates),
            "eligible_candidate_count": len(candidates),
            "blocked_candidate_count": int(
                route.get("blocked_candidate_count") or 0
            ),
            "runner_up_business_ids": [],
            "rejections": rejected,
        }

        if selected is None:
            payload["manual_review_reason"] = str(
                route.get("manual_review_reason")
                or "decision_core_rejected_all_candidates"
            )
        else:
            selected_business_id = str(
                selected.payload.get("business_id") or ""
            ).strip()
            payload.update(
                {
                    "selected_business_id": selected_business_id,
                    "delivery_channel": str(selected.channel),
                    "selected_candidate_id": selected.candidate_id,
                    "selection_score": float(
                        selected.objective_score()
                    ),
                    "runner_up_business_ids": [
                        str(candidate.payload.get("business_id") or "").strip()
                        for candidate in candidates
                        if str(
                            candidate.payload.get("business_id") or ""
                        ).strip()
                        and candidate.candidate_id != selected.candidate_id
                    ],
                }
            )

        return ProposedAction(
            action=ACTION_ROUTE_LEAD_V1,
            payload=payload,
        )


__all__ = [
    "CANON_DEMAND_ROUTE_POLICY",
    "DemandRoutePolicyV1",
]
