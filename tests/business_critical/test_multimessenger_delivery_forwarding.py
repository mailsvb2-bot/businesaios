from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from runtime.handlers.delivery_contract import (
    CANON_DELIVERY_METADATA_FORWARDER,
    delivery_kwargs,
)
from runtime.handlers.profit_sprint_onboarding import handle_onboarding_start
from runtime.handlers.platform_effects import (
    handle_apply_offer_patch,
    handle_enqueue_evolution_job,
    handle_suggest_offer_patch,
)
from runtime.handler_impl.domains.admin_ops import handle_admin_set_role
from runtime.handler_impl.domains.payment_ops import (
    handle_create_payment_and_send_link,
    handle_grant_access,
)
from runtime.handler_impl.domains.pricing_ops import handle_select_tariff
from runtime.handler_impl.domains.user_ops import (
    handle_send_weather,
    handle_set_user_setting,
)
from runtime.messaging.channel_types import ALL_CHANNELS
from runtime.ports.effects_admin import EffectsAdminPort
from runtime.ports.effects_comms import EffectsCommsPort
from runtime.ports.effects_platform import EffectsPlatformPort
from runtime.ports.effects_revenue import EffectsRevenuePort


class FakeEffects:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    def send_message(self, **kwargs):
        self.messages.append(dict(kwargs))
        return {"ok": True}


class RecordingDomainEffects:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def _record(self, name: str, kwargs: dict):
        self.calls.append((name, dict(kwargs)))
        return {"ok": True}

    def send_weather(self, **kwargs):
        return self._record("send_weather", kwargs)

    def set_user_setting(self, **kwargs):
        return self._record("set_user_setting", kwargs)

    def select_tariff(self, **kwargs):
        return self._record("select_tariff", kwargs)

    def grant_access(self, **kwargs):
        return self._record("grant_access", kwargs)

    def admin_set_role(self, **kwargs):
        return self._record("admin_set_role", kwargs)

    def enqueue_evolution_job(self, **kwargs):
        return self._record("enqueue_evolution_job", kwargs)

    def suggest_offer_patch(self, **kwargs):
        return self._record("suggest_offer_patch", kwargs)

    def apply_offer_patch(self, **kwargs):
        return self._record("apply_offer_patch", kwargs)

    def capture_payment(self, **kwargs):
        self._record("capture_payment", kwargs)
        return {"ok": False, "router_evidence": None}

    def send_message(self, **kwargs):
        return self._record("send_message", kwargs)


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


@pytest.mark.lock
@pytest.mark.parametrize(
    "handler, payload, expected_method",
    [
        (
            handle_send_weather,
            {"tenant_id": "business-a", "user_id": "owner-1", "city": "Perm"},
            "send_weather",
        ),
        (
            handle_set_user_setting,
            {
                "tenant_id": "business-a",
                "user_id": "owner-1",
                "key": "locale",
                "value": "ru",
            },
            "set_user_setting",
        ),
        (
            handle_select_tariff,
            {
                "tenant_id": "business-a",
                "product_id": "product-a",
                "user_id": "owner-1",
                "tariff": "pro",
                "days": 30,
                "period": "month",
                "amount": 9900,
            },
            "select_tariff",
        ),
        (
            handle_grant_access,
            {
                "tenant_id": "business-a",
                "product_id": "product-a",
                "user_id": "owner-1",
            },
            "grant_access",
        ),
        (
            handle_admin_set_role,
            {
                "tenant_id": "business-a",
                "admin_id": "admin-1",
                "target_user_id": "owner-1",
                "role": "operator",
                "enabled": True,
            },
            "admin_set_role",
        ),
    ],
)
def test_domain_handlers_forward_multimessenger_metadata(
    handler,
    payload: dict,
    expected_method: str,
) -> None:
    effects = RecordingDomainEffects()
    policy = {"fallback_channels": ["viber", "sms", "email"]}
    body = {
        **payload,
        "channel": "wechat",
        "channel_policy": policy,
    }

    handler(body, effects, _env())

    method, kwargs = effects.calls[-1]
    assert method == expected_method
    assert kwargs["channel"] == "wechat"
    assert kwargs["channel_policy"] == policy
    assert kwargs["channel_policy"] is not policy


@pytest.mark.lock
def test_effect_ports_expose_the_same_multimessenger_contract() -> None:
    methods = (
        EffectsCommsPort.send_weather,
        EffectsAdminPort.set_user_setting,
        EffectsAdminPort.admin_set_role,
        EffectsAdminPort.admin_set_perm,
        EffectsAdminPort.set_marketing_copy,
        EffectsRevenuePort.select_tariff,
        EffectsRevenuePort.grant_access,
        EffectsPlatformPort.enqueue_evolution_job,
        EffectsPlatformPort.suggest_offer_patch,
        EffectsPlatformPort.apply_offer_patch,
    )

    for method in methods:
        parameters = inspect.signature(method).parameters
        assert parameters["channel"].default == "telegram"
        assert parameters["channel_policy"].default is None


@pytest.mark.lock
@pytest.mark.parametrize(
    "handler, payload, expected_method",
    [
        (
            handle_enqueue_evolution_job,
            {
                "tenant_id": "business-a",
                "user_id": "owner-1",
                "job_kind": "offer_analysis",
            },
            "enqueue_evolution_job",
        ),
        (
            handle_suggest_offer_patch,
            {
                "tenant_id": "business-a",
                "product": "crm-pro",
                "env": "test",
                "offer_id": "offer-1",
                "action": "improve_headline",
            },
            "suggest_offer_patch",
        ),
        (
            handle_apply_offer_patch,
            {
                "tenant_id": "business-a",
                "product": "crm-pro",
                "env": "test",
                "offer_id": "offer-1",
                "patch": {"headline": "New title"},
                "mode": "dry_run",
            },
            "apply_offer_patch",
        ),
    ],
)
def test_platform_handlers_forward_multimessenger_metadata(
    handler,
    payload: dict,
    expected_method: str,
) -> None:
    effects = RecordingDomainEffects()
    policy = {"fallback_channels": ["email", "sms"]}

    handler(
        {
            **payload,
            "channel": "whatsapp",
            "channel_policy": policy,
        },
        effects,
        _env(),
    )

    method, kwargs = effects.calls[-1]
    assert method == expected_method
    assert kwargs["channel"] == "whatsapp"
    assert kwargs["channel_policy"] == policy
    assert kwargs["channel_policy"] is not policy


@pytest.mark.lock
def test_payment_link_delivery_forwards_multimessenger_metadata() -> None:
    effects = RecordingDomainEffects()
    policy = {"fallback_channels": ["messenger", "email"]}

    handle_create_payment_and_send_link(
        {
            "tenant_id": "business-a",
            "product_id": "product-a",
            "order_id": "order-a",
            "user_id": "owner-1",
            "amount": 9900,
            "currency": "RUB",
            "channel": "line",
            "channel_policy": policy,
        },
        effects,
        _env(),
    )

    method, kwargs = effects.calls[-1]
    assert method == "send_message"
    assert kwargs["channel"] == "line"
    assert kwargs["channel_policy"] == policy
    assert kwargs["channel_policy"] is not policy
