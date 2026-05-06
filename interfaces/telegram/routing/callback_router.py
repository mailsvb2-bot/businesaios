from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

Handler = Callable[..., Awaitable[None]]

@dataclass(frozen=True)
class CallbackContext:
    tenant_id: str
    user_id: Optional[str]
    chat_id: int
    callback_data: str

class CallbackRouter:
    def __init__(self) -> None:
        self._exact: Dict[str, Handler] = {}
        self._prefix: list[Tuple[str, Handler]] = []

    def on(self, key: str, handler: Handler) -> None:
        self._exact[key] = handler

    def on_prefix(self, prefix: str, handler: Handler) -> None:
        self._prefix.append((prefix, handler))
        self._prefix.sort(key=lambda x: len(x[0]), reverse=True)

    async def dispatch(self, sys: Any, io: Any, ctx: CallbackContext) -> bool:
        data = ctx.callback_data or ""
        if data in self._exact:
            await self._exact[data](sys, io, ctx)
            return True
        for pref, h in self._prefix:
            if data.startswith(pref):
                await h(sys, io, ctx)
                return True
        return False
