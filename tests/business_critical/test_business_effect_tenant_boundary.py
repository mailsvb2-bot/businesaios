from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.events.log import EventLog
from runtime._internal.effects_actions.payments import access, selection
from runtime._internal.effects_domains import marketing, user_state
from runtime._internal.effects_domains import admin_pricing
from runtime._internal.effects_domains.admin_state_support import (
    apply_pricing_change_effect,
    perform_admin_toggle,
)
from runtime._internal.effects_tenant import assert_event_log_tenant


class FakeEventLog:
    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = str(tenant_id)
        self.events: list[dict] = []

    def emit(self, **event) -> None:
        self.events.append(dict(event))


class FakeAccessEffects:
    def __init__(self, tenant_id: str) -> None:
        self.event_log = FakeEventLog(tenant_id)
        self.delivery_calls: list[dict] = []

    def send_message(self, **kwargs):
        self.delivery_calls.append(dict(kwargs))
        return {"ok": True}


class FakePaymentEffects:
    def __init__(self, tenant_id: str) -> None:
        self.event_log = FakeEventLog(tenant_id)
        self.provider_calls = 0

    def _yookassa_create_payment(self, **kwargs):
        self.provider_calls += 1
        return True, {"yookassa": {"id": "payment-1", "status": "pending"}}


class FakeUserStateEffects(user_state.UserStateEffectsMixin):
    def __init__(self, tenant_id: str) -> None:
        self.event_log = FakeEventLog(tenant_id)
        self.callback_calls: list[dict] = []
        self.delivery_calls: list[dict] = []

    def _telegram_answer_callback(self, callback_query_id: str, **kwargs) -> None:
        self.callback_calls.append({"callback_query_id": callback_query_id, **kwargs})

    def send_message(self, **kwargs):
        self.delivery_calls.append(dict(kwargs))
        return {"ok": True}


class FakeMarketingEffects(marketing.MarketingEffectsMixin):
    def __init__(self, tenant_id: str) -> None:
        self.event_log = FakeEventLog(tenant_id)
        self.callback_calls: list[dict] = []
        self.delivery_calls: list[dict] = []

    def _telegram_answer_callback(self, callback_query_id: str, **kwargs) -> None:
        self.callback_calls.append({"callback_query_id": callback_query_id, **kwargs})

    def send_message(self, **kwargs):
        self.delivery_calls.append(dict(kwargs))
        return {"ok": True}


class FakeAdminOwner:
    def __init__(self) -> None:
        self.callback_calls: list[dict] = []
        self.delivery_calls: list[dict] = []

    def _telegram_answer_callback(self, callback_query_id: str, **kwargs) -> None:
        self.callback_calls.append({"callback_query_id": callback_query_id, **kwargs})

    def send_message(self, **kwargs):
        self.delivery_calls.append(dict(kwargs))
        return {"ok": True}


def test_canonical_event_log_exposes_read_only_tenant_scope() -> None:
    event_log = EventLog(object(), tenant="business-a")

    assert event_log.tenant_id == "business-a"
    with pytest.raises(AttributeError):
        event_log.tenant_id = "business-b"  # type: ignore[misc]


def test_sealed_tenant_assert_rejects_cross_business_scope() -> None:
    with pytest.raises(RuntimeError, match="TENANT_CONTEXT_MISMATCH"):
        assert_event_log_tenant(
            FakeEventLog("business-a"),
            tenant_id="business-b",
            operation="test-operation",
        )


def test_entitlement_mismatch_stops_before_event_or_notification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(access, "assert_called_from_executor", lambda: None)
    effects = FakeAccessEffects("business-a")

    with pytest.raises(RuntimeError, match="TENANT_CONTEXT_MISMATCH"):
        access.grant_access_effect(
            effects,
            decision_id="decision-access",
            correlation_id="correlation-access",
            tenant_id="business-b",
            product_id="crm-pro",
            user_id="user-1",
        )

    assert effects.event_log.events == []
    assert effects.delivery_calls == []


def test_tariff_mismatch_stops_before_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selection, "assert_called_from_executor", lambda: None)
    effects = SimpleNamespace(event_log=FakeEventLog("business-a"))

    with pytest.raises(RuntimeError, match="TENANT_CONTEXT_MISMATCH"):
        selection.select_tariff_effect(
            effects,
            decision_id="decision-tariff",
            correlation_id="correlation-tariff",
            tenant_id="business-b",
            product_id="crm-pro",
            user_id="user-1",
            tariff="pro",
            days=30,
            period="month",
            amount=900,
        )

    assert effects.event_log.events == []


def test_payment_mismatch_stops_before_provider_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selection, "assert_called_from_executor", lambda: None)
    effects = FakePaymentEffects("business-a")

    with pytest.raises(RuntimeError, match="TENANT_CONTEXT_MISMATCH"):
        selection.capture_payment_effect(
            effects,
            decision_id="decision-payment",
            correlation_id="correlation-payment",
            user_id="user-1",
            amount=900,
            currency="RUB",
            provider="yookassa",
            metadata={
                "tenant_id": "business-b",
                "product_id": "crm-pro",
                "order_id": "order-1",
            },
        )

    assert effects.provider_calls == 0
    assert effects.event_log.events == []


def test_pricing_mismatch_stops_before_catalog_prepare(monkeypatch: pytest.MonkeyPatch) -> None:
    prepare_calls = 0

    def fake_prepare(**kwargs):
        nonlocal prepare_calls
        prepare_calls += 1
        raise AssertionError("catalog prepare must not be reached")

    monkeypatch.setattr(admin_pricing, "prepare_offer_price_update", fake_prepare)
    owner = SimpleNamespace(event_log=FakeEventLog("business-a"))

    with pytest.raises(RuntimeError, match="TENANT_CONTEXT_MISMATCH"):
        apply_pricing_change_effect(
            owner,
            decision_id="decision-pricing",
            correlation_id="correlation-pricing",
            admin_id="admin-1",
            tenant_id="business-b",
            product_id="crm-pro",
            environment="test",
            offer_id="crm-pro-monthly",
            new_price=900,
            pricing_version="version-new",
            requested_by="admin-2",
        )

    assert prepare_calls == 0
    assert owner.event_log.events == []


def test_user_setting_mismatch_stops_before_callback_event_and_notification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(user_state, "assert_called_from_executor", lambda: None)
    effects = FakeUserStateEffects("business-a")

    with pytest.raises(RuntimeError, match="TENANT_CONTEXT_MISMATCH"):
        effects.set_user_setting(
            decision_id="decision-setting",
            correlation_id="correlation-setting",
            tenant_id="business-b",
            user_id="user-1",
            key="city",
            value="Berlin",
            callback_query_id="callback-1",
            notify_text="Saved",
        )

    assert effects.callback_calls == []
    assert effects.event_log.events == []
    assert effects.delivery_calls == []


def test_marketing_copy_mismatch_stops_before_callback_event_and_notification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(marketing, "assert_called_from_executor", lambda: None)
    effects = FakeMarketingEffects("business-a")

    with pytest.raises(RuntimeError, match="TENANT_CONTEXT_MISMATCH"):
        effects.set_marketing_copy(
            decision_id="decision-marketing",
            correlation_id="correlation-marketing",
            tenant_id="business-b",
            admin_id="admin-1",
            step_key="followup",
            variant_a="A",
            variant_b="B",
            callback_query_id="callback-1",
            notify_text="Saved",
        )

    assert effects.callback_calls == []
    assert effects.event_log.events == []
    assert effects.delivery_calls == []


def test_admin_toggle_mismatch_stops_before_callback_event_and_notification() -> None:
    owner = FakeAdminOwner()
    event_log = FakeEventLog("business-a")

    with pytest.raises(RuntimeError, match="TENANT_CONTEXT_MISMATCH"):
        perform_admin_toggle(
            owner,
            decision_id="decision-admin",
            correlation_id="correlation-admin",
            tenant_id="business-b",
            admin_id="admin-1",
            target_user_id="user-2",
            field_name="role",
            field_value="operator",
            enabled=True,
            notify_text="Saved",
            notify_reply_markup=None,
            callback_query_id="callback-1",
            channel="telegram",
            channel_policy=None,
            event_log=event_log,
        )

    assert owner.callback_calls == []
    assert event_log.events == []
    assert owner.delivery_calls == []
