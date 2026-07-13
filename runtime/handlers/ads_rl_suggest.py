from __future__ import annotations

import logging
from typing import Any

from runtime.ads import RLSuggester, bind_runtime_state, policy_store
from runtime.governance import PolicyUpdateGate, PolicyUpdateGateError, ProfitMetricsService
from runtime.ports.effects import EffectsPort
from runtime.tenancy import as_tenant_id

CANON_THIN_HANDLER = True

logger = logging.getLogger(__name__)

ACTION_NAME = "ads_rl_suggest@v1"
_SUGGEST_GATE = PolicyUpdateGate(cooldown_ms=10 * 60 * 1000)


def handle_ads_rl_suggest(payload: dict[str, Any], effects: EffectsPort, env: Any, *, event_store: Any) -> Any:
    body = dict(payload or {})
    tenant_id = as_tenant_id(str(body.get("tenant_id") or ""))
    user_id = str(body.get("user_id") or "").strip()
    if not user_id:
        raise RuntimeError("USER_ID_REQUIRED")
    decision_id = str(env.decision.decision_id)
    correlation_id = str(env.decision.correlation_id)

    bind_runtime_state(event_store=event_store)
    _SUGGEST_GATE.bind_event_store(event_store)
    update_id = decision_id

    try:
        _SUGGEST_GATE.propose(
            tenant_id=str(tenant_id),
            domain="ads.rl.suggest",
            update_id=update_id,
            payload={
                "decision_id": decision_id,
                "correlation_id": correlation_id,
            },
        )
        _SUGGEST_GATE.approve(
            tenant_id=str(tenant_id),
            domain="ads.rl.suggest",
            update_id=update_id,
        )
        _SUGGEST_GATE.claim_for_apply(
            tenant_id=str(tenant_id),
            domain="ads.rl.suggest",
            update_id=update_id,
        )
    except PolicyUpdateGateError as exc:
        return effects.send_message(
            decision_id=decision_id,
            correlation_id=correlation_id,
            tenant_id=str(tenant_id),
            user_id=user_id,
            text=f"⏳ RL Suggest: cooldown → {exc}",
            track_event_type="ads_rl_suggest_blocked@v1",
            track_payload={
                "tenant_id": str(tenant_id),
                "reason": "cooldown",
                "error": str(exc),
            },
        )

    metrics = ProfitMetricsService(event_store=event_store)
    suggester = RLSuggester(store=policy_store, profit_metrics=metrics)

    current_budget_minor = body.get("current_daily_budget_minor")
    try:
        current_budget_minor = (
            int(current_budget_minor)
            if current_budget_minor is not None
            else None
        )
    except (TypeError, ValueError):
        current_budget_minor = None

    suggestion = suggester.suggest(
        tenant_id=str(tenant_id),
        current_daily_budget_minor=current_budget_minor,
    )

    try:
        effects.track_event(
            decision_id=decision_id,
            correlation_id=correlation_id,
            user_id=user_id,
            event_type="ads_rl_suggestion@v1",
            payload={
                "tenant_id": str(tenant_id),
                "ok": bool(suggestion.ok),
                "reason": str(suggestion.reason),
                "policy_version": suggestion.policy_version,
                "action": suggestion.action,
            },
            source="ads_rl",
        )
    except Exception as exc:
        logger.warning(
            "telemetry emission failed",
            extra={"component": __name__, "error": str(exc)},
        )

    if not suggestion.ok:
        return effects.send_message(
            decision_id=decision_id,
            correlation_id=correlation_id,
            tenant_id=str(tenant_id),
            user_id=user_id,
            text=f"🧠 RL Suggest: нет предложения ({suggestion.reason}).",
            track_event_type="ads_rl_suggest_skipped@v1",
            track_payload={
                "tenant_id": str(tenant_id),
                "reason": suggestion.reason,
            },
        )

    action = suggestion.action or {}
    return effects.send_message(
        decision_id=decision_id,
        correlation_id=correlation_id,
        tenant_id=str(tenant_id),
        user_id=user_id,
        text=(
            "🧠 RL Suggest (не применяет автоматически)\n\n"
            f"policy_version: {suggestion.policy_version}\n"
            f"multiplier_x1000: {action.get('multiplier_x1000')}\n"
            f"baseline_daily_budget_minor: {action.get('baseline_daily_budget_minor')}\n"
            f"proposed_daily_budget_minor: {action.get('proposed_daily_budget_minor')}\n\n"
            "Чтобы применить — это должно пройти через DecisionCore/Autopilot → AdsApplyEngine (с guard’ами)."
        ),
        track_event_type="ads_rl_suggest_ok@v1",
        track_payload={
            "tenant_id": str(tenant_id),
            "policy_version": suggestion.policy_version,
            "action": action,
        },
    )
