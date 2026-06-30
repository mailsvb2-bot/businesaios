"""AI CEO telegram handler (pure).

Adds a user command /ceo to show a CEO plan, and callbacks to execute it.

Routing contract:
- /ceo -> ai_ceo_plan@v1
- callback ceo:plan -> ai_ceo_plan@v1
- callback ceo:run  -> execute_plan@v1 with CEO steps
"""

from __future__ import annotations

from typing import Any
from core.ai_ceo import autonomy_from_env, build_plan, read_growth_snapshot, render_plan_text
from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose
from core.ux.callbacks import CB_CEO_MENU, CB_CEO_PLAN, CB_CEO_RUN
from core.ux.telegram_keyboards import kb_ai_ceo_menu

def handle_ai_ceo(ctx: TelegramCtx, *, user_id: str, event_store: Any | None = None) -> ProposedAction | None:
    # entrypoints: command or callbacks
    if ctx.cmd == "/ceo":
        return _propose_plan(ctx, user_id=user_id, event_store=event_store)
    if str(ctx.callback_data or "") in {CB_CEO_MENU, CB_CEO_PLAN}:
        return _propose_plan(ctx, user_id=user_id, event_store=event_store)
    if str(ctx.callback_data or "") == CB_CEO_RUN:
        # Recompute plan (pure) and execute as composite action.
        plan = _build(ctx, event_store=event_store)
        steps = []
        for s in plan.steps:
            steps.append({"action": s.action, **dict(s.payload or {})})
        return propose(
            "execute_plan@v1",
            {
                "steps": steps,
                "user_id": user_id,
                "callback_query_id": ctx.callback_query_id,
            },
        )
    return None


def _build(ctx: TelegramCtx, *, event_store: Any | None) -> Any:
    tenant_id = str(ctx.tenant_id or "")
    autonomy = autonomy_from_env()
    snapshot = read_growth_snapshot(event_store, tenant_id=tenant_id) if event_store is not None else None
    if snapshot is None:
        from core.ai_ceo.ledger import GrowthSnapshotV1
        snapshot = GrowthSnapshotV1()
    return build_plan(state=ctx.state, snapshot=snapshot, autonomy=autonomy, bot_username=str(ctx.bot_username or ""))


def _propose_plan(ctx: TelegramCtx, *, user_id: str, event_store: Any | None) -> ProposedAction:
    plan = _build(ctx, event_store=event_store)
    text = render_plan_text(plan)
    return propose(
        "ai_ceo_plan@v1",
        {
            "user_id": user_id,
            "text": text,
            "reply_markup": kb_ai_ceo_menu(),
            "callback_query_id": ctx.callback_query_id,
            "track_event_type": "ai_ceo_plan_shown" + "@v1",
            "track_payload": {"plan_id": plan.plan_id},
        },
    )
