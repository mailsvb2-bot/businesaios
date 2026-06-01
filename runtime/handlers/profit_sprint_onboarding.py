from __future__ import annotations

CANON_THIN_HANDLER = True


"""Profit Sprint onboarding handlers (runtime actions).

These are intentionally dumb. They only execute decided steps via EffectsPort.
The business logic remains in core/profit_sprint/* and decision policies.
"""

from typing import Any, Dict

from runtime.ads import AdsApplyState, AdsPlan, plan_digest
from runtime.idempotency import make_idempotency_key
from runtime.ports.effects import EffectsPort
from runtime.ux import kb_ads_apply_pending


def handle_onboarding_start(payload: dict[str, Any], effects: EffectsPort, env: Any, *, event_store: Any) -> Any:
    user_id = str((payload or {}).get("user_id") or "")
    return effects.send_message(
        decision_id=str((payload or {}).get("decision_id") or ""),
        correlation_id=str((payload or {}).get("correlation_id") or ""),
        user_id=user_id,
        text="🚀 Profit Sprint: старт.\n\nСледуй шагам в меню автопилота.",
        reply_markup={"inline_keyboard": [[{"text": "⬅️ Назад", "callback_data": "autopilot:menu"}]]},
        callback_query_id=(payload or {}).get("callback_query_id"),
        track_event_type="profit_sprint_onboarding_start@v1",
        track_payload={},
    )


def handle_onboarding_text(payload: dict[str, Any], effects: EffectsPort, env: Any, *, event_store: Any) -> Any:
    user_id = str((payload or {}).get("user_id") or "")
    return effects.send_message(
        decision_id=str((payload or {}).get("decision_id") or ""),
        correlation_id=str((payload or {}).get("correlation_id") or ""),
        user_id=user_id,
        text="✅ Принято.",
        callback_query_id=(payload or {}).get("callback_query_id"),
        track_event_type="profit_sprint_onboarding_text@v1",
        track_payload={},
    )


def handle_onboarding_lead_source(payload: dict[str, Any], effects: EffectsPort, env: Any, *, event_store: Any) -> Any:
    user_id = str((payload or {}).get("user_id") or "")
    return effects.send_message(
        decision_id=str((payload or {}).get("decision_id") or ""),
        correlation_id=str((payload or {}).get("correlation_id") or ""),
        user_id=user_id,
        text="✅ Источник лидов выбран.",
        callback_query_id=(payload or {}).get("callback_query_id"),
        track_event_type="profit_sprint_onboarding_lead_source@v1",
        track_payload={},
    )
