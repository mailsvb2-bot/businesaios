from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from runtime._internal.effects_actions import telegram_actions
from runtime._internal.effects_actions.payments import access
from runtime._internal.effects_domains import admin_pricing, marketing, user_state
from runtime._internal.effects_domains.admin_state_support import (
    apply_pricing_change_effect,
    perform_admin_toggle,
)


class FakeEventLog:
    def __init__(self, *, tenant_id: str = "business-a", fail_event: str | None = None) -> None:
        self._tenant_id = tenant_id
        self.fail_event = fail_event
        self.events: list[dict] = []

    def emit(self, **event) -> None:
        if event.get("event_type") == self.fail_event:
            raise RuntimeError("event-store-down")
        self.events.append(dict(event))


class FakeUserStateEffects(user_state.UserStateEffectsMixin):
    def __init__(self) -> None:
        self.event_log = FakeEventLog()
        self.callback_calls: list[dict] = []

    def _telegram_answer_callback(self, callback_query_id: str, **kwargs) -> None:
        self.callback_calls.append({"callback_query_id": callback_query_id, **kwargs})

    def send_message(self, **kwargs):
        return {"ok": True, "router_evidence": {"source": "connector", "verified": True, "status": "verified"}}


class FakeMarketingEffects(marketing.MarketingEffectsMixin):
    def __init__(self) -> None:
        self.event_log = FakeEventLog()
        self.callback_calls: list[dict] = []

    def _telegram_answer_callback(self, callback_query_id: str, **kwargs) -> None:
        self.callback_calls.append({"callback_query_id": callback_query_id, **kwargs})

    def send_message(self, **kwargs):
        return {"ok": True}


class FakeAdminOwner:
    def __init__(self) -> None:
        self.callback_calls: list[dict] = []

    def _telegram_answer_callback(self, callback_query_id: str, **kwargs) -> None:
        self.callback_calls.append({"callback_query_id": callback_query_id, **kwargs})

    def send_message(self, **kwargs):
        return {"ok": True}


class FakeAccessEffects:
    def __init__(self, *, tenant_id: str = "business-a") -> None:
        self.event_log = FakeEventLog(tenant_id=tenant_id)

    def send_message(self, **kwargs):
        return {"ok": True}


def test_telegram_polling_port_contract_uses_timeout_s_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict = {}

    def fake_poll(_effects, **kwargs):
        observed.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(telegram_actions, "poll_telegram_updates_effect", fake_poll)
    method = telegram_actions.TelegramEffectsMixin.poll_telegram_updates
    parameters = inspect.signature(method).parameters

    assert "token" not in parameters
    assert "timeout" not in parameters
    assert "timeout_s" in parameters

    result = method(SimpleNamespace(), offset=7, timeout_s=12, limit=44)

    assert result == {"ok": True}
    assert observed == {"offset": 7, "timeout_s": 12, "limit": 44}


def test_user_setting_callback_gets_full_execution_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(user_state, "assert_called_from_executor", lambda: None)
    effects = FakeUserStateEffects()

    result = effects.set_user_setting(
        decision_id="decision-setting",
        correlation_id="correlation-setting",
        user_id="user-1",
        key="city",
        value="Berlin",
        callback_query_id="callback-setting",
    )

    assert effects.callback_calls == [
        {
            "callback_query_id": "callback-setting",
            "user_id": "user-1",
            "decision_id": "decision-setting",
            "correlation_id": "correlation-setting",
        }
    ]
    assert result["router_evidence"]["source"] == "ledger"
    assert result["router_evidence"]["verified"] is True


def test_admin_toggle_callback_gets_full_execution_context() -> None:
    owner = FakeAdminOwner()
    event_log = FakeEventLog()

    result = perform_admin_toggle(
        owner,
        decision_id="decision-admin",
        correlation_id="correlation-admin",
        admin_id="admin-1",
        target_user_id="user-2",
        field_name="role",
        field_value="operator",
        enabled=True,
        notify_text=None,
        notify_reply_markup=None,
        callback_query_id="callback-admin",
        channel="telegram",
        event_log=event_log,
    )

    assert owner.callback_calls == [
        {
            "callback_query_id": "callback-admin",
            "user_id": "admin-1",
            "decision_id": "decision-admin",
            "correlation_id": "correlation-admin",
        }
    ]
    assert result["router_evidence"]["source"] == "ledger"


def test_marketing_copy_callback_gets_full_execution_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(marketing, "assert_called_from_executor", lambda: None)
    effects = FakeMarketingEffects()

    result = effects.set_marketing_copy(
        decision_id="decision-marketing",
        correlation_id="correlation-marketing",
        admin_id="admin-7",
        step_key="lead-followup",
        variant_a="A",
        variant_b="B",
        callback_query_id="callback-marketing",
    )

    assert effects.callback_calls[0]["user_id"] == "admin-7"
    assert effects.callback_calls[0]["decision_id"] == "decision-marketing"
    assert result["router_evidence"]["source"] == "ledger"


def test_entitlement_grant_requires_explicit_business_and_product_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(access, "assert_called_from_executor", lambda: None)
    effects = FakeAccessEffects()

    with pytest.raises(RuntimeError, match="PRODUCT_ID_REQUIRED"):
        access.grant_access_effect(
            effects,
            decision_id="decision-access",
            correlation_id="correlation-access",
            user_id="user-9",
            tenant_id="business-a",
            product_id="",
        )


def test_entitlement_grant_rejects_event_log_tenant_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(access, "assert_called_from_executor", lambda: None)
    effects = FakeAccessEffects(tenant_id="business-a")

    with pytest.raises(RuntimeError, match="TENANT_CONTEXT_MISMATCH"):
        access.grant_access_effect(
            effects,
            decision_id="decision-access",
            correlation_id="correlation-access",
            user_id="user-9",
            tenant_id="business-b",
            product_id="crm-pro",
        )


def test_entitlement_grant_emits_canonical_event_and_ledger_proof(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(access, "assert_called_from_executor", lambda: None)
    effects = FakeAccessEffects()

    result = access.grant_access_effect(
        effects,
        decision_id="decision-access",
        correlation_id="correlation-access",
        user_id="user-9",
        tenant_id="business-a",
        product_id="crm-pro",
        grant_key="order-77",
    )

    assert [event["event_type"] for event in effects.event_log.events] == ["entitlement_granted"]
    assert result["router_evidence"]["source"] == "ledger"
    assert result["router_evidence"]["external_refs"] == [
        "entitlement:business-a:crm-pro:user-9:order-77"
    ]


def test_pricing_change_rolls_back_files_when_audit_event_cannot_persist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plans_path = tmp_path / "plans.json"
    override_path = tmp_path / "pricing_version_override.txt"
    original_plans = [{"plan_id": 1, "price": 100}]
    plans_path.write_text(json.dumps(original_plans), encoding="utf-8")
    override_path.write_text("version-old\n", encoding="utf-8")

    def fake_env_path(name: str, _default: str) -> Path:
        return plans_path if name == "PLANS_PATH" else override_path

    monkeypatch.setattr(admin_pricing, "env_path", fake_env_path)
    monkeypatch.setattr(admin_pricing, "env_bool", lambda *_args, **_kwargs: False)
    owner = SimpleNamespace(event_log=FakeEventLog(fail_event="admin_pricing_change_applied"))

    with pytest.raises(RuntimeError, match="event-store-down"):
        apply_pricing_change_effect(
            owner,
            decision_id="decision-pricing",
            correlation_id="correlation-pricing",
            admin_id="admin-1",
            plan_id=1,
            new_price=900,
            pricing_version="version-new",
            requested_by="admin-2",
        )

    assert json.loads(plans_path.read_text(encoding="utf-8")) == original_plans
    assert override_path.read_text(encoding="utf-8") == "version-old\n"


def test_pricing_change_returns_ledger_proof_only_after_storage_and_event_commit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plans_path = tmp_path / "plans.json"
    override_path = tmp_path / "pricing_version_override.txt"
    plans_path.write_text(json.dumps([{"plan_id": 1, "price": 100}]), encoding="utf-8")

    def fake_env_path(name: str, _default: str) -> Path:
        return plans_path if name == "PLANS_PATH" else override_path

    monkeypatch.setattr(admin_pricing, "env_path", fake_env_path)
    monkeypatch.setattr(admin_pricing, "env_bool", lambda *_args, **_kwargs: False)
    event_log = FakeEventLog()
    owner = SimpleNamespace(event_log=event_log)

    result = apply_pricing_change_effect(
        owner,
        decision_id="decision-pricing",
        correlation_id="correlation-pricing",
        admin_id="admin-1",
        plan_id=1,
        new_price=900,
        pricing_version="version-new",
        requested_by="admin-2",
    )

    assert json.loads(plans_path.read_text(encoding="utf-8"))[0]["price"] == 900
    assert override_path.read_text(encoding="utf-8").strip() == "version-new"
    assert event_log.events[-1]["event_type"] == "admin_pricing_change_applied"
    assert result["router_evidence"]["source"] == "ledger"
    assert result["router_evidence"]["verified"] is True
