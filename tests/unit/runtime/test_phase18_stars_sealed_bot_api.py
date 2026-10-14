from __future__ import annotations

from typing import Any

import pytest

from runtime._internal.effects_clients import telegram_client
from runtime._internal.effects_clients.telegram_client import TelegramClient


def _api_client(monkeypatch, responses):
    monkeypatch.setattr(telegram_client, "_token", lambda: "test-token")
    client = TelegramClient(transport=object())
    calls: list[tuple[str, dict[str, Any], int]] = []

    def fake_post(*, url, payload, timeout_s):
        calls.append((url.split("/")[-1], dict(payload), timeout_s))
        return responses.pop(0)

    monkeypatch.setattr(client, "_http_post", fake_post)
    return client, calls


def test_invoice_creation_exact_xtr_and_precheckout_result(monkeypatch):
    client, calls = _api_client(monkeypatch, [
        {"ok": True, "result": "https://t.me/$real-invoice"},
        {"ok": True, "result": True},
        {"ok": True, "result": True},
    ])
    assert client.create_stars_invoice_link(
        title="Program", description="One digital lesson",
        invoice_payload="baios-stars-v1:verified", amount_stars=42,
    ) == "https://t.me/$real-invoice"
    assert calls[0][0] == "createInvoiceLink"
    assert calls[0][1] == {
        "title": "Program", "description": "One digital lesson",
        "payload": "baios-stars-v1:verified", "currency": "XTR",
        "prices": [{"label": "Program", "amount": 42}],
    }
    assert "provider_token" not in calls[0][1]
    client.answer_stars_pre_checkout(query_id="query1", approved=False)
    client.answer_stars_pre_checkout(query_id="query2", approved=True)
    assert calls[1][1]["ok"] is False
    assert calls[2][1] == {"pre_checkout_query_id": "query2", "ok": True}
    assert calls[1][2] == calls[2][2] == 8


@pytest.mark.parametrize(
    "price", [0, -10, True, 5.1, "23"],
)
def test_stars_checkout_rejects_invalid_prices_without_network(monkeypatch, price):
    client, calls = _api_client(monkeypatch, [])
    with pytest.raises(ValueError):
        client.create_stars_invoice_link(
            title="Course", description="Digital course",
            invoice_payload="signed", amount_stars=price,
        )
    assert calls == []


def test_provider_history_read_is_exhaustive_and_fails_on_truncation(monkeypatch):
    rows = [{"id": str(i), "amount": 10} for i in range(100)]
    client, calls = _api_client(monkeypatch, [
        {"ok": True, "result": {"transactions": rows}},
        {"ok": True, "result": {"transactions": [{"id": "100", "amount": -10}]}},
    ])
    assert len(client.list_stars_transactions(maximum=101)) == 101
    assert [item[1]["offset"] for item in calls] == [0, 100]

    client2, _ = _api_client(monkeypatch, [
        {"ok": True, "result": {"transactions": rows}},
        {"ok": True, "result": {"transactions": [{"id": "100"}]}},
    ])
    with pytest.raises(RuntimeError, match="truncated"):
        client2.list_stars_transactions(maximum=100)


def test_refund_is_a_sealed_provider_result_not_a_local_money_claim(monkeypatch):
    client, calls = _api_client(monkeypatch, [{"ok": True, "result": True}])
    client.refund_stars_payment(payer_user_id=183, charge_id="tg-charge-1")
    assert calls[0][0] == "refundStarPayment"
    assert calls[0][1] == {
        "user_id": 183, "telegram_payment_charge_id": "tg-charge-1",
    }
    with pytest.raises(ValueError):
        client.refund_stars_payment(payer_user_id=True, charge_id="tg-charge-1")


def test_stars_fail_closed_on_provider_failure_and_untrusted_link(monkeypatch):
    client, _ = _api_client(monkeypatch, [
        {"ok": True, "result": "https://evil.example/pay"},
        {"ok": False, "description": "unavailable"},
    ])
    with pytest.raises(RuntimeError, match="stars_invoice_link_invalid"):
        client.create_stars_invoice_link(
            title="Program", description="Digital course",
            invoice_payload="signed", amount_stars=42,
        )
    with pytest.raises(RuntimeError, match="stars_provider_request_failed"):
        client.answer_stars_pre_checkout(query_id="query", approved=True)
