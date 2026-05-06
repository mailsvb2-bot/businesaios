from __future__ import annotations

from typing import Any, Dict, Iterable, List

from core.actions.names import ACTION_GROWTH_PROPOSAL_APPLY_V1
from kernel.decisioning.route_contract import canonical_runtime_route


class GrowthProposalService:
    """Proposal-only service.

    Important:
      - prepares growth proposals
      - may queue proposals through gateway
      - must not apply policy directly
      - must not emit actions on its own
    """

    def build_proposals(
        self,
        *,
        tenant_id: str,
        objective: str,
        signals: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        proposals: List[Dict[str, Any]] = []
        if float(signals.get("conversion_rate", 0.0) or 0.0) < 0.02:
            proposals.append(
                {
                    "kind": "creative_refresh",
                    "objective": objective,
                    "reason": "low_conversion_rate",
                }
            )
        if float(signals.get("roas", 0.0) or 0.0) > 2.0:
            proposals.append(
                {
                    "kind": "budget_expand",
                    "objective": objective,
                    "reason": "strong_roas",
                }
            )
        return proposals

    def queue(
        self,
        *,
        gateway: Any,
        tenant_id: str,
        decision_id: str,
        correlation_id: str,
        issuer_id: str,
        proposals: Iterable[Dict[str, Any]],
    ) -> int:
        queued = 0
        for proposal in proposals:
            gateway.propose(
                tenant_id=tenant_id,
                action=ACTION_GROWTH_PROPOSAL_APPLY_V1,
                payload={
                    "tenant_id": tenant_id,
                    "proposal": dict(proposal),
                    "decision_id": decision_id,
                    "correlation_id": correlation_id,
                    "issuer_id": issuer_id,
                    "route": canonical_runtime_route("GrowthProposalService", "Gateway"),
                },
            )
            queued += 1
        return queued