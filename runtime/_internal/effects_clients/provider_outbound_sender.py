from __future__ import annotations

import hashlib
import json
import smtplib
import ssl
from collections.abc import Mapping
from contextlib import suppress
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlparse

from runtime.messaging.outbound_message import OutboundMessage, transport_guard_blocks
from runtime.messaging.provider_config import ProviderConfig
from runtime.platform.config.env_flags import env_bool, env_float, env_str

CANON_SEALED_PROVIDER_OUTBOUND_TRANSPORT = True

NOOP_MODE = "configured_noop"
_MAX_RESPONSE_BYTES = 1_048_576
_DELIVERED_STATUSES = frozenset({"delivered", "read"})
_REJECTED_STATUSES = frozenset(
    {
        "cancelled",
        "canceled",
        "error",
        "failed",
        "failure",
        "rejected",
        "undeliverable",
    }
)


def _base_result(*, cfg: ProviderConfig, msg: OutboundMessage) -> dict[str, Any]:
    return {
        "provider": cfg.provider,
        "delivery_key": msg.delivery_key,
    }


def _failure_result(
    *,
    cfg: ProviderConfig,
    msg: OutboundMessage,
    reason: str,
    error: str | None = None,
    status_code: int | None = None,
) -> dict[str, Any]:
    return {
        **_base_result(cfg=cfg, msg=msg),
        "ok": False,
        "accepted": False,
        "delivered": False,
        "noop": False,
        "mode": "failed",
        "external_id": "",
        "reason": str(reason),
        "error": str(error or ""),
        "status_code": status_code,
        "execution_state": "failed",
        "delivery_disposition": "failed",
    }


def _guard_blocked_result(*, cfg: ProviderConfig, msg: OutboundMessage) -> dict[str, Any]:
    return {**_failure_result(cfg=cfg, msg=msg, reason="transport_guard_blocked"), "mode": "blocked", "execution_state": "blocked", "delivery_disposition": "suppressed"}


def _noop_result(*, cfg: ProviderConfig, msg: OutboundMessage) -> dict[str, Any]:
    return {
        **_base_result(cfg=cfg, msg=msg),
        "ok": False,
        "accepted": False,
        "mode": NOOP_MODE,
        "external_id": "",
        "reason": "provider_not_enabled",
        "delivered": False,
        "noop": True,
        "execution_state": "not_sent",
        "delivery_disposition": "suppressed",
        "observability_hint": ("configured_noop: provider wiring is disabled; treat as unsent in delivery metrics"),
    }


def _provider_token(cfg: ProviderConfig) -> str:
    for suffix in ("TOKEN", "API_KEY", "ACCESS_TOKEN"):
        value = env_str(f"{cfg.env_prefix}_{suffix}", "").strip()
        if value:
            return value
    return ""


def _webhook_payload(*, cfg: ProviderConfig, msg: OutboundMessage) -> dict[str, Any]:
    return {
        "provider": cfg.provider,
        "tenant_id": str(msg.tenant_id),
        "recipient": str(msg.user_id),
        "sender": str(cfg.sender or ""),
        "text": str(msg.text),
        "reply_markup": msg.reply_markup,
        "decision_id": str(msg.decision_id),
        "correlation_id": str(msg.correlation_id),
        "delivery_key": msg.delivery_key,
        "payload_digest": msg.payload_digest,
    }


def _decode_response(raw: bytes) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _nested_external_id(payload: Mapping[str, Any]) -> str:
    for key in (
        "external_id",
        "message_id",
        "delivery_id",
        "request_id",
        "message_token",
        "id",
    ):
        value = payload.get(key)
        if isinstance(value, str | int) and str(value).strip():
            return str(value).strip()

    messages = payload.get("messages")
    if isinstance(messages, list):
        for item in messages:
            if isinstance(item, Mapping):
                value = _nested_external_id(item)
                if value:
                    return value

    data = payload.get("data")
    if isinstance(data, Mapping):
        return _nested_external_id(data)
    return ""


def _header_external_id(headers: Any) -> str:
    if headers is None:
        return ""
    for key in (
        "X-Request-ID",
        "X-Request-Id",
        "X-Correlation-ID",
        "X-Slack-Req-Id",
        "X-Line-Request-Id",
    ):
        try:
            value = headers.get(key)
        except Exception:
            value = None
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _response_is_delivered(payload: Mapping[str, Any]) -> bool:
    if payload.get("delivered") is True:
        return True
    status = str(payload.get("status") or payload.get("state") or "").strip().casefold()
    return status in _DELIVERED_STATUSES


def _response_is_rejected(payload: Mapping[str, Any]) -> bool:
    if payload.get("ok") is False or payload.get("success") is False:
        return True
    status = str(payload.get("status") or payload.get("state") or "").strip().casefold()
    if status in _REJECTED_STATUSES:
        return True
    error = payload.get("error")
    if isinstance(error, Mapping):
        return bool(error)
    if isinstance(error, str | list | tuple):
        return bool(error)
    return False


def _send_webhook(*, cfg: ProviderConfig, msg: OutboundMessage) -> dict[str, Any]:
    if transport_guard_blocks(msg.transport_guard, msg):
        return _guard_blocked_result(cfg=cfg, msg=msg)
    endpoint = str(cfg.endpoint or "").strip()
    try:
        parsed = urlparse(endpoint)
    except ValueError:
        parsed = None
    if parsed is None or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return _failure_result(
            cfg=cfg,
            msg=msg,
            reason="provider_endpoint_missing_or_invalid",
        )

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "Idempotency-Key": msg.delivery_key,
        "X-BusinessAIOS-Provider": cfg.provider,
    }
    token = _provider_token(cfg)
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        body = json.dumps(
            _webhook_payload(cfg=cfg, msg=msg),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        request = urllib_request.Request(
            endpoint,
            data=body,
            headers=headers,
            method="POST",
        )
    except (TypeError, UnicodeError, ValueError) as exc:
        return _failure_result(
            cfg=cfg,
            msg=msg,
            reason="provider_request_invalid",
            error=exc.__class__.__name__,
        )
    timeout_s = float(
        env_float(
            f"{cfg.env_prefix}_TIMEOUT_S",
            15.0,
            lo=0.1,
            hi=120.0,
        )
    )
    if transport_guard_blocks(msg.transport_guard, msg):
        return _guard_blocked_result(cfg=cfg, msg=msg)

    try:
        with urllib_request.urlopen(request, timeout=timeout_s) as response:
            status_code = int(getattr(response, "status", 0) or response.getcode() or 0)
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
            response_headers = getattr(response, "headers", None)
    except urllib_error.HTTPError as exc:
        return _failure_result(
            cfg=cfg,
            msg=msg,
            reason="provider_http_error",
            error=exc.__class__.__name__,
            status_code=int(getattr(exc, "code", 0) or 0),
        )
    except (urllib_error.URLError, TimeoutError, OSError) as exc:
        return _failure_result(
            cfg=cfg,
            msg=msg,
            reason="provider_transport_error",
            error=exc.__class__.__name__,
        )

    if not 200 <= status_code < 300:
        return _failure_result(
            cfg=cfg,
            msg=msg,
            reason="provider_http_status_rejected",
            status_code=status_code,
        )
    if len(raw) > _MAX_RESPONSE_BYTES:
        return _failure_result(
            cfg=cfg,
            msg=msg,
            reason="provider_response_too_large",
            status_code=status_code,
        )

    response_payload = _decode_response(raw)
    if _response_is_rejected(response_payload):
        return _failure_result(
            cfg=cfg,
            msg=msg,
            reason="provider_rejected_message",
            status_code=status_code,
        )
    external_id = _nested_external_id(response_payload) or _header_external_id(response_headers)
    if not external_id:
        return _failure_result(
            cfg=cfg,
            msg=msg,
            reason="provider_receipt_missing",
            status_code=status_code,
        )
    if external_id == msg.delivery_key:
        return _failure_result(
            cfg=cfg,
            msg=msg,
            reason="provider_receipt_not_external",
            status_code=status_code,
        )

    delivered = _response_is_delivered(response_payload)
    return {
        **_base_result(cfg=cfg, msg=msg),
        "ok": True,
        "accepted": True,
        "delivered": delivered,
        "noop": False,
        "mode": "webhook" if delivered else "accepted",
        "external_id": external_id,
        "status_code": status_code,
        "execution_state": "sent" if delivered else "accepted",
        "delivery_disposition": "delivered" if delivered else "accepted",
    }


def _smtp_coordinates(cfg: ProviderConfig) -> tuple[str, int, bool]:
    endpoint = str(cfg.endpoint or "").strip()
    if "://" not in endpoint:
        endpoint = f"smtp://{endpoint}"
    try:
        parsed = urlparse(endpoint)
        secure = parsed.scheme == "smtps"
        if parsed.scheme not in {"smtp", "smtps"}:
            return "", 0, False
        port = int(parsed.port or (465 if secure else 587))
    except (TypeError, ValueError):
        return "", 0, False
    return str(parsed.hostname or ""), port, secure


def _safe_header(value: object) -> str:
    text = str(value or "").strip()
    if "\r" in text or "\n" in text:
        return ""
    return text


def _send_smtp(*, cfg: ProviderConfig, msg: OutboundMessage) -> dict[str, Any]:
    if transport_guard_blocks(msg.transport_guard, msg):
        return _guard_blocked_result(cfg=cfg, msg=msg)
    host, port, secure = _smtp_coordinates(cfg)
    recipient = _safe_header(msg.user_id)
    username = env_str(f"{cfg.env_prefix}_USERNAME", "").strip()
    password = env_str(f"{cfg.env_prefix}_PASSWORD", "").strip() or _provider_token(cfg)
    sender = _safe_header(cfg.sender or username)
    if not host or not sender or not recipient:
        return _failure_result(
            cfg=cfg,
            msg=msg,
            reason="smtp_coordinates_missing",
        )
    if bool(username) != bool(password):
        return _failure_result(
            cfg=cfg,
            msg=msg,
            reason="smtp_credentials_incomplete",
        )

    subject = _safe_header(
        str((msg.payload or {}).get("subject") or "").strip()
        or env_str(f"{cfg.env_prefix}_SUBJECT", "BusinessAIOS notification")
    )
    if not subject:
        return _failure_result(
            cfg=cfg,
            msg=msg,
            reason="smtp_header_invalid",
        )

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message_id = make_msgid(domain=sender.partition("@")[2] or None)
    message["Message-ID"] = message_id
    message.set_content(str(msg.text or ""))

    timeout_s = float(
        env_float(
            f"{cfg.env_prefix}_TIMEOUT_S",
            15.0,
            lo=0.1,
            hi=120.0,
        )
    )
    if transport_guard_blocks(msg.transport_guard, msg):
        return _guard_blocked_result(cfg=cfg, msg=msg)
    try:
        starttls = not secure and env_bool(f"{cfg.env_prefix}_STARTTLS", True)
        tls_context = ssl.create_default_context() if secure or starttls else None
        if secure:
            client = smtplib.SMTP_SSL(host, port, timeout=timeout_s, context=tls_context)
        else:
            client = smtplib.SMTP(host, port, timeout=timeout_s)
        try:
            client.ehlo()
            if starttls:
                client.starttls(context=tls_context)
                client.ehlo()
            if username and password:
                client.login(username, password)
            if transport_guard_blocks(msg.transport_guard, msg):
                return _guard_blocked_result(cfg=cfg, msg=msg)
            refused = client.send_message(message)
        finally:
            with suppress(Exception):
                client.quit()
    except (OSError, smtplib.SMTPException) as exc:
        return _failure_result(
            cfg=cfg,
            msg=msg,
            reason="smtp_transport_error",
            error=exc.__class__.__name__,
        )

    if refused:
        return _failure_result(
            cfg=cfg,
            msg=msg,
            reason="smtp_recipient_refused",
        )
    return {
        **_base_result(cfg=cfg, msg=msg),
        "ok": True,
        "accepted": True,
        "delivered": False,
        "noop": False,
        "mode": "accepted",
        "external_id": message_id,
        "execution_state": "accepted",
        "delivery_disposition": "accepted",
    }



class SmtpExplicitError(RuntimeError):
    def __init__(self, code: str, *, delivery_state: str, retryable: bool = False) -> None:
        super().__init__(str(code or "smtp_error")[:160])
        self.code = str(code or "smtp_error")[:160]
        self.delivery_state = str(delivery_state or "unknown")
        self.retryable = bool(retryable)


def _smtp_connect_explicit(
    *, host: str, port: int, security: str, username: str, password: str, timeout_s: float,
):
    if bool(username) != bool(password):
        raise SmtpExplicitError("smtp_credentials_incomplete", delivery_state="not_attempted")
    try:
        tls_context = ssl.create_default_context()
        if security == "ssl":
            client = smtplib.SMTP_SSL(host, port, timeout=timeout_s, context=tls_context)
        else:
            client = smtplib.SMTP(host, port, timeout=timeout_s)
            client.ehlo()
            client.starttls(context=tls_context)
            client.ehlo()
        if username:
            client.login(username, password)
        return client
    except smtplib.SMTPAuthenticationError as exc:
        raise SmtpExplicitError("smtp_authentication_failed", delivery_state="rejected") from exc
    except SmtpExplicitError:
        raise
    except (OSError, smtplib.SMTPException) as exc:
        raise SmtpExplicitError(
            "smtp_pre_send_transport_failure", delivery_state="not_attempted", retryable=True
        ) from exc


def smtp_probe_explicit(
    *, host: str, port: int, security: str, username: str, password: str, timeout_s: float,
) -> dict[str, Any]:
    client = _smtp_connect_explicit(
        host=host, port=port, security=security, username=username, password=password, timeout_s=timeout_s
    )
    try:
        code, _response = client.noop()
        if int(code) >= 400:
            raise SmtpExplicitError("smtp_probe_rejected", delivery_state="rejected")
        return {"ok": True, "smtp_status": int(code)}
    except SmtpExplicitError:
        raise
    except (OSError, smtplib.SMTPException) as exc:
        raise SmtpExplicitError("smtp_probe_failed", delivery_state="not_attempted", retryable=True) from exc
    finally:
        with suppress(Exception):
            client.quit()


def smtp_send_explicit(
    *,
    host: str,
    port: int,
    security: str,
    username: str,
    password: str,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    idempotency_key: str,
    timeout_s: float,
) -> dict[str, Any]:
    digest = hashlib.sha256(str(idempotency_key).encode("utf-8")).hexdigest()
    domain = sender.rsplit("@", 1)[-1] if "@" in sender else "localhost"
    message_id = f"<baios-{digest[:40]}@{domain}>"
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message["Message-ID"] = message_id
    message["Auto-Submitted"] = "auto-generated"
    message.set_content(body)
    client = _smtp_connect_explicit(
        host=host, port=port, security=security, username=username, password=password, timeout_s=timeout_s
    )
    send_started = False
    try:
        send_started = True
        refused = client.send_message(message)
        if refused:
            raise SmtpExplicitError("smtp_recipient_rejected", delivery_state="rejected")
    except SmtpExplicitError:
        raise
    except smtplib.SMTPRecipientsRefused as exc:
        raise SmtpExplicitError("smtp_recipient_rejected", delivery_state="rejected") from exc
    except smtplib.SMTPAuthenticationError as exc:
        raise SmtpExplicitError("smtp_authentication_failed", delivery_state="rejected") from exc
    except (OSError, smtplib.SMTPException) as exc:
        raise SmtpExplicitError(
            "smtp_send_outcome_ambiguous" if send_started else "smtp_pre_send_transport_failure",
            delivery_state="unknown" if send_started else "not_attempted",
            retryable=not send_started,
        ) from exc
    finally:
        with suppress(Exception):
            client.quit()
    return {"ok": True, "accepted": True, "message_id": message_id, "delivery_state": "accepted"}

def send_outbound(*, cfg: ProviderConfig, msg: OutboundMessage) -> dict[str, Any]:
    if transport_guard_blocks(msg.transport_guard, msg):
        return _guard_blocked_result(cfg=cfg, msg=msg)
    if cfg.mode == NOOP_MODE:
        return _noop_result(cfg=cfg, msg=msg)
    if cfg.mode == "webhook":
        return _send_webhook(cfg=cfg, msg=msg)
    if cfg.mode == "smtp":
        return _send_smtp(cfg=cfg, msg=msg)
    return _failure_result(cfg=cfg, msg=msg, reason="provider_mode_unsupported")


__all__ = [
    "CANON_SEALED_PROVIDER_OUTBOUND_TRANSPORT",
    "NOOP_MODE",
    "_MAX_RESPONSE_BYTES",
    "_DELIVERED_STATUSES",
    "_REJECTED_STATUSES",
    "_base_result",
    "_failure_result",
    "_noop_result",
    "_provider_token",
    "_webhook_payload",
    "_decode_response",
    "_nested_external_id",
    "_header_external_id",
    "_response_is_delivered",
    "_response_is_rejected",
    "_send_webhook",
    "_smtp_coordinates",
    "_safe_header",
    "_send_smtp",
    "SmtpExplicitError",
    "smtp_probe_explicit",
    "smtp_send_explicit",
    "send_outbound",
]
