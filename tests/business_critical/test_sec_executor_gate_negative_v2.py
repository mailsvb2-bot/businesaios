"""Security regressions for the existing canonical executor context and PSP boundary.

These tests do not create a second executor, business decision path, or mock
the code that is supposed to reject direct paid side effects.
"""
from __future__ import annotations

import threading

import pytest

from runtime.execution.context import (
    assert_called_from_executor,
    current_execution_business_id,
    execution_business_scope,
    executor_context,
    is_executor_context_active,
)
from runtime._internal.effects_actions.payments.yookassa import yookassa_create_payment


def test_executor_context_closed_before_and_after_normal_execution():
    assert not is_executor_context_active()
    with pytest.raises(RuntimeError, match="SIDE_EFFECT_REQUIRES_EXECUTOR"):
        assert_called_from_executor()
    with executor_context("authorized"):
        assert is_executor_context_active()
        assert_called_from_executor()
    assert not is_executor_context_active()


def test_executor_context_resets_after_failure():
    with pytest.raises(ValueError, match="fail"):
        with executor_context("authorized"):
            assert is_executor_context_active()
            raise ValueError("fail")
    assert not is_executor_context_active()


def test_executor_context_isolated_from_new_thread():
    observed = []
    with executor_context("authorized"):
        worker = threading.Thread(target=lambda: observed.append(is_executor_context_active()))
        worker.start()
        worker.join(timeout=3)
        assert not worker.is_alive()
    assert observed == [False]


def test_execution_business_scope_restores_previous_identity_even_on_failure():
    original = current_execution_business_id()
    with execution_business_scope("tenant-a"):
        assert current_execution_business_id() == "tenant-a"
        with pytest.raises(ValueError):
            with execution_business_scope("tenant-b"):
                assert current_execution_business_id() == "tenant-b"
                raise ValueError("fail")
        assert current_execution_business_id() == "tenant-a"
    assert current_execution_business_id() == original


@pytest.mark.parametrize("currency,amount", [
    ("RUB", 100), ("USD", 100), ("RUB", 0),
])
def test_payment_create_is_rejected_before_any_psp_side_effect(currency, amount):
    class NoCalls:
        def __getattr__(self, attr):
            raise AssertionError("External transport unexpectedly touched: " + attr)

    with pytest.raises(RuntimeError, match="SIDE_EFFECT_REQUIRES_EXECUTOR"):
        yookassa_create_payment(
            effects=NoCalls(), decision_id="decision-1", amount=amount,
            currency=currency, user_id="user-1",
            metadata={"order_id": "order-1"},
        )
