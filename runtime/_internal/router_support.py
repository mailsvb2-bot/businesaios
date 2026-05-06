from __future__ import annotations
import asyncio
from concurrent.futures import Future
from threading import Thread
from typing import Any, TypeVar
from runtime._internal.effect_router import EffectRouter
from runtime._internal.effect_types import EffectActionType, require_effect_action_type
from runtime._internal.http_transport import build_http_transport
T = TypeVar("T")
def get_effect_router(effects: Any | None) -> EffectRouter:
    if effects is not None:
        router = getattr(effects, "effect_router", None)
        if router is not None:
            return router
        transport = getattr(effects, "http_transport", None)
        outbound_queue = getattr(effects, "telegram_outbound_queue", None)
        return EffectRouter(
            transport=transport or build_http_transport(),
            outbound_queue=outbound_queue,
        )
    return EffectRouter(transport=build_http_transport())
async def execute_effect_action(effects: Any | None, action_type: str | EffectActionType, payload: dict[str, Any]) -> dict[str, Any]:
    return await get_effect_router(effects).execute(require_effect_action_type(action_type), dict(payload or {}))
def _run_coro_in_dedicated_thread(coro: Any) -> Any:
    result: Future[Any] = Future()
    def _runner() -> None:
        try:
            value = asyncio.run(coro)
        except BaseException as exc:  # pragma: no cover - propagated to caller
            result.set_exception(exc)
        else:
            result.set_result(value)
    thread = Thread(target=_runner, name="effect-router-sync-bridge", daemon=True)
    thread.start()
    thread.join()
    return result.result()
def execute_effect_action_sync(effects: Any | None, action_type: str | EffectActionType, payload: dict[str, Any]) -> dict[str, Any]:
    coro = execute_effect_action(effects, require_effect_action_type(action_type), dict(payload or {}))
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return _run_coro_in_dedicated_thread(coro)
def run_effect_router(effects: Any | None, action_type: str | EffectActionType, payload: dict[str, Any]) -> dict[str, Any]:
    return execute_effect_action_sync(effects, require_effect_action_type(action_type), dict(payload or {}))
