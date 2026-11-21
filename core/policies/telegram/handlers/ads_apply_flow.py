"""Thin routing shim for ads apply flow callbacks.

Previously this module duplicated preview/confirm/cancel logic that also
lived in ads_apply.py, creating a divergence risk.

Now: single canon is ads_apply.handle_ads_apply().
This module is a thin wrapper so router.py's import/call stays unchanged.
"""

from __future__ import annotations

from typing import Any

from core.ads.apply_flow_codec import compute_plan_idempotency_key
from core.ads.apply_gate import ADS_APPLY_SETTING_KEY, AdsApplyState
from core.policies.telegram.context import TelegramCtx, operator_flag
from core.policies.telegram.handlers.ads_apply import handle_ads_apply
from core.policies.telegram.helpers import ProposedAction, propose
from core.ux.callbacks import CB_ADS_APPLY_CANCEL, CB_ADS_APPLY_CONFIRM, CB_ADS_APPLY_PREVIEW


def handle_ads_apply_flow(ctx: TelegramCtx, *, user_id: str) -> ProposedAction | None:
    """Route ads-apply callbacks to the canonical handler.

    Returns None if the callback doesn't belong to the ads-apply flow,
    so the router can fall through to other handlers.
    """
    cb = str(ctx.callback_data or "")
    if cb not in {CB_ADS_APPLY_PREVIEW, CB_ADS_APPLY_CONFIRM, CB_ADS_APPLY_CANCEL}:
        return None
    # Note: strict single-path — only ads_apply.handle_ads_apply triggers runtime apply.
    return handle_ads_apply(ctx, user_id=user_id)

# canonical runtime action proposed by this flow: ads_apply_execute@v1


# Unique canonical proposer. All confirmation paths delegate here.
ADS_APPLY_EXECUTE = "ads_apply_execute@v1"


def _plan_commands(pending: dict[str, Any]) -> list[dict[str, Any]]:
    platform = str(pending.get("platform") or "")
    budget = int(pending.get("daily_budget_minor") or 0)
    ops = list(pending.get("ops") or [])
    if not platform or budget < 0 or not ops:
        return []
    commands = []
    for operation in ops:
        if not isinstance(operation, dict):
            return []
        payload = operation.get("payload")
        if not isinstance(payload, dict):
            return []
        action = str(operation.get("action") or "").strip()
        if not action:
            return []
        commands.append({
            "platform": platform, "action": action,
            "payload": {**payload, "daily_budget_minor": budget},
        })
    return commands


def propose_confirmed_apply(ctx: TelegramCtx, *, user_id: str,
                            pending: dict[str, Any]) -> ProposedAction | None:
    """Use the existing executor, gate, budget, kill switch and idempotency."""
    plan = _plan_commands(pending)
    if not plan:
        return None
    settings = ctx.settings if isinstance(ctx.settings, dict) else {}
    return propose(ADS_APPLY_EXECUTE, {
        "user_id": str(user_id),
        "idempotency_key": "tg-" + compute_plan_idempotency_key(pending)[:48],
        "plan": plan,
        "dry_run": not operator_flag(ctx, "ads_apply_live"),
        "gate_settings": {ADS_APPLY_SETTING_KEY: AdsApplyState.from_settings(settings).enabled},
        "reason": "telegram_confirm",
        **({"callback_query_id": ctx.callback_query_id} if ctx.callback_query_id else {}),
    })
