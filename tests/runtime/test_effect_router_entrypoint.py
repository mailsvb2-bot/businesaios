from __future__ import annotations

import asyncio

from runtime import effects as effects_public


class _StubTransport(effects_public.DisabledNetworkTransport()):
    async def post_json(self, **kwargs):
        return type("Resp", (), {"status": 200, "json": {"ok": True, "echo": dict(kwargs.get("data") or {})}, "text": ""})()


def test_runtime_network_mode_disabled_under_pytest():
    assert effects_public.runtime_network_mode() == "disabled"


def test_get_effect_router_keeps_injected_transport():
    transport = _StubTransport()
    router = effects_public.get_effect_router(type("E", (), {"http_transport": transport, "telegram_outbound_queue": None})())
    assert isinstance(router, effects_public.EffectRouter())
    assert router.transport is transport


def test_execute_effect_action_routes_via_canonical_entrypoint():
    transport = _StubTransport()
    effects = type("E", (), {"http_transport": transport, "telegram_outbound_queue": None})()
    out = asyncio.run(
        effects_public.execute_effect_action(
            effects,
            effects_public.EffectActionType().CRM_WRITE_RECORD,
            {"url": "https://example.test/write", "data": {"a": 1}},
        )
    )
    assert out["ok"] is True
    assert out["json"]["ok"] is True
    assert out["json"]["echo"] == {"a": 1}


def test_run_effect_router_sync_wrapper_still_works():
    transport = _StubTransport()
    effects = type("E", (), {"http_transport": transport, "telegram_outbound_queue": None})()
    out = effects_public.run_effect_router(
        effects,
        effects_public.EffectActionType().ADS_UPDATE_BUDGET,
        {"url": "https://example.test/budget", "data": {"budget": 10}},
    )
    assert out["ok"] is True
    assert out["json"]["echo"] == {"budget": 10}
