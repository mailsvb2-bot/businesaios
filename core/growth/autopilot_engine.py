from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from application.decisioning.decision_output_guard import assert_non_decision_payload
from core.growth.autopilot_contracts import (
    GrowthAutopilotContext,
    GrowthRecommendationBuilderPort,
)
from core.growth.autopilot_engine_run import run_autopilot_engine
from kernel.decisioning.decision_types import RecommendationSet

CANON_NON_DECISION_MODULE = True

class GrowthAutopilotEngine:
    """Legacy filename retained intentionally.

    Canonical behavior: prepare growth recommendations only.
    It does not issue decisions.
    It does not apply ads changes directly.
    No hidden decision authority.
    """

    def __init__(self, builder: GrowthRecommendationBuilderPort) -> None:
        self._builder = builder

    def build_recommendations(
        self,
        tenant_id: str,
        correlation_id: str,
        payload: dict[str, object] | None = None,
    ) -> RecommendationSet:
        context = GrowthAutopilotContext(
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            payload=payload or {},
        )
        return assert_non_decision_payload(self._builder.build(context))


@dataclass(frozen=True)
class AutopilotRunResult:
    ok: bool
    message: str
    proposed: int
    queued: int
    applied: int
    blocked: int


class AutopilotEngine:
    """Guarded queue-only compat surface.

    This is a recommendation_only queue surface.
    It never directly applies changes; it only validates preconditions,
    imports stats, collects recommendations, and routes guarded apply proposals
    through the proposal gateway.
    """

    def __init__(
        self,
        *,
        entitlements_provider: Any,
        ads_service: Any,
        ads_reco_service: Any,
        ads_apply_service: Any,
        trust_score: Any,
        circuit_breaker: Any,
        sink: Any,
        cfg: Any,
        proposal_gateway: Any,
    ) -> None:
        self._ent = entitlements_provider
        self._ads = ads_service
        self._reco = ads_reco_service
        self._apply = ads_apply_service
        self._trust = trust_score
        self._breaker = circuit_breaker
        self._sink = sink
        self._cfg = cfg
        self._proposal_gateway = proposal_gateway
        self._mode_value = "autopilot"

    def _ensure_guarded_execution_contract(self) -> None:
        if self._apply is not None:
            raise RuntimeError(
                "direct apply is forbidden; AutopilotEngine must not be wired with direct ads apply surface; use proposal_gateway only"
            )
        if self._proposal_gateway is None or not callable(getattr(self._proposal_gateway, "propose", None)):
            raise RuntimeError("AutopilotEngine requires callable proposal_gateway.propose")


    async def _run_flow(
        self,
        *,
        tenant_id: str,
        platform: str,
        account_id: str,
        decision_id: str,
        correlation_id: str,
        issuer_id: str,
    ):
        return await run_autopilot_engine(
            self,
            tenant_id=tenant_id,
            platform=platform,
            account_id=account_id,
            decision_id=decision_id,
            correlation_id=correlation_id,
            issuer_id=issuer_id,
        )

    async def run(
        self,
        *,
        tenant_id: str,
        platform: str,
        account_id: str,
        decision_id: str = "autopilot-system",
        correlation_id: str = "autopilot-system",
        issuer_id: str = "businesaios-core",
    ) -> AutopilotRunResult:
        try:
            self._ensure_guarded_execution_contract()
            ok, message, stats = await self._run_flow(
                tenant_id=tenant_id,
                platform=platform,
                account_id=account_id,
                decision_id=decision_id,
                correlation_id=correlation_id,
                issuer_id=issuer_id,
            )
        except Exception as exc:
            return AutopilotRunResult(False, str(exc), 0, 0, 0, 1)

        return AutopilotRunResult(
            ok,
            message,
            proposed=int(stats["proposed"]),
            queued=int(stats["queued"]),
            applied=int(stats["applied"]),
            blocked=int(stats["blocked"]),
        )


def build_growth_recommendations(
    builder: GrowthRecommendationBuilderPort,
    tenant_id: str,
    correlation_id: str,
    payload: dict[str, object] | None = None,
) -> RecommendationSet:
    return GrowthAutopilotEngine(builder).build_recommendations(
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        payload=payload,
    )


__all__ = [
    "AutopilotEngine",
    "AutopilotRunResult",
    "GrowthAutopilotEngine",
    "build_growth_recommendations",
]
