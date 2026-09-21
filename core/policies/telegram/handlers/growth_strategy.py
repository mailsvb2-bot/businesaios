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


def _scope(ctx: TelegramCtx) -> tuple[str, str]:
    state = ctx.state
    tenant_id = str(getattr(state, "tenant_id", "") or "").strip()
    semantics = getattr(state, "world_model_semantics", None)
    business_id = str(getattr(semantics, "business_id", "") or "").strip()
    semantic_tenant = str(getattr(semantics, "tenant_id", "") or "").strip()
    return tenant_id, business_id if business_id and semantic_tenant == tenant_id else ""


def handle_growth_strategy(ctx: TelegramCtx, *, user_id: str) -> ProposedAction | None:
    cb = str(ctx.callback_data or "").strip()
    tenant_id, business_id = _scope(ctx)
    growth_action = cb in {CB_GROWTH_GENERATE, CB_GROWTH_BACKLOG} or cb.startswith((CB_GROWTH_ACCEPT_PREFIX, CB_GROWTH_REJECT_PREFIX))
    if growth_action and not business_id:
        return propose_message(user_id=user_id, text="Сначала выбери бизнес в рабочем пространстве.", callback_query_id=ctx.callback_query_id)

    if cb == CB_GROWTH_MENU:
        return propose_message(user_id=user_id, text="🧠 AI Growth Strategy", reply_markup=kb_growth_menu())

    if cb == CB_GROWTH_GENERATE:
        return propose(
            "growth_strategy_generate@v1",
            {"user_id": user_id, "tenant_id": tenant_id, "business_id": business_id, "idempotency_key": str((ctx.state.meta or {}).get("correlation_key") or "growth:generate")},
        )

    if cb == CB_GROWTH_BACKLOG:
        return propose("growth_strategy_backlog@v1", {"user_id": user_id, "tenant_id": tenant_id, "business_id": business_id, "limit": 30})

    if cb.startswith(CB_GROWTH_ACCEPT_PREFIX):
        hid = cb[len(CB_GROWTH_ACCEPT_PREFIX) :].strip()
        return propose("growth_strategy_accept@v1", {"user_id": user_id, "tenant_id": tenant_id, "business_id": business_id, "hypothesis_id": hid, "idempotency_key": f"growth:accept:{hid}"})

    if cb.startswith(CB_GROWTH_REJECT_PREFIX):
        hid = cb[len(CB_GROWTH_REJECT_PREFIX) :].strip()
        return propose("growth_strategy_reject@v1", {"user_id": user_id, "tenant_id": tenant_id, "business_id": business_id, "hypothesis_id": hid, "idempotency_key": f"growth:reject:{hid}"})

    return None
