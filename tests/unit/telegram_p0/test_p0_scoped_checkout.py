"""Unified scoped checkout does not charge a foreign or stale catalog plan."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.policies.telegram.tariffs import propose_pay_selected
from runtime.handler_impl.domains.payment_ops import handle_create_payment_and_send_link


def _selected():
    return {"tenant_id": "tenant-1", "product_id": "prod-1", "plan_id": 7,
            "expected_price": 2490, "amount": 2490, "ts": 123}


@pytest.fixture(autouse=True)
def _plans(monkeypatch):
    monkeypatch.setattr("core.plans.plan_by_id",
                        lambda plan_id, *, tenant_id, product_id: (
                            {"plan_id": 7, "price": 2490, "plan_code": "monthly",
                             "title": "Workspace", "scope": "monthly", "days": 30}
                            if (plan_id, tenant_id, product_id) == (7, "tenant-1", "prod-1") else None
                        ))


def _pay(selected=None, **kwargs):
    return propose_pay_selected(
        user_id="user-1", full_access=False,
        selected=_selected() if selected is None else selected,
        tenant_id="tenant-1", product_id="prod-1", business_id="biz-1", **kwargs
    )


def test_disabled_checkout_never_proposes_psp():
    result = _pay()
    assert result.action == "send_message@v1"
    assert "выключена" in result.payload["text"]


def test_scoped_checkout_uses_current_minor_units_and_stable_order():
    first = _pay(checkout_enabled=True)
    second = _pay(checkout_enabled=True)
    assert first.action == second.action == "create_payment_and_send_link@v1"
    assert first.payload["amount"] == 249000
    assert first.payload["order_id"] == second.payload["order_id"]
    assert first.payload["metadata"]["plan_id"] == 7


def test_reject_cross_product_and_stale_selection():
    foreign = _selected()
    foreign["product_id"] = "foreign"
    assert _pay(selected=foreign, checkout_enabled=True).action == "send_message@v1"
    stale = _selected()
    stale["expected_price"] = 1990
    result = _pay(selected=stale, checkout_enabled=True)
    assert result.action == "send_message@v1"
    assert "Цена изменилась" in result.payload["text"]


def test_checkout_executor_rechecks_scope_before_psp():
    calls = []

    class Effects:
        def capture_payment(self, **kwargs):
            calls.append(kwargs)
            return {"ok": False}

    env = SimpleNamespace(decision=SimpleNamespace(decision_id="d", correlation_id="c"))
    body = {"tenant_id": "tenant-1", "business_id": "biz-1",
            "product_id": "prod-1", "user_id": "user-1", "order_id": "order-1",
            "amount": 249000, "expected_amount": 249000, "currency": "RUB",
            "metadata": {"plan_id": 7}}
    with pytest.raises(ValueError, match="TARIFF_PRICE_NOT_AUTHORITATIVE"):
        handle_create_payment_and_send_link({**body, "amount": 199000}, Effects(), env)
    assert calls == []
    with pytest.raises(ValueError, match="TARIFF_CATALOG_SCOPE_MISMATCH"):
        handle_create_payment_and_send_link({**body, "product_id": "foreign"}, Effects(), env)
    assert calls == []
