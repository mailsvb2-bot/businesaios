from __future__ import annotations

import asyncio

import pytest

from runtime._internal.effect_payloads import EffectPayloadError, normalize_effect_payload, payload_contract_fields
from runtime._internal.effect_router import EffectRouter
from runtime._internal.effect_types import EffectActionType
from runtime._internal.http_transport import DisabledNetworkTransport


class _StubTransport(DisabledNetworkTransport):
    async def post_json(self, **kwargs):
        return type("Resp", (), {"status": 200, "json": {"ok": True, "echo": dict(kwargs.get("data") or {})}, "text": ""})()


def test_effect_payload_contract_registry_matches_router_support() -> None:
    router = EffectRouter(transport=_StubTransport())
    contracts = router.payload_contracts()
    assert set(contracts) == set(router.supported_action_types())
    assert set(payload_contract_fields()) == set(router.supported_action_enums())


def test_normalize_effect_payload_applies_canonical_defaults() -> None:
    with pytest.raises(
        EffectPayloadError,
        match=r"effect_payload_invalid:weather.open_meteo.current:missing_city",
    ):
        normalize_effect_payload(EffectActionType.WEATHER_OPEN_METEO_CURRENT, {})

    normalized = normalize_effect_payload(
        EffectActionType.WEATHER_OPEN_METEO_CURRENT,
        {"city": " Amsterdam "},
    )
    assert normalized == {"city": "Amsterdam"}

    normalized = normalize_effect_payload(
        EffectActionType.CRM_WRITE_RECORD,
        {"url": "https://example.test/write", "data": {"lead_id": 1}},
    )
    assert normalized == {
        "endpoint": "https://example.test/write",
        "headers": {},
        "data": {"lead_id": 1},
        "timeout_s": 30,
    }


def test_effect_router_rejects_invalid_payload_before_handler() -> None:
    router = EffectRouter(transport=_StubTransport())
    with pytest.raises(RuntimeError, match=r"effect_payload_invalid:telegram.send_message:missing_chat_id"):
        asyncio.run(router.execute(EffectActionType.TELEGRAM_SEND_MESSAGE, {"text": "hi"}))

    with pytest.raises(RuntimeError, match=r"effect_payload_invalid:crm.write_record:missing_endpoint"):
        asyncio.run(router.execute(EffectActionType.CRM_WRITE_RECORD, {"data": {"x": 1}}))


def test_effect_router_executes_with_normalized_generic_payload() -> None:
    router = EffectRouter(transport=_StubTransport())
    out = asyncio.run(
        router.execute(
            EffectActionType.ADS_UPDATE_BUDGET,
            {"endpoint": "https://example.test/ads", "payload": {"budget": 42}, "timeout_s": "9"},
        )
    )
    assert out["ok"] is True
    assert out["json"]["echo"] == {"budget": 42}
