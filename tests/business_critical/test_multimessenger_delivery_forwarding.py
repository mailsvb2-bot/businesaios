from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.handlers.delivery_contract import (
    CANON_DELIVERY_METADATA_FORWARDER,
    delivery_kwargs,
)
from runtime.handlers.profit_sprint_onboarding import handle_onboarding_start
from runtime.messaging.channel_types import ALL_CHANNELS


class FakeEffects:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    def send_message(self, **kwargs):
        self.messages.append(dict(kwargs))
        return {"ok": True}


def _env() -> SimpleNamespace:
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="signed-decision",
            correlation_id="signed-correlation",
        )
    )


@pytest.mark.lock
@pytest.mark.parametrize("channel", ALL_CHANNELS)
def test_delivery_forwarder_preserves_every_canonical_channel(channel: str) -> None:
    policy = {"fallback_channels": ["email"], "critical": False}

    forwarded = delivery_kwargs(
        {"channel": channel, "channel_policy": policy}
    )

    assert CANON_DELIVERY_METADATA_FORWARDER is True
    assert forwarded == {"channel": channel, "channel_policy": policy}
    assert forwarded["channel_policy"] is not policy


@pytest.mark.lock
def test_onboarding_forwards_signed_multimessenger_delivery_metadata() -> None:
    effects = FakeEffects()

    handle_onboarding_start(
        {
            "tenant_id": "business-a",
            "user_id": "owner-1",
            "product_id": "product-a",
            "channel": "web_chat",
            "channel_policy": {
                "fallback_channels": ["whatsapp", "sms", "email"]
            },
        },
        effects,
        _env(),
    )

    call = effects.messages[-1]
    assert call["decision_id"] == "signed-decision"
    assert call["correlation_id"] == "signed-correlation"
    assert call["tenant_id"] == "business-a"
    assert call["user_id"] == "owner-1"
    assert call["channel"] == "web_chat"
    assert call["channel_policy"] == {
        "fallback_channels": ["whatsapp", "sms", "email"]
    }


@pytest.mark.lock
def test_delivery_forwarder_keeps_legacy_telegram_default() -> None:
    assert delivery_kwargs({}) == {
        "channel": "telegram",
        "channel_policy": None,
    }
