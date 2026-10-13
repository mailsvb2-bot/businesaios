"""Sealed merchant payment boundary for the existing commercial authorities.

Only server-held YooKassa credentials are used. A browser callback or webhook
cannot set paid status. Network access stays in the existing HTTP transport.
"""
from __future__ import annotations

import base64
import re
from decimal import Decimal
from typing import Any

from runtime._internal.effects_clients.http_client import http_json
from runtime._internal.effects_clients.yookassa_client import resolve_credentials
from runtime._internal.http_transport import HttpTransport
from runtime.platform.config.env_flags import env_str

CANON_COMMERCIAL_MERCHANT_TRANSPORT = True
_PAYMENT_ID = re.compile(r"[A-Za-z0-9-]{1,128}")


def _merchant() -> tuple[str, str, dict[str, str]]:
    merchant, secret, url = resolve_credentials()
    if not merchant or not secret or url != "https://api.yookassa.ru":
        raise RuntimeError("commercial_merchant_credentials_or_origin_invalid")
    token = base64.b64encode(f"{merchant}:{secret}".encode()).decode("ascii")
    return merchant, url, {"Authorization": "Basic " + token,
                           "Content-Type": "application/json",
                           "User-Agent": "businesaios/commercial"}


def create_merchant_payment(*, amount_minor: int, currency: str, customer_id: str,
                            description: str, idempotency_key: str,
                            metadata: dict[str, Any],
                            transport: HttpTransport | None = None) -> dict[str, Any]:
    if (type(amount_minor) is not int or amount_minor <= 0 or currency != "RUB"
            or not isinstance(metadata, dict)
            or not isinstance(idempotency_key, str)
            or not 1 <= len(idempotency_key) <= 128):
        raise ValueError("commercial_merchant_checkout_parameters_invalid")
    url = env_str("YOOKASSA_RETURN_URL", "").strip()
    if not url.startswith("https://") or "example.com" in url:
        raise RuntimeError("commercial_return_url_must_be_configured")
    _, api, headers = _merchant()
    value = str((Decimal(amount_minor) / 100).quantize(Decimal("0.01")))
    response = http_json("POST", api + "/v3/payments", {
        "amount": {"value": value, "currency": "RUB"},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": url},
        "description": description or "Published program",
        "metadata": {**metadata, "customer_id": customer_id},
    }, headers={**headers, "Idempotence-Key": idempotency_key},
        timeout_s=30, transport=transport)
    if not isinstance(response, dict) or not response.get("id"):
        raise RuntimeError("commercial_merchant_checkout_response_invalid")
    return response


def fetch_merchant_payment(payment_id: str, *,
                           transport: HttpTransport | None = None) -> dict[str, Any]:
    if not isinstance(payment_id, str) or not _PAYMENT_ID.fullmatch(payment_id):
        raise ValueError("commercial_merchant_payment_id_invalid")
    _, api, headers = _merchant()
    response = http_json("GET", api + "/v3/payments/" + payment_id,
                         None, headers=headers, timeout_s=20, transport=transport)
    if not isinstance(response, dict) or response.get("id") != payment_id:
        raise RuntimeError("commercial_merchant_payment_response_invalid")
    return response
