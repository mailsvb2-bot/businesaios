from __future__ import annotations

import pytest

from runtime.execution.context import execution_business_scope
from runtime.handlers_ops import handle_capture_payment, handle_deploy_policy, handle_reconcile_payment


class Effects:
    def capture_payment(self, **kwargs):
        return kwargs

    def deploy_policy(self, **kwargs):
        return kwargs

    def reconcile_payment(self, **kwargs):
        return kwargs


class Decision:
    decision_id = "d1"
    correlation_id = "c1"
    payload = {}


class Env:
    decision = Decision()


def test_capture_payment_requires_positive_amount():
    with pytest.raises(ValueError):
        handle_capture_payment({"user_id": "u1", "amount": 0, "currency": "EUR"}, Effects(), Env())


def test_deploy_policy_rollout_pct_must_be_bounded():
    with pytest.raises(ValueError):
        handle_deploy_policy({"candidate_policy_id": "p1", "rollout_pct": 101}, Effects(), Env())


def test_reconcile_payment_requires_external_id():
    with pytest.raises(ValueError):
        handle_reconcile_payment({"user_id": "u1"}, Effects(), Env())


def test_capture_payment_requires_business_scope():
    payload = {
        "tenant_id": "tenant-a",
        "product_id": "product-a",
        "order_id": "order-123456",
        "user_id": "u1",
        "amount": 100,
        "currency": "EUR",
    }
    with pytest.raises(ValueError, match="BUSINESS_ID_REQUIRED"):
        handle_capture_payment(payload, Effects(), Env())


def test_capture_payment_uses_bound_business_scope_when_payload_omits_it():
    payload = {
        "tenant_id": "tenant-a",
        "product_id": "product-a",
        "order_id": "order-123456",
        "user_id": "u1",
        "amount": 100,
        "currency": "EUR",
    }
    with execution_business_scope("business-bound"):
        result = handle_capture_payment(payload, Effects(), Env())
    assert result["metadata"]["business_id"] == "business-bound"


def test_capture_payment_signed_business_scope_overrides_untrusted_metadata():
    payload = {
        "tenant_id": "tenant-a",
        "business_id": "business-signed",
        "product_id": "product-a",
        "order_id": "order-123456",
        "user_id": "u1",
        "amount": 100,
        "currency": "EUR",
        "metadata": {"business_id": "business-provider"},
    }
    result = handle_capture_payment(payload, Effects(), Env())
    assert result["metadata"]["business_id"] == "business-signed"
