from __future__ import annotations

from dataclasses import replace

import pytest

from billing.telegram_stars_commercial_proof import (
    StarsInvoiceBinding,
    invoice_payload,
    validate_pre_checkout,
    verified_provider_transaction,
    verified_receipt,
)

SECRET = b"phase18-trusted-merchant-key-at-least-32-bytes-long"


def _binding() -> StarsInvoiceBinding:
    return StarsInvoiceBinding(
        tenant_id="tenant-a", business_id="business-a", order_id="order-a",
        invoice_id="invoice-a", customer_id="customer-a",
        telegram_user_id=183, amount_stars=42,
    )


def test_stars_authorized_pre_checkout_is_scoped_to_exact_payer_and_invoice():
    binding = _binding()
    payload = invoice_payload(binding, secret=SECRET)
    query = {"invoice_payload": payload, "currency": "XTR",
             "total_amount": 42, "from": {"id": 183}}
    validate_pre_checkout(binding=binding, secret=SECRET, query=query)
    for changed in (
        {"currency": "RUB"}, {"total_amount": 43},
        {"total_amount": True}, {"from": {"id": 184}},
        {"invoice_payload": invoice_payload(replace(binding, order_id="other"), secret=SECRET)},
    ):
        with pytest.raises(ValueError):
            validate_pre_checkout(
                binding=binding, secret=SECRET, query={**query, **changed},
            )


def test_stars_receipt_requires_independent_verified_charge_and_payer():
    binding = _binding()
    successful = {
        "currency": "XTR", "total_amount": 42,
        "invoice_payload": invoice_payload(binding, secret=SECRET),
        "telegram_payment_charge_id": "charge-1",
    }
    independently_verified = {**successful, "payer_user_id": 183}
    receipt = verified_receipt(
        binding=binding, secret=SECRET, successful_payment=successful,
        payer_user_id=183, verified_provider_receipt=independently_verified,
    )
    assert receipt.charge_id == "charge-1"
    for mismatch in (
        {"telegram_payment_charge_id": "charge-2"},
        {"payer_user_id": 184}, {"total_amount": 41},
        {"currency": "USD"}, {"invoice_payload": "forged"},
    ):
        with pytest.raises(ValueError):
            verified_receipt(
                binding=binding, secret=SECRET, successful_payment=successful,
                payer_user_id=183,
                verified_provider_receipt={**independently_verified, **mismatch},
            )


def test_stars_fail_closed_on_invalid_scopes_and_secret():
    with pytest.raises(ValueError):
        invoice_payload(_binding(), secret=b"short")
    for invalid in (
        replace(_binding(), amount_stars=0),
        replace(_binding(), amount_stars=True),
        replace(_binding(), telegram_user_id=0),
        replace(_binding(), tenant_id=""),
    ):
        with pytest.raises(ValueError):
            invoice_payload(invalid, secret=SECRET)


def test_stars_provider_snapshot_is_authoritative_and_refund_sensitive():
    binding = _binding()
    payment = {
        "id": "telegram-charge-1", "amount": 42, "date": 1791970000,
        "source": {
            "type": "user", "transaction_type": "invoice_payment",
            "user": {"id": 183}, "invoice_payload": invoice_payload(binding, secret=SECRET),
        },
    }
    assert verified_provider_transaction(
        binding=binding, secret=SECRET, transactions=(),
    ) is None
    verified = verified_provider_transaction(
        binding=binding, secret=SECRET, transactions=(payment,),
    )
    assert verified is not None and verified.charge_id == "telegram-charge-1"
    refund = {
        "id": "telegram-charge-1", "amount": -42, "date": 1791971000,
        "receiver": {"type": "user", "user": {"id": 183}},
    }
    assert verified_provider_transaction(
        binding=binding, secret=SECRET, transactions=(payment, refund),
    ) is None
    with pytest.raises(RuntimeError, match="duplicate_invoice_charges"):
        verified_provider_transaction(
            binding=binding, secret=SECRET,
            transactions=(payment, {**payment, "id": "telegram-charge-2"}),
        )
    with pytest.raises(RuntimeError, match="purchase_scope_mismatch"):
        verified_provider_transaction(
            binding=binding, secret=SECRET,
            transactions=({**payment, "source": {**payment["source"], "user": {"id": 184}}},),
        )
    with pytest.raises(RuntimeError, match="purchase_scope_mismatch"):
        verified_provider_transaction(
            binding=binding, secret=SECRET, transactions=({**payment, "amount": 41},),
        )
