from __future__ import annotations

from runtime._internal.effect_router import EffectRouter
from runtime._internal.http_transport import DisabledNetworkTransport


def test_effect_router_registry_contains_canonical_domains() -> None:
    router = EffectRouter(transport=DisabledNetworkTransport())
    supported = set(router.supported_action_types())

    assert "telegram.send_message" in supported
    assert "telegram.send_audio" in supported
    assert "telegram.answer_callback" in supported
    assert "telegram.send_chat_action" in supported
    assert "telegram.self_check" in supported
    assert "telegram.poll_updates" in supported
    assert "payments.yookassa.create" in supported
    assert "payments.yookassa.get_status" in supported
    assert "crm.write_record" in supported
    assert "ads.update_budget" in supported
    assert "website.publish_page" in supported
    assert "weather.open_meteo.current" in supported
    assert "llm.marketing_complete" in supported


def test_effect_router_aliases_resolve_to_registered_handlers() -> None:
    router = EffectRouter(transport=DisabledNetworkTransport())

    aliases = {
        "telegram_send_message": "telegram.send_message",
        "telegram_send_audio": "telegram.send_audio",
        "telegram_answer_callback": "telegram.answer_callback",
        "telegram_send_chat_action": "telegram.send_chat_action",
        "payment_create": "payments.yookassa.create",
        "yookassa_get_payment_status": "payments.yookassa.get_status",
        "crm_write": "crm.write_record",
        "ads_update_budget": "ads.update_budget",
        "website_publish_page": "website.publish_page",
        "weather_open_meteo_current": "weather.open_meteo.current",
        "marketing_llm_complete": "llm.marketing_complete",
        "telegram_self_check": "telegram.self_check",
        "telegram_poll_updates": "telegram.poll_updates",
    }

    for alias, canonical in aliases.items():
        assert router.has_handler(alias), alias
        assert router.has_handler(canonical), canonical
