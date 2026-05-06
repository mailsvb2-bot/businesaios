from __future__ import annotations

import asyncio

from runtime._internal.effect_types import EffectActionType
from runtime._internal.router_support import execute_effect_action_sync
from runtime._internal.http_transport import DisabledNetworkTransport


class _EffectsStub:
    def __init__(self) -> None:
        self.http_transport = DisabledNetworkTransport()
        self.telegram_outbound_queue = None
        self.effect_router = None


async def _call_sync_bridge_inside_loop() -> dict[str, object]:
    return execute_effect_action_sync(
        _EffectsStub(),
        EffectActionType.WEATHER_OPEN_METEO_CURRENT,
        {"city": "Amsterdam"},
    )


def test_execute_effect_action_sync_remains_callable_inside_running_event_loop() -> None:
    out = asyncio.run(_call_sync_bridge_inside_loop())
    assert out["ok"] is False
    assert isinstance(out.get("meta"), dict)
    assert out["meta"].get("error")
