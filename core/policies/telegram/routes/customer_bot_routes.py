"""Customer side of a tenant's own Telegram bot -> DecisionCore actions.

Same route table and DecisionCore as the main bot, but a customer bot never
grants owner/admin commands: only ``owner_only=False`` routes pass, everything
else is refused with a pointer to the main bot. Business context (activity,
offerings, timezone) comes from the session the gateway built per route.
"""

from __future__ import annotations

from typing import Any

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose, propose_message
from core.policies.telegram.routes.business_flow_routes import BUSINESS_FLOW_COMMANDS

# Literal mirror of application.business_flows.bot_gateway.SESSION_SOURCE (core must not import application).
CUSTOMER_SOURCE = "customer_bot_update"
CUSTOMER_COMMANDS: tuple[str, ...] = tuple(
    c for c, (_a, _o, owner_only) in BUSINESS_FLOW_COMMANDS.items() if not owner_only
)
_MENU_HINTS = {"/slots": "свободные слоты", "/book": "записаться", "/my_bookings": "мои записи",
               "/cancel_booking": "отменить запись", "/me": "мой профиль",
               "/delete_my_data": "удалить мои данные"}  # fmt: skip


def is_customer_session(session: Any) -> bool:
    return isinstance(session, dict) and session.get("source") == CUSTOMER_SOURCE


def _bot(ctx: TelegramCtx) -> dict[str, Any]:
    session = getattr(getattr(ctx, "state", None), "session", None) or {}
    bot = session.get("customer_bot") if isinstance(session, dict) else None
    return bot if isinstance(bot, dict) else {}


def customer_menu_text(bot: dict[str, Any]) -> str:
    business = bot.get("business") if isinstance(bot.get("business"), dict) else {}
    name = str(bot.get("username") or "").strip()
    lines = [f"Здравствуйте! Это бот @{name}." if name else "Здравствуйте!"]
    activity = str(business.get("activity") or "").strip()
    if activity:
        lines.append(activity[:300])
    offerings = [str(o)[:80] for o in list(business.get("offerings") or [])[:5] if str(o).strip()]
    if offerings:
        lines.append("Что мы предлагаем: " + ", ".join(offerings))
    lines.append("")
    lines.extend(f"{cmd} — {hint}" for cmd, hint in _MENU_HINTS.items() if cmd in CUSTOMER_COMMANDS)
    return "\n".join(lines)


def handle_customer_bot(ctx: TelegramCtx, *, user_id: str) -> ProposedAction:
    """Always returns an action: a customer bot never falls through to the owner brain."""
    bot = _bot(ctx)
    cmd = str(ctx.cmd or "")
    args = str(ctx.args or "").strip()

    def pm(text: str) -> ProposedAction:
        return propose_message(user_id=user_id, text=text, callback_query_id=ctx.callback_query_id)

    if cmd == "/start" and args.startswith("cpa_"):
        return propose("bookings@v1", {"user_id": user_id, "op": "promo_open", "arg": args[:64]})
    if cmd == "/start" and args.startswith("ecv_"):
        return propose("bookings@v1", {"user_id": user_id, "op": "channel_verify", "arg": args[:200]})
    route = BUSINESS_FLOW_COMMANDS.get(cmd)
    if route is not None:
        action, op, owner_only = route
        if owner_only:
            return pm("Эта команда доступна только владельцу в основном боте BusinesAIOS.")
        return propose(action, {"user_id": user_id, "op": op, "arg": args[:200]})
    return pm(customer_menu_text(bot))


__all__ = ["CUSTOMER_COMMANDS", "CUSTOMER_SOURCE", "customer_menu_text", "handle_customer_bot", "is_customer_session"]
