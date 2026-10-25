"""A tenant/product plan catalog cannot authorize another business's checkout."""

import json

from core.plans import catalog
from core.ux.keyboards.payments import kb_sub


def test_plan_catalog_is_explicitly_scoped_and_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog, "_repo_root", lambda: tmp_path)
    monkeypatch.delenv("TENANT_ID", raising=False)
    monkeypatch.delenv("PRODUCT_ID", raising=False)
    legacy = tmp_path / "data" / "plans.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(json.dumps([{"plan_id": 1, "title": "Утро — 5 дней", "price": 1990}]), encoding="utf-8")
    assert catalog.active_plans() == []

    scoped = tmp_path / "data" / "plan_catalogs" / "tenant_one" / "organization_platform.json"
    scoped.parent.mkdir(parents=True)
    scoped.write_text(json.dumps({
        "tenant_id": "tenant_one", "product_id": "organization_platform",
        "plans": [{"plan_id": 2, "title": "Business Workspace", "scope": "monthly",
                   "days": 30, "price": 2490, "plan_code": "workspace_month", "is_active": True}],
    }), encoding="utf-8")
    monkeypatch.setenv("TENANT_ID", "tenant_one")
    monkeypatch.setenv("PRODUCT_ID", "organization_platform")
    assert catalog.plan_by_id(2)["plan_code"] == "workspace_month"
    assert catalog.plan_by_id(1) is None
    monkeypatch.setenv("TENANT_ID", "tenant_two")
    assert catalog.active_plans() == []
    monkeypatch.setenv("TENANT_ID", "tenant_one")
    monkeypatch.setenv("PRODUCT_ID", "metrotherapy")
    assert catalog.active_plans() == []


def test_catalog_rejects_mismatched_ownership(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog, "_repo_root", lambda: tmp_path)
    monkeypatch.setenv("TENANT_ID", "tenant_one")
    monkeypatch.setenv("PRODUCT_ID", "organization_platform")
    scoped = tmp_path / "data" / "plan_catalogs" / "tenant_one" / "organization_platform.json"
    scoped.parent.mkdir(parents=True)
    scoped.write_text(json.dumps({"tenant_id": "tenant_other", "product_id": "organization_platform",
                                  "plans": [{"plan_id": 1}]}), encoding="utf-8")
    assert catalog.load_plans() == []


def test_legacy_therapy_keyboard_never_offers_therapy_checkout():
    markup = kb_sub({"Утро — 5 дней": 1990})
    rows = markup.get("inline_keyboard", [])
    assert not any("sub:morning:" in item.get("callback_data", "") for row in rows for item in row)
    assert not any("1990" in item.get("text", "") for row in rows for item in row)


def test_payment_route_never_proposes_unbound_checkout():
    from core.policies.telegram.tariffs import propose_pay_selected
    proposal = propose_pay_selected(
        user_id="user-1", full_access=False,
        selected={"tenant_id": "tenant_one", "product_id": "organization_platform",
                  "plan_id": 9, "expected_price": 2490},
        tenant_id="tenant_two", product_id="organization_platform",
        default_price_rub=2490, legacy_prices={},
    )
    assert getattr(proposal, "action", "") != "create_payment_and_send_link@v1"


def test_unbound_checkout_route_is_not_reachable_from_policy():
    from pathlib import Path
    import core.policies.telegram.tariffs as module
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert 'return propose(\n        "create_payment_and_send_link@v1"' not in source
