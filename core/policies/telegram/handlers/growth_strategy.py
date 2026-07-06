from __future__ import annotations

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose, propose_message
from core.ux.callbacks import (
    CB_GROWTH_ACCEPT_PREFIX,
    CB_GROWTH_BACKLOG,
    CB_GROWTH_GENERATE,
    CB_GROWTH_MENU,
    CB_GROWTH_REJECT_PREFIX,
)
from core.ux.telegram_keyboards import kb_growth_menu


def handle_growth_strategy(ctx: TelegramCtx, *, user_id: str) -> ProposedAction | None:
    cb = str(ctx.callback_data or "").strip()

    if cb == CB_GROWTH_MENU:
        return propose_message(user_id=user_id, text="🧠 AI Growth Strategy", reply_markup=kb_growth_menu())

    if cb == CB_GROWTH_GENERATE:
        return propose(
            "growth_strategy_generate@v1",
            {"user_id": user_id, "tenant_id": str(ctx.tenant_id or ""), "idempotency_key": str(ctx.idempotency_key or "growth:generate")},
        )

    if cb == CB_GROWTH_BACKLOG:
        return propose("growth_strategy_backlog@v1", {"user_id": user_id, "tenant_id": str(ctx.tenant_id or ""), "limit": 30})

    if cb.startswith(CB_GROWTH_ACCEPT_PREFIX):
        hid = cb[len(CB_GROWTH_ACCEPT_PREFIX) :].strip()
        return propose("growth_strategy_accept@v1", {"user_id": user_id, "tenant_id": str(ctx.tenant_id or ""), "hypothesis_id": hid, "idempotency_key": f"growth:accept:{hid}"})

    if cb.startswith(CB_GROWTH_REJECT_PREFIX):
        hid = cb[len(CB_GROWTH_REJECT_PREFIX) :].strip()
        return propose("growth_strategy_reject@v1", {"user_id": user_id, "tenant_id": str(ctx.tenant_id or ""), "hypothesis_id": hid, "idempotency_key": f"growth:reject:{hid}"})

    return None
