from __future__ import annotations

"""YooKassa webhook parsing + verification (PURE).

IMPORTANT:
- This module is pure: it performs NO I/O.
- Network binding and provider API calls must live in runtime/_internal.

YooKassa notification formats may vary depending on configured event types.
We keep parsing permissive and require the operator to configure one of the
auth modes:

  webhook auth mode = none | basic | hmac_sha256

For 'basic', provide env vars for basic auth user/pass.

For 'hmac_sha256', provide env var for HMAC secret and send header: X-YK-Signature: <hex>

If auth_mode is 'none', we still enforce best-effort safety by requiring
that the payload contains a recognizable payment id.
"""

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Optional


class WebhookAuthError(RuntimeError):
    pass


class WebhookPayloadError(RuntimeError):
    pass


@dataclass(frozen=True)
class WebhookParsed:
    event: str
    object_type: str
    external_payment_id: str
    notification_id: str
    raw: dict[str, Any]

    @property
    def dedupe_key(self) -> str:
        # Stable idempotency key.
        # Prefer explicit notification id; otherwise fallback to event+payment.
        nid = (self.notification_id or "").strip()
        if nid:
            return f"yk:webhook:{nid}"
        return f"yk:webhook:{self.event}:{self.external_payment_id}"


def _get_header(headers: dict[str, str], name: str) -> str | None:
    for k, v in (headers or {}).items():
        if str(k).lower() == str(name).lower():
            return str(v)
    return None


def verify_webhook(
    *,
    headers: dict[str, str],
    body_bytes: bytes,
    auth_mode: str,
    basic_user: str | None = None,
    basic_pass: str | None = None,
    hmac_secret: str | None = None,
) -> None:
    mode = (auth_mode or "none").strip().lower()
    if mode == "none":
        return
    if mode == "basic":
        auth = _get_header(headers, "Authorization") or ""
        if not auth.lower().startswith("basic "):
            raise WebhookAuthError("missing_basic_auth")
        token = auth.split(" ", 1)[1].strip()
        try:
            decoded = base64.b64decode(token).decode("utf-8")
        except Exception:
            raise WebhookAuthError("bad_basic_auth")
        if ":" not in decoded:
            raise WebhookAuthError("bad_basic_auth")
        u, p = decoded.split(":", 1)
        if str(u) != str(basic_user or "") or str(p) != str(basic_pass or ""):
            raise WebhookAuthError("invalid_basic_credentials")
        return
    if mode == "hmac_sha256":
        sig = _get_header(headers, "X-YK-Signature") or ""
        if not sig:
            raise WebhookAuthError("missing_signature")
        if not hmac_secret:
            raise WebhookAuthError("missing_hmac_secret")
        mac = hmac.new(str(hmac_secret).encode("utf-8"), msg=bytes(body_bytes), digestmod=hashlib.sha256)
        expected = mac.hexdigest()
        # constant-time compare
        if not hmac.compare_digest(str(sig).strip().lower(), str(expected).strip().lower()):
            raise WebhookAuthError("bad_signature")
        return
    raise WebhookAuthError(f"unknown_auth_mode:{mode}")


def parse_notification(*, body_bytes: bytes) -> WebhookParsed:
    try:
        raw = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception as e:
        raise WebhookPayloadError(f"bad_json:{e!r}")

    if not isinstance(raw, dict):
        raise WebhookPayloadError("payload_not_object")

    event = str(raw.get("event") or raw.get("type") or "").strip() or "unknown"
    obj = raw.get("object")
    if not isinstance(obj, dict):
        obj = {}
    object_type = str(obj.get("type") or raw.get("object_type") or "payment").strip() or "payment"

    # YooKassa typically puts payment id into object.id
    external_id = str(obj.get("id") or raw.get("payment_id") or raw.get("id") or "").strip()
    if not external_id:
        raise WebhookPayloadError("missing_payment_id")

    # Notification id may be present as raw.id (not payment id) depending on provider.
    notification_id = str(raw.get("notification_id") or raw.get("id") or "").strip()
    # If raw.id == payment id, it's not a stable notification id; keep it only if it differs.
    if notification_id == external_id:
        notification_id = ""

    return WebhookParsed(
        event=event,
        object_type=object_type,
        external_payment_id=external_id,
        notification_id=notification_id,
        raw=raw,
    )


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return a safe subset of headers for event-store (no secrets)."""
    safe: dict[str, str] = {}
    for k, v in (headers or {}).items():
        lk = str(k).lower()
        if lk in {"authorization", "cookie", "set-cookie"}:
            continue
        if lk.startswith("x-yookassa") or lk.startswith("x-yc") or lk.startswith("x-y-k") or lk.startswith("x-y"):
            # Keep provider correlation ids but not secrets.
            safe[str(k)] = str(v)[:200]
        if lk in {"user-agent", "content-type", "x-request-id", "x-real-ip", "x-forwarded-for"}:
            safe[str(k)] = str(v)[:200]
    return safe


def canonical_webhook_event_payload(parsed: WebhookParsed, *, headers: dict[str, str], body_bytes: bytes) -> tuple[str, dict[str, Any]]:
    """Return (event_type, payload) for event-store."""
    body_hash = hashlib.sha256(body_bytes or b"").hexdigest()
    return (
        "yookassa_webhook_received",
        {
            "event": parsed.event,
            "object_type": parsed.object_type,
            "external_id": parsed.external_payment_id,
            "notification_id": parsed.notification_id or None,
            "body_sha256": body_hash,
            "headers": redact_headers(headers),
        },
    )
