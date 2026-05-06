from __future__ import annotations

from runtime.decisioning import RecommendationSet
from runtime.handlers.ads_autopilot_flow_contracts import AdsAutopilotProposalPort


class AdsAutopilotFlowService:
    '''
    Orchestrates proposal building only.
    Does not execute, approve, or route final decisions.
    '''

    def __init__(self, proposal_port: AdsAutopilotProposalPort) -> None:
        self._proposal_port = proposal_port

    def build_proposal(
        self,
        tenant_id: str,
        correlation_id: str,
        payload: dict[str, object] | None = None,
    ) -> RecommendationSet:
        return self._proposal_port.build(
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            payload=payload,
        )
