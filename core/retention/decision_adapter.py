from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from core.offers.engine import OfferEngine
from core.policies.telegram.helpers import ProposedAction, normalize_proposed_action
from core.retention.decision_adapter_support import (
    build_initial_plan,
    build_offer_proposal,
    read_entitlements_from_state,
    read_outbound_metrics,
)
from core.retention.engine import (
    RetentionDayDecision,
    RetentionDecision,
    RetentionEngine,
    RetentionEvaluation,
    neutral_decision,
)
from core.tenancy.normalization import normalize_tenant_scope
from kernel.world_state import WorldStateV1 as WorldState

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActionPlan:
    """Compatibility telemetry-only plan.

    Offer effects are candidate actions ranked by DecisionCore, never plan steps.
    """

    steps: list[dict[str, Any]]
    debug: dict[str, Any]


class RetentionDecisionAdapter:
    def __init__(
        self,
        *,
        event_store: Any,
        tenant_id: str = "",
        logger=None,
        prices: dict | None = None,
        outbound_metrics_reader=None,
        offer_engine: Any = None,
        offer_cooldown_store: Any = None,
    ):
        self._engine = RetentionEngine(
            event_store,
            tenant_id=normalize_tenant_scope(tenant_id, allow_unknown=True),
        )
        self._log = logger
        self._prices = prices
        self._outbound_metrics_reader = outbound_metrics_reader
        self._offer_engine = offer_engine or OfferEngine.default()
        self._offer_cooldown_store = offer_cooldown_store

    def _outbound(self) -> dict | None:
        if self._outbound_metrics_reader is None:
            return None
        return read_outbound_metrics(
            reader=self._outbound_metrics_reader,
            logger=self._log,
        )

    def evaluate(self, state: WorldState) -> RetentionEvaluation:
        session = getattr(state, "session", None)
        values = session if isinstance(session, dict) else {}
        return self._engine.compute_evidence(
            user_id=str(state.user_id or "anonymous"),
            day_key=str(values.get("day_key") or "day:today"),
            day_index=int(values.get("day_index") or 0),
            now_ms=int(getattr(state, "timestamp_ms", 0) or 0) or None,
            outbound_telemetry=self._outbound(),
            prices=self._prices,
            entitlements=read_entitlements_from_state(state=state, logger=self._log),
        )

    def propose_candidates(
        self,
        *,
        state: WorldState,
        base: ProposedAction | dict[str, Any],
        evaluation: RetentionEvaluation | None = None,
    ) -> list[ProposedAction]:
        normalized = normalize_proposed_action(base)
        evidence = evaluation or self.evaluate(state)
        proposals = [normalized]
        if evidence.suppressed or not evidence.candidates:
            return proposals
        user_id = str(state.user_id or normalized.payload.get("user_id") or "anonymous")
        for candidate in evidence.candidates:
            proposal = build_offer_proposal(
                base=normalized,
                evaluation=evidence,
                candidate=candidate,
                state=state,
                offer_engine=self._offer_engine,
                cooldown_store=self._offer_cooldown_store,
                user_id=user_id,
            )
            if proposal is not None:
                proposals.append(proposal)
        return proposals

    def maybe_decide_offer(
        self,
        *,
        tenant_id: str,
        user_id: str,
        context: dict,
    ) -> RetentionDecision | None:
        """Compatibility materializer requiring an explicit selected candidate id."""

        try:
            values = dict(context or {})
            if self._prices and "prices" not in values:
                values["prices"] = self._prices
            if self._outbound_metrics_reader and "outbound_telemetry" not in values:
                values["outbound_telemetry"] = self._outbound()
            return self._engine.decide_offer(
                tenant_id=tenant_id,
                user_id=user_id,
                context=values,
            )
        except Exception as exc:
            if self._log:
                self._log.warning("retention_decide_offer_failed: %s", exc)
            return None

    def compute_plan(self, state: WorldState) -> ActionPlan:
        """Historical read-only telemetry surface; never renders or selects an offer."""

        evaluation = self.evaluate(state)
        decision: RetentionDayDecision = neutral_decision(evaluation)
        steps, debug = build_initial_plan(
            decision=decision,
            user_id=str(state.user_id or "anonymous"),
        )
        return ActionPlan(steps=steps, debug=debug)
