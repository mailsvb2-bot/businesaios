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
}


def handle_business_flow_routes(ctx: TelegramCtx, *, user_id: str) -> ProposedAction | None:
    route = BUSINESS_FLOW_COMMANDS.get(str(ctx.cmd or ""))
    if route is None:
        return None
    action, op, owner_only = route
    if owner_only and not ctx.is_admin:
        return None
    return propose(action, {"user_id": user_id, "op": op, "arg": str(ctx.args or "").strip()[:200]})


__all__ = ["BUSINESS_FLOW_COMMANDS", "handle_business_flow_routes"]
