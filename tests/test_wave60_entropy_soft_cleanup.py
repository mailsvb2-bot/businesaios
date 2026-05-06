from __future__ import annotations

from core.tenancy.normalization import normalize_tenant_id_or_unknown, UNKNOWN_TENANT_ID
from runtime.handlers_messaging import _resolve_tenant_id
from runtime.telegram_message_factory import resolve_tenant_id as resolve_message_factory_tenant_id
from runtime.firewall.effect_port import GuardedEffects
from core.policies.telegram.handlers.offer_outcome import handle_offer_outcome


def test_normalize_tenant_id_or_unknown_collapses_placeholder_values():
    assert normalize_tenant_id_or_unknown("default") == UNKNOWN_TENANT_ID
    assert normalize_tenant_id_or_unknown("legacy") == UNKNOWN_TENANT_ID
    assert normalize_tenant_id_or_unknown("tenant-1") == "tenant-1"


def test_runtime_handler_message_resolution_returns_unknown_tenant_when_no_real_value():
    env = type("Env", (), {"decision": type("D", (), {"tenant_id": "default"})(), "tenant_id": "legacy", "default_tenant_id": "default"})()
    assert _resolve_tenant_id({"track_payload": {"tenant_id": "default"}}, env) == UNKNOWN_TENANT_ID


def test_message_factory_resolution_prefers_real_tenant_and_falls_back_to_unknown():
    assert resolve_message_factory_tenant_id(tenant_id="default", track_payload={"tenant_id": "legacy"}) == UNKNOWN_TENANT_ID
    assert resolve_message_factory_tenant_id(tenant_id="tenant-1", track_payload={"tenant_id": "legacy"}) == "tenant-1"


class _Impl:
    def __init__(self):
        self.last = None

    def send_message(self, **kwargs):
        self.last = kwargs
        return kwargs

    def capture_payment(self, **kwargs):
        return kwargs

    def deploy_policy(self, **kwargs):
        return True

    def rollback_policy(self, **kwargs):
        return True


def test_guarded_effects_legacy_send_message_uses_unknown_tenant(monkeypatch):
    monkeypatch.setattr("runtime.firewall.effect_port.require_effect_capability", lambda token: None)
    impl = _Impl()
    guarded = GuardedEffects("tok", impl)
    guarded.send_message("u1", "hello")
    assert impl.last["tenant_id"] == UNKNOWN_TENANT_ID


def test_offer_outcome_uses_unknown_tenant_when_state_has_placeholder():
    ctx = type("Ctx", (), {
        "callback_data": "offer:accept:offer-1",
        "callback_query_id": None,
        "state": type("State", (), {"tenant_id": "default", "product": {"product_id": "p1", "domain": "sales"}})(),
        "selected_tariff": None,
        "is_admin": False,
    })()
    proposed = handle_offer_outcome(ctx, user_id="u1", default_price_rub=600)
    assert proposed is not None
    steps = proposed["steps"]
    track_step = next(s for s in steps if s.get("action") == "track_event@v1")
    assert track_step["payload"]["tenant_id"] == UNKNOWN_TENANT_ID
