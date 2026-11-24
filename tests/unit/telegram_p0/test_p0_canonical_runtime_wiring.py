"""Canonical platform Telegram runtime scope, projection and pricing proofs."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from core.actions.proof_registry import ACTION_PROOF_EVENT
from core.ai.world_state import WorldStateV1
from core.events import event_types as et
from interfaces.telegram.read_models import user_bundle
from runtime.ports.effects import EffectsPort
from runtime.security.capability_gate import GuardedEffectsPort


def _world(product: dict, user: dict | None = None) -> WorldStateV1:
    return WorldStateV1(
        schema_version=1, user=user or {}, session={}, product=product, economy={},
        timestamp_ms=1, tenant_id="tenant-test", user_id="4001", meta={}
    )


def test_guarded_effects_port_explicitly_forwards_every_method():
    public = [n for n in dir(EffectsPort) if not n.startswith("_") and callable(getattr(EffectsPort, n))]
    missing = [n for n in public if "self._forward(" not in inspect.getsource(getattr(GuardedEffectsPort, n))]
    assert missing == []


def test_guarded_effects_deny_pricing_without_execution_capability():
    called = []
    port = GuardedEffectsPort("secret-token", SimpleNamespace(request_pricing_change=lambda **k: called.append(k)))
    with pytest.raises(Exception):
        port.request_pricing_change(request_id="r1")
    assert called == []


def test_governed_pricing_actions_have_matching_proof_events():
    from governance.time_scale import TimeScale, assert_action_allowed

    for name, event in (
        ("request_pricing_change@v1", et.ADMIN_PRICING_CHANGE_REQUESTED),
        ("apply_pricing_change@v1", et.ADMIN_PRICING_CHANGE_APPLIED),
        ("reject_pricing_change@v1", et.ADMIN_PRICING_CHANGE_REJECTED),
    ):
        assert_action_allowed(name, TimeScale.RUNTIME)
        assert ACTION_PROOF_EVENT[name] == event


def test_hydration_enforces_product_scoped_payment_and_authoritative_roles(monkeypatch):
    recorded = []

    def read_bundle(**kwargs):
        recorded.append(kwargs.get("product_id"))
        return {
            "settings": {"real": True}, "city": "", "selected_tariff": {},
            "mood_last": [], "roles": [], "perms": [],
            "pricing_suggestions": {}, "realtime_state": {}, "autopilot_dashboard": {},
            "marketing_variants": {}, "marketing_bandit": {},
            "payments": {"status": "succeeded"}, "entitlements": {"full_access": True},
        }

    monkeypatch.setattr(user_bundle, "load_user_bundle", read_bundle)
    state = _world({}, {"settings": {"forged": True}, "roles": ["admin"]})
    unscoped = user_bundle.hydrate_world_state_user(state, event_store=object())
    assert recorded[-1] is None
    assert unscoped.user["roles"] == []
    assert unscoped.user["settings"] == {"real": True}
    assert unscoped.economy["payments"]["status"] == "none"
    assert unscoped.economy["entitlements"]["full_access"] is False

    scoped = user_bundle.hydrate_world_state_user(_world({"product_id": "prod-a"}), event_store=object())
    assert recorded[-1] == "prod-a"
    assert scoped.economy["payments"]["status"] == "succeeded"
    assert scoped.economy["entitlements"]["full_access"] is True


def test_admin_pricing_read_model_reads_canonical_events():
    from core.admin.read_models.pricing import pricing_change_requests

    events = [
        {"tenant_id": "tenant-test", "event_type": kind, "timestamp_ms": n,
         "user_id": "admin", "payload": {"request_id": rid, "plan_id": 2, "new_price": 2500,
                                        "product_id": "prod-a", "business_id": "biz-a"}}
        for n, kind, rid in (
            (1, "admin_pricing_change_requested", "r1"),
            (2, "admin_pricing_change_requested", "r2"),
            (3, "admin_pricing_change_applied", "r1"),
            (4, "admin_pricing_change_rejected", "r2"),
        )
    ]

    class Store:
        def iter_events(self, *, tenant_id, start_ms=0, end_ms=None, event_type=None, **kwargs):
            return [e for e in events if e["tenant_id"] == tenant_id and
                    (event_type is None or e["event_type"] == event_type)]

    result = {row["request_id"]: row for row in pricing_change_requests(Store(), tenant_id="tenant-test", now_ms=10)}
    assert {key: value["status"] for key, value in result.items()} == {"r1": "applied", "r2": "rejected"}
    assert result["r1"]["business_id"] == "biz-a"


def test_payments_status_mapping_never_raises_float_type_error():
    from bootstrap.canonical_decision_world_model import CanonicalDecisionWorldModel
    from bootstrap.canonical_decision_world_model_ltv import CanonicalLtvEnricher

    adapter = CanonicalDecisionWorldModel.__new__(CanonicalDecisionWorldModel)
    adapter._ltv = CanonicalLtvEnricher()
    adapter._kind = "hybrid@v1"
    adapter._store = None
    adapter._state_snapshot_store = None
    state = _world({})
    from dataclasses import replace
    state = replace(state, economy={"payments": {"status": "succeeded"}})
    try:
        adapter.enrich_state(state)
    except TypeError as error:
        pytest.fail(f"mapping was coerced as numeric payment count: {error}")
    except Exception:
        pass


@pytest.mark.parametrize(("session", "fast_menu"), [
    ({"command": "/start", "args": ""}, True),
    ({"command": "/menu", "args": ""}, True),
    ({"callback_data": "menu:main", "is_callback": True}, True),
    ({"command": "/start", "args": "cpa_external"}, False),
    ({"callback_data": "cp:section:partners", "is_callback": True}, False),
    ({"command": "/report", "args": ""}, False),
])
def test_start_menu_skips_optional_dashboard_but_always_hydrates_trusted_owner(monkeypatch, session, fast_menu):
    from dataclasses import replace

    captured = []
    def authoritative_bundle(**kwargs):
        captured.append(kwargs)
        return {
            "roles": ["owner"], "perms": ["partners:view"], "settings": {"trusted": True},
            "city": "", "selected_tariff": {}, "mood_last": [], "realtime_state": {},
            "pricing_suggestions": {}, "autopilot_dashboard": {"growth": {"leads": 3}},
            "marketing_variants": {}, "marketing_bandit": {},
            "payments": {"status": "succeeded"}, "entitlements": {"full_access": True},
        }

    monkeypatch.setattr(user_bundle, "load_user_bundle", authoritative_bundle)
    forged = _world({"product_id": "prod-a"}, {"roles": ["admin"], "perms": ["billing:write"]})
    result = user_bundle.hydrate_world_state_user(
        replace(forged, session=session), event_store=object())
    assert captured[-1]["tenant_id"] == "tenant-test"
    assert captured[-1]["product_id"] == "prod-a"
    assert captured[-1]["include_dashboard"] is not fast_menu
    assert result.user["roles"] == ["owner"]
    assert result.user["perms"] == ["partners:view"]
    assert result.user["settings"] == {"trusted": True}
    assert result.economy["entitlements"]["full_access"] is True


def test_start_menu_does_not_query_expensive_autopilot_or_growth_read_models(monkeypatch):
    from core.growth import today_ledger

    called = []
    monkeypatch.setattr(user_bundle, "behavior_snapshot",
                        lambda *args, **kwargs: called.append("behavior"))
    monkeypatch.setattr(today_ledger, "build_today_kpi",
                        lambda *args, **kwargs: called.append("growth"))
    bundle = user_bundle.load_user_bundle(
        event_store=object(), tenant_id="tenant-test", user_id="4001",
        event_warning=lambda **kwargs: None, include_dashboard=False)
    assert called == []
    assert bundle["autopilot_dashboard"] == {}
    assert bundle["behavior"] == {}
    assert isinstance(bundle["roles"], list)
    assert isinstance(bundle["perms"], list)
