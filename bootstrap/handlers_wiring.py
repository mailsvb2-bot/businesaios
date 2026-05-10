from __future__ import annotations

from typing import Any

CANON_BOOT_HANDLERS_WIRING_FINAL_OWNER = True
CANON_BOOT_WIRING_ONLY = True
"""Wire all action handlers into an ActionHandlerRegistry.

The canonical registry remains single and strict, but handler definitions are
cut into domain groups so boot wiring does not become a god module again.
"""

from runtime.boot.handler_groups.ads import register_ads_handlers
from runtime.boot.handler_groups.core import register_core_handlers
from runtime.boot.handler_groups.growth import register_growth_handlers
from runtime.boot.handler_groups.messaging import register_messaging_handlers
from runtime.boot.handler_groups.ops import register_ops_handlers
from runtime.boot.handler_groups.shared import get_ctx_value


def _action_handler_registry_cls() -> Any:
    module = __import__('runtime.handlers', fromlist=['ActionHandlerRegistry'])
    return getattr(module, 'ActionHandlerRegistry')


def wire_handlers(*, ctx, event_store, composer):
    handlers = _action_handler_registry_cls()()

    register_messaging_handlers(handlers=handlers, composer=composer)

    register_core_handlers(handlers=handlers, ctx=ctx)

    register_ads_handlers(
        handlers=handlers,
        event_store=event_store,
        ads_runtime=get_ctx_value(ctx, "ads_runtime"),
        ads_autopilot_engine=get_ctx_value(ctx, "ads_autopilot_engine"),
        ads_apply_engine=get_ctx_value(ctx, "ads_apply_engine"),
    )

    register_growth_handlers(
        handlers=handlers,
        event_store=event_store,
        behavior_graph_store=get_ctx_value(ctx, "behavior_graph_store"),
        marketing_llm=get_ctx_value(ctx, "marketing_llm"),
    )
    register_ops_handlers(handlers=handlers, event_store=event_store)

    from runtime.boot.actions_registry import handler_actions

    registered = handlers.actions()
    expected = handler_actions()
    if registered != expected:
        missing = sorted(expected - registered)
        extra = sorted(registered - expected)
        raise RuntimeError(f"ACTIONS_REGISTRY_DRIFT missing={missing} extra={extra}")

    return handlers
