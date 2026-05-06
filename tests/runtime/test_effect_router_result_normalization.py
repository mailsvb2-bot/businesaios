from __future__ import annotations

import asyncio

from runtime._internal.effect_router import EffectRouter
from runtime._internal.effect_types import EffectActionType
from runtime._internal.http_transport import DisabledNetworkTransport


class _StubTransport(DisabledNetworkTransport):
    async def post_json(self, **kwargs):
        return type("Resp", (), {"status": 200, "json": {"ok": True, "echo": dict(kwargs.get("data") or {})}, "text": ""})()


def test_effect_router_normalizes_handler_result_and_attaches_evidence() -> None:
    router = EffectRouter(transport=_StubTransport())
    out = asyncio.run(router.execute(EffectActionType.CRM_WRITE_RECORD, {"url": "https://example.test/write", "data": {"a": 1}}))
    assert out["status"] == "success"
    assert out["ok"] is True
    assert out["action_type"] == "crm.write_record"
    assert out["data"]["json"]["echo"] == {"a": 1}
    assert out["evidence"]["source"] == "effect_router"
    assert out["evidence"]["action_type"] == "crm.write_record"


def test_effect_router_normalizes_none_result_from_handler() -> None:
    router = EffectRouter(transport=DisabledNetworkTransport())

    async def _none_handler(payload):
        return None

    router.register(EffectActionType.WEBSITE_PUBLISH_PAGE, _none_handler)
    out = asyncio.run(router.execute(EffectActionType.WEBSITE_PUBLISH_PAGE, {"endpoint": "https://example.test/site", "data": {}}))
    assert out["status"] == "success"
    assert out["ok"] is True
    assert out["data"] == {}
