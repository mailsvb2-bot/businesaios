"""Telegram commands for event-sourced business flows -> DecisionCore actions.

One table, no logic: each command proposes exactly one action with an ``op``.
Owner-only commands require ``ctx.is_admin``.
"""

from __future__ import annotations

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose

# cmd -> (action, op, owner_only)
BUSINESS_FLOW_COMMANDS: dict[str, tuple[str, str, bool]] = {
    "/connect_bot": ("bot_provisioning@v1", "request", True),
    "/bot_status": ("bot_provisioning@v1", "status", True),
    "/cancel_bot": ("bot_provisioning@v1", "cancel", True),
    "/add_slot": ("bookings@v1", "add_slot", True),
    "/slots": ("bookings@v1", "list", False),
    "/book": ("bookings@v1", "book", False),
    "/my_bookings": ("bookings@v1", "mine", False),
    "/cancel_booking": ("bookings@v1", "cancel", False),
    "/me": ("bookings@v1", "home", False),
    "/delete_my_data": ("privacy_delete@v1", "request", False),
    "/partner_add": ("partners@v1", "add", True),
    "/partners": ("partners@v1", "rank", True),
    "/ladder_add": ("offer_ladder@v1", "add", True),
    "/ladder": ("offer_ladder@v1", "show", True),
    "/ops": ("business_ops_summary@v1", "show", True),
    "/cockpit": ("business_ops_summary@v1", "cockpit", True),
    "/send_reminders": ("bookings@v1", "dispatch", True),
    "/bot_secret": ("bot_provisioning@v1", "attach", True),
    "/verify_bot": ("bot_provisioning@v1", "verify", True),
    "/partner_status": ("partners@v1", "status", True),
    "/partner_pitch": ("partners@v1", "pitch", True),
    "/partner_ref": ("partners@v1", "ref", True),
    "/setting": ("business_admin@v1", "setting", True),
    "/autopilot": ("business_admin@v1", "autopilot", True),
    "/price": ("business_admin@v1", "price", True),
    "/pay": ("business_admin@v1", "pay", True),
    "/refund": ("business_admin@v1", "refund", True),
    "/payments": ("business_admin@v1", "summary", True),
    "/approvals": ("business_admin@v1", "approvals", True),
    "/approve": ("business_admin@v1", "approve", True),
    "/reject": ("business_admin@v1", "reject", True),
    "/revoke": ("business_admin@v1", "revoke", True),
    "/series": ("event_series@v1", "preview", True),
    "/series_text": ("event_series@v1", "text", True),
    "/series_reset": ("event_series@v1", "reset", True),
    "/warmup_days": ("event_series@v1", "warmup_days", True),
    "/attendance": ("event_series@v1", "attendance", True),
    "/send_series": ("event_series@v1", "dispatch", True),
    "/offers_on": ("event_series@v1", "offers_on", False),
    "/offers_off": ("event_series@v1", "offers_off", False),
    "/new_event": ("event_series@v1", "wizard_start", True),
    "/leads": ("sales_pipeline@v1", "list", True),
    "/lead_add": ("sales_pipeline@v1", "add", True),
    "/lead": ("sales_pipeline@v1", "event", True),
    "/lead_reopen": ("sales_pipeline@v1", "reopen", True),
    "/lead_next": ("sales_pipeline@v1", "next", True),
    "/lead_note": ("sales_pipeline@v1", "note", True),
    "/lead_ai": ("sales_pipeline@v1", "ai", True),
    "/lead_card": ("sales_pipeline@v1", "card", True),
    "/leads_due": ("sales_pipeline@v1", "due", True),
}


def handle_business_flow_routes(ctx: TelegramCtx, *, user_id: str) -> ProposedAction | None:
    data = str(getattr(ctx, "callback_data", "") or "")
    if data.startswith("cpm:") and ctx.is_admin:
        return propose("business_ops_summary@v1", {"user_id": user_id, "op": "cockpit", "arg": data[:120]})
    if data.startswith("cpe:") and ctx.is_admin:
        return propose("event_series@v1", {"user_id": user_id, "op": "wizard", "arg": data[:64]})
    route = BUSINESS_FLOW_COMMANDS.get(str(ctx.cmd or ""))
    if route is None:
        return None
    action, op, owner_only = route
    if owner_only and not ctx.is_admin:
        return None
    return propose(action, {"user_id": user_id, "op": op, "arg": str(ctx.args or "").strip()[:200]})


__all__ = ["BUSINESS_FLOW_COMMANDS", "handle_business_flow_routes"]
