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
