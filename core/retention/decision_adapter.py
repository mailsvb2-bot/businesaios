from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from core.offers.engine import OfferEngine
from core.retention.decision_adapter_support import (
    build_initial_plan,
    build_retention_debug,
    make_telemetry_step,
    read_entitlements_from_state,
    read_outbound_metrics,
    render_offer_step,
    try_build_offer_step,
)
from core.retention.engine import RetentionDayDecision, RetentionDecision, RetentionEngine
from core.tenancy.normalization import normalize_tenant_scope
from kernel.world_state import WorldStateV1 as WorldState

log = logging.getLogger(__name__)
_RETENTION_SPLIT_HELPERS = (build_retention_debug, make_telemetry_step, render_offer_step)


@dataclass(frozen=True)
class ActionPlan:
    """Single output contract for UX.

    One input -> one plan (no second brain).
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
        self._engine = RetentionEngine(event_store, tenant_id=normalize_tenant_scope(tenant_id, allow_unknown=True))
        self._log = logger
        self._prices = prices
        self._outbound_metrics_reader = outbound_metrics_reader
        self._offer_engine = offer_engine or OfferEngine.default()
        self._offer_cooldown_store = offer_cooldown_store

    def maybe_decide_offer(self, *, tenant_id: str, user_id: str, context: dict) -> RetentionDecision | None:
        try:
            ctx = dict(context or {})
            if self._prices and "prices" not in ctx:
                ctx["prices"] = self._prices
            if self._outbound_metrics_reader and "outbound_telemetry" not in ctx:
                ctx["outbound_telemetry"] = read_outbound_metrics(reader=self._outbound_metrics_reader, logger=self._log)
            return self._engine.decide_offer(tenant_id=tenant_id, user_id=user_id, context=ctx)
        except Exception as exc:
            if self._log:
                self._log.warning("retention_decide_offer_failed: %s", exc)
            return None

    def compute_plan(self, state: WorldState) -> ActionPlan:
        user_id = str(state.user_id)
        outbound = read_outbound_metrics(reader=self._outbound_metrics_reader, logger=self._log) if self._outbound_metrics_reader else None
        entitlements = read_entitlements_from_state(state=state, logger=self._log)
        session = getattr(state, "session", None)
        decision: RetentionDayDecision = self._engine.compute_decision(
            user_id=user_id,
            day_key=str(session.get("day_key", "day:today")) if isinstance(session, dict) else "day:today",
            day_index=int(session.get("day_index", 0)) if isinstance(session, dict) else 0,
            outbound_telemetry=outbound,
            prices=self._prices,
            entitlements=entitlements,
        )
        steps, debug = build_initial_plan(decision=decision, user_id=user_id)
        offer_step, override_debug = try_build_offer_step(
            decision=decision,
            state=state,
            offer_engine=self._offer_engine,
            cooldown_store=self._offer_cooldown_store,
            user_id=user_id,
        )
        if override_debug is not None:
            return ActionPlan(steps=steps, debug=override_debug)
        if offer_step is not None:
            steps.append(offer_step)
        return ActionPlan(steps=steps, debug=debug)
