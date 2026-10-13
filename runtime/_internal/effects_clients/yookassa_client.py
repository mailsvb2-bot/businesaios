"""Sealed transport: YooKassa API client."""

from __future__ import annotations

import base64
import re
import uuid
from decimal import Decimal
from typing import Any

from runtime._internal.http_transport import HttpTransport
from runtime.platform.config.env_flags import env_str

from .http_client import http_json, safe_result


def resolve_credentials() -> tuple[str, str, str]:
    """Resolve provider creds for staging/prod without guessing."""
    env = env_str("APP_ENV", env_str("ENV", "dev")).lower().strip()
    api_base = env_str("YOOKASSA_API_BASE", "https://api.yookassa.ru").strip().rstrip("/")
    if env in {"prod", "production"}:
        shop_id = env_str("YOOKASSA_SHOP_ID_PROD", env_str("YOOKASSA_SHOP_ID", "")).strip()
        secret = env_str("YOOKASSA_SECRET_KEY_PROD", env_str("YOOKASSA_SECRET_KEY", "")).strip()
        return shop_id, secret, api_base
    if env in {"staging", "stage"}:
        shop_id = env_str("YOOKASSA_SHOP_ID_STAGING", env_str("YOOKASSA_SHOP_ID", "")).strip()
        secret = env_str("YOOKASSA_SECRET_KEY_STAGING", env_str("YOOKASSA_SECRET_KEY", "")).strip()
        return shop_id, secret, api_base
    shop_id = env_str("YOOKASSA_SHOP_ID", "").strip()
    secret = env_str("YOOKASSA_SECRET_KEY", "").strip()
    return shop_id, secret, api_base


def create_payment(
    *,
    amount_rub: Decimal,
    description: str,
    customer_id: str,
    idempotence_key: str | None = None,
    metadata: dict[str, Any] | None = None,
    timeout_s: int = 30,
    transport: HttpTransport | None = None,
) -> tuple[bool, dict[str, Any]]:
    shop_id, secret, api_base = resolve_credentials()
    if not shop_id or not secret:
        return False, {"mode": "unavailable", "reason": "missing YOOKASSA_SHOP_ID/YOOKASSA_SECRET_KEY"}

    # Basic auth
    auth = base64.b64encode(f"{shop_id}:{secret}".encode()).decode("ascii")
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
        # Idempotence-Key must be stable across retries.
        "Idempotence-Key": str(idempotence_key or uuid.uuid4()),
        "User-Agent": "businesaios/yookassa",
    }

    # amount must be string with 2 decimals
    amt = amount_rub.quantize(Decimal("0.01"))
    payload: dict[str, Any] = {
        "amount": {"value": str(amt), "currency": "RUB"},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": env_str("YOOKASSA_RETURN_URL", "https://example.com/return")},
        "description": str(description or "Payment"),
        "metadata": {"customer_id": str(customer_id), **(metadata or {})},
    }

    out = http_json("POST", f"{api_base}/v3/payments", payload, headers=headers, timeout_s=int(timeout_s or 30), transport=transport)
    # keep prior shape
    return True, {
        "yookassa": {
            "id": (out or {}).get("id") if isinstance(out, dict) else None,
            "status": (out or {}).get("status") if isinstance(out, dict) else None,
            "confirmation_url": ((out or {}).get("confirmation") or {}).get("confirmation_url") if isinstance(out, dict) else None,
            "result": safe_result(out),
        }
    }


def get_payment_status(*, external_payment_id: str, timeout_s: int = 20, transport: HttpTransport | None = None) -> str:
    shop_id, secret, api_base = resolve_credentials()
    if not shop_id or not secret:
        return "unknown"

    auth = base64.b64encode(f"{shop_id}:{secret}".encode()).decode("ascii")
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
        "User-Agent": "businesaios/yookassa",
    }

    out = http_json("GET", f"{api_base}/v3/payments/{str(external_payment_id)}", None, headers=headers, timeout_s=int(timeout_s or 20), transport=transport)
    if isinstance(out, dict) and out.get("status"):
        return str(out.get("status"))
    return "unknown"


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
