from __future__ import annotations

CANON_THIN_HANDLER = True


import logging
from typing import Any

from runtime.ads import RLSuggester, bind_runtime_state, policy_store
from runtime.governance import ProfitMetricsService, PolicyUpdateGate, PolicyUpdateGateError
from runtime.ports.effects import EffectsPort
from runtime.tenancy import as_tenant_id

logger = logging.getLogger(__name__)

ACTION_NAME = "ads_rl_suggest@v1"
_SUGGEST_GATE = PolicyUpdateGate(cooldown_ms=10 * 60 * 1000)


def handle_ads_rl_suggest(payload: dict[str, Any], effects: EffectsPort, env: Any, *, event_store: Any) -> Any:
    p = payload or {}
    bind_runtime_state(event_store=event_store)
    tenant_id = as_tenant_id(str(p.get("tenant_id") or ""))
    _SUGGEST_GATE.bind_event_store(event_store)
    update_id = str(p.get("decision_id") or p.get("correlation_id") or "rl_suggest")

    try:
        _SUGGEST_GATE.propose(
            tenant_id=str(tenant_id),
            domain="ads.rl.suggest",
            update_id=update_id,
            payload={"decision_id": str(p.get("decision_id") or ""), "correlation_id": str(p.get("correlation_id") or "")},
        )
        _SUGGEST_GATE.approve(tenant_id=str(tenant_id), domain="ads.rl.suggest", update_id=update_id)
        _SUGGEST_GATE.claim_for_apply(tenant_id=str(tenant_id), domain="ads.rl.suggest", update_id=update_id)
    except PolicyUpdateGateError as ge:
        return effects.send_message(
            decision_id=str(p.get("decision_id") or ""),
            correlation_id=str(p.get("correlation_id") or ""),
            user_id=str(p.get("user_id") or ""),
            chat_id=str(p.get("chat_id") or ""),
            text=f"⏳ RL Suggest: cooldown → {ge}",
            track_event_type="ads_rl_suggest_blocked@v1",
            track_payload={"reason": "cooldown", "error": str(ge)},
        )

    pm = ProfitMetricsService(event_store=event_store)
    suggester = RLSuggester(store=policy_store, profit_metrics=pm)

    current_budget_minor = p.get("current_daily_budget_minor")
    try:
        current_budget_minor = int(current_budget_minor) if current_budget_minor is not None else None
    except Exception:
        current_budget_minor = None

    sug = suggester.suggest(tenant_id=str(tenant_id), current_daily_budget_minor=current_budget_minor)

    try:
        effects.track_event(
            decision_id=str(p.get("decision_id") or ""),
            correlation_id=str(p.get("correlation_id") or ""),
            user_id=str(p.get("user_id") or ""),
            event_type="ads_rl_suggestion@v1",
            payload={
                "tenant_id": str(tenant_id),
                "ok": bool(sug.ok),
                "reason": str(sug.reason),
                "policy_version": sug.policy_version,
                "action": sug.action,
            },
            source="ads_rl",
        )
    except Exception as exc:
        logger.warning("telemetry emission failed", extra={"component": __name__, "error": str(exc)})

    if not sug.ok:
        return effects.send_message(
            decision_id=str(p.get("decision_id") or ""),
            correlation_id=str(p.get("correlation_id") or ""),
            user_id=str(p.get("user_id") or ""),
            chat_id=str(p.get("chat_id") or ""),
            text=f"🧠 RL Suggest: нет предложения ({sug.reason}).",
            track_event_type="ads_rl_suggest_skipped@v1",
            track_payload={"reason": sug.reason},
        )

    a = sug.action or {}
    return effects.send_message(
        decision_id=str(p.get("decision_id") or ""),
        correlation_id=str(p.get("correlation_id") or ""),
        user_id=str(p.get("user_id") or ""),
        chat_id=str(p.get("chat_id") or ""),
        text=(
            "🧠 RL Suggest (не применяет автоматически)\n\n"
            f"policy_version: {sug.policy_version}\n"
            f"multiplier_x1000: {a.get('multiplier_x1000')}\n"
            f"baseline_daily_budget_minor: {a.get('baseline_daily_budget_minor')}\n"
            f"proposed_daily_budget_minor: {a.get('proposed_daily_budget_minor')}\n\n"
            "Чтобы применить — это должно пройти через DecisionCore/Autopilot → AdsApplyEngine (с guard’ами)."
        ),
        track_event_type="ads_rl_suggest_ok@v1",
        track_payload={"policy_version": sug.policy_version, "action": a},
    )
