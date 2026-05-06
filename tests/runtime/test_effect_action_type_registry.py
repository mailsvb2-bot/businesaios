from __future__ import annotations

import pytest

from runtime._internal.effect_router import EffectRouter
from runtime._internal.effect_types import (
    EffectActionType,
    canonical_effect_action_types,
    normalize_effect_action_type,
    require_effect_action_type,
)
from runtime._internal.http_transport import DisabledNetworkTransport


def test_effect_action_type_registry_matches_router_support() -> None:
    router = EffectRouter(transport=DisabledNetworkTransport())
    assert set(canonical_effect_action_types()) == set(router.supported_action_types())
    assert set(EffectActionType) == set(router.supported_action_enums())


def test_effect_action_type_aliases_normalize_to_canonical_values() -> None:
    assert normalize_effect_action_type("payment_create") == EffectActionType.PAYMENTS_YOOKASSA_CREATE
    assert normalize_effect_action_type("telegram_send_message") == EffectActionType.TELEGRAM_SEND_MESSAGE
    assert normalize_effect_action_type("weather_open_meteo_current") == EffectActionType.WEATHER_OPEN_METEO_CURRENT
    assert normalize_effect_action_type(EffectActionType.LLM_MARKETING_COMPLETE) == EffectActionType.LLM_MARKETING_COMPLETE


def test_effect_action_type_requires_known_registry_value() -> None:
    assert require_effect_action_type("payment_create") is EffectActionType.PAYMENTS_YOOKASSA_CREATE
    with pytest.raises(RuntimeError, match="unsupported_effect_action:unknown.action"):
        require_effect_action_type("unknown.action")
