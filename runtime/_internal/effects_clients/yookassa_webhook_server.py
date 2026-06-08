from __future__ import annotations

"""Sealed transport: YooKassa webhook server.

Extracted from runtime/_internal/_effects_impl.py without changing behavior.
"""

import base64
import hmac
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from runtime.observability.error_handling import swallow
from runtime.platform.config.env_flags import env_str
from runtime.tenancy import normalize_tenant_id


def _extract_webhook_tenant_id(raw: dict[str, Any]) -> str:
    obj = raw.get("object") if isinstance(raw.get("object"), dict) else {}
    metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    for candidate in (
        raw.get("tenant_id"),
        raw.get("metadata", {}).get("tenant_id") if isinstance(raw.get("metadata"), dict) else None,
        metadata.get("tenant_id"),
        metadata.get("tenant"),
    ):
        tenant_id = normalize_tenant_id(candidate)
        if tenant_id:
            return tenant_id
    return "unknown_tenant"


def start_yookassa_webhook_server_in_thread(
    *,
    host: str,
    port: int,
    path: str,
    event_store: Any,
    payment_outbox: Any,
    auth_mode: str | None = None,
    webhook_token: str | None = None,
) -> Any:
    """Start a minimal YooKassa webhook HTTP server in a daemon thread."""

    auth_mode = (auth_mode or env_str("YOOKASSA_WEBHOOK_AUTH_MODE", "none") or "none").strip().lower()
    if env_str("APP_ENV", env_str("ENV", "dev")).lower().strip() in {"prod", "production"} and auth_mode == "none":
        raise RuntimeError("YOOKASSA_WEBHOOK_AUTH_MODE=none is not allowed in prod")

    basic_user = env_str("YOOKASSA_WEBHOOK_BASIC_USER", "") or None
    basic_pass = env_str("YOOKASSA_WEBHOOK_BASIC_PASS", "") or None
    hmac_secret = env_str("YOOKASSA_WEBHOOK_HMAC_SECRET", "") or None
    token_secret = webhook_token or (env_str("YOOKASSA_WEBHOOK_TOKEN", "") or None)

    from runtime.payments import (
        parse_yookassa_notification as parse_notification,
    )
    from runtime.payments import (
        verify_yookassa_webhook as verify_webhook,
    )

    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            try:
                if self.path != str(path):
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"not_found")
                    return

                # Auth
                if auth_mode == "basic":
                    hdr = self.headers.get("Authorization")
                    if not hdr or not hdr.startswith("Basic "):
                        self.send_response(401)
                        self.end_headers()
                        return
                    try:
                        raw = base64.b64decode(hdr.split(" ", 1)[1]).decode("utf-8")
                        u, p = raw.split(":", 1)
                    except Exception:
                        self.send_response(401)
                        self.end_headers()
                        return
                    if u != (basic_user or "") or p != (basic_pass or ""):
                        self.send_response(401)
                        self.end_headers()
                        return
                elif auth_mode == "token":
                    # Historical/test header name: X-Webhook-Token.
                    hdr = self.headers.get("X-Webhook-Token") or self.headers.get("X-YooKassa-Token")
                    expected = str(token_secret or "").strip()
                    got = str(hdr or "").strip()
                    if (not expected) or (not got) or (not hmac.compare_digest(expected, got)):
                        self.send_response(401)
                        self.end_headers()
                        return

                length = int(self.headers.get("Content-Length") or "0")
                raw = self.rfile.read(length) if length > 0 else b""

                # Verify webhook signature / integrity.
                # For token auth we already validated the header above.
                try:
                    if auth_mode in {"basic", "hmac_sha256"}:
                        verify_webhook(
                            headers=dict(self.headers),
                            body_bytes=raw,
                            auth_mode=auth_mode,
                            basic_user=basic_user,
                            basic_pass=basic_pass,
                            hmac_secret=hmac_secret,
                        )
                except Exception:
                    self.send_response(401)
                    self.end_headers()
                    self.wfile.write(b"unauthorized")
                    return

                notif = parse_notification(body_bytes=raw)
                tenant_id = _extract_webhook_tenant_id(notif.raw)

                # Write to event store and outbox
                try:
                    if event_store is not None:
                        event_store.emit(
                            tenant_id=tenant_id,
                            event_type="yookassa_webhook_received",
                            payload={
                                "type": "yookassa_webhook",
                                "notification": notif,
                                "tenant_id": tenant_id,
                            },
                        )
                except Exception:
                    swallow(__name__, "event_store.emit")

                try:
                    if payment_outbox is not None:
                        payload = {
                            "type": "yookassa_webhook",
                            # Keep raw notification for downstream handlers.
                            "payload": notif.raw,
                        }
                        if hasattr(payment_outbox, "enqueue_once"):
                            payment_outbox.enqueue_once(dedupe_key=str(notif.dedupe_key), payload=payload)
                        elif hasattr(payment_outbox, "enqueue"):
                            payment_outbox.enqueue(payload)
                        else:
                            raise AttributeError("payment_outbox has no enqueue/enqueue_once")
                except Exception:
                    swallow(__name__, "payment_outbox.enqueue")

                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
            except Exception:
                try:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"bad_request")
                except Exception:
                    swallow(__name__, "handler.fail")

        def log_message(self, format, *args):  # noqa: A002
            return

    httpd = HTTPServer((str(host), int(port)), _Handler)
    th = threading.Thread(target=httpd.serve_forever, daemon=True, name="yookassa-webhook")
    th.start()
    return httpd
