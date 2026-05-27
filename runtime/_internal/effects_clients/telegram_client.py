from __future__ import annotations

"""Sealed transport: Telegram Bot API client."""

import inspect
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from runtime._internal.http_transport import HttpTransport, build_http_transport
from runtime.observability.error_handling import swallow
from runtime.platform.config.env_flags import env_bool, env_str
from runtime.platform.delivery_state import ACCEPTED_PHASE, FINALIZED_PHASE, RECOVERY_PHASE

from ._telegram_delivery_state import (
    accepted_receipt_stale,
    delivery_metadata,
    existing_receipt,
    mark_transport_accepted,
    mark_transport_delivered,
    receipt_phase,
    recover_stale_receipt,
)
from ._telegram_delivery_state import (
    recover_inflight_accepted_receipts as recover_inflight_receipts,
)
from ._telegram_delivery_support import delivery_key as build_delivery_key
from ._telegram_delivery_support import payload_digest as build_payload_digest
from ._telegram_delivery_support import stable_json
from .http_client import http_json


def telegram_api_base() -> str:
    return env_str("TELEGRAM_API_BASE", "https://api.telegram.org").strip().rstrip("/")


def _token() -> str:
    return env_str("TELEGRAM_BOT_TOKEN", "").strip()


def _strict_token_required() -> bool:
    env = env_str("APP_ENV", env_str("ENV", "dev")).lower().strip()
    if env in {"prod", "production"}:
        return True
    return env_bool("TELEGRAM_STRICT_TOKEN", False)


def _stable_json(payload: Mapping[str, Any]) -> str:
    return stable_json(payload)


def _payload_digest(payload: Mapping[str, Any]) -> str:
    return build_payload_digest(payload)


def _delivery_key(*, method: str, chat_id: str, payload: Mapping[str, Any]) -> str:
    return build_delivery_key(method=method, chat_id=chat_id, payload=payload)


@dataclass
class TelegramClient:
    outbound_queue: Any | None = None
    transport: HttpTransport | None = None
    delivery_state: Any | None = None

    def __post_init__(self) -> None:
        if self.transport is None:
            self.transport = build_http_transport()

    def get_me(self, *, token: str | None = None, timeout_s: int = 20) -> Dict[str, Any]:
        t = (token or _token()).strip()
        if not t:
            raise RuntimeError("TELEGRAM_BOT_TOKEN_MISSING")
        base = f"{telegram_api_base()}/bot{t}"
        return http_json("GET", f"{base}/getMe", None, timeout_s=int(timeout_s or 20), transport=self.transport)

    def get_webhook_info(self, *, token: str | None = None, timeout_s: int = 20) -> Dict[str, Any]:
        t = (token or _token()).strip()
        if not t:
            raise RuntimeError("TELEGRAM_BOT_TOKEN_MISSING")
        base = f"{telegram_api_base()}/bot{t}"
        return http_json("GET", f"{base}/getWebhookInfo", None, timeout_s=int(timeout_s or 20), transport=self.transport)

    def answer_callback_query(self, callback_query_id: str, *, text: str | None = None, show_alert: bool = False) -> None:
        token = _token()
        if not token:
            return
        url = f"{telegram_api_base()}/bot{token}/answerCallbackQuery"
        payload: Dict[str, Any] = {"callback_query_id": str(callback_query_id), "cache_time": 0}
        if isinstance(text, str) and text.strip():
            payload["text"] = text.strip()
        if bool(show_alert) is True:
            payload["show_alert"] = True
        try:
            if self._enqueue_transport(
                method="answerCallbackQuery",
                chat_id=None,
                payload=payload,
                priority="high",
                critical=False,
                meta={"callback_query_id": str(callback_query_id), "delivery_phase": "queued", "timeout_s": 15, "priority": "high", "critical": False, "mode": "queued"},
                fn=self._queue_callable(url=url, payload=payload, timeout_s=15),
            ):
                return
        except Exception:
            swallow(__name__, "answer_callback.queue")
        try:
            self._http_post(url=url, payload=payload, timeout_s=15)
        except Exception:
            return

    def send_chat_action(self, *, chat_id: str, action: str = "typing") -> None:
        token = _token()
        if not token:
            return
        url = f"{telegram_api_base()}/bot{token}/sendChatAction"
        payload = {"chat_id": str(chat_id), "action": str(action or "typing")}
        try:
            if self._enqueue_transport(
                method="sendChatAction",
                chat_id=str(chat_id),
                payload=payload,
                priority="high",
                critical=False,
                meta={"chat_id": str(chat_id), "delivery_phase": "queued", "timeout_s": 15, "priority": "high", "critical": False, "mode": "queued"},
                fn=self._queue_callable(url=url, payload=payload, timeout_s=15),
            ):
                return
        except Exception:
            swallow(__name__, "chat_action.queue")
        try:
            self._http_post(url=url, payload=payload, timeout_s=15)
        except Exception:
            return

    def recover_inflight_accepted_receipts(self, *, stale_after_ms: int, limit: int = 100) -> list[dict[str, Any]]:
        return recover_inflight_receipts(self.delivery_state, stale_after_ms=int(stale_after_ms), limit=int(limit))

    def _maybe_requeue_existing_receipt(
        self,
        *,
        existing: Mapping[str, Any] | None,
        method: str,
        chat_id: str,
        payload: Mapping[str, Any],
        priority: Any,
        critical: bool,
        timeout_s: int,
        url: str,
        delivery_key: str,
        payload_digest: str,
    ) -> dict[str, Any] | None:
        if not isinstance(existing, Mapping):
            return None
        if self.outbound_queue is None:
            return None
        if not accepted_receipt_stale(existing):
            return None
        accepted_metadata = delivery_metadata(
            method=method,
            chat_id=str(chat_id),
            payload=payload,
            timeout_s=int(timeout_s or 0),
            priority=priority,
            critical=bool(critical),
            mode="queued_recovery",
            delivery_key=delivery_key,
            payload_digest=payload_digest,
            extra={"delivery_phase": RECOVERY_PHASE, "recovered_from_phase": receipt_phase(existing, default=ACCEPTED_PHASE)},
        )
        queued = self._enqueue_transport(
            method=method,
            chat_id=str(chat_id),
            payload=payload,
            priority=priority,
            critical=bool(critical),
            meta={**accepted_metadata, "delivery_phase": "queued"},
            fn=self._queue_callable(
                url=url,
                payload=payload,
                timeout_s=int(timeout_s or 0),
                delivery_key=delivery_key,
                payload_digest=payload_digest,
                delivered_metadata=delivery_metadata(
                    method=method,
                    chat_id=str(chat_id),
                    payload=payload,
                    timeout_s=int(timeout_s or 0),
                    priority=priority,
                    critical=bool(critical),
                    mode="queued_worker",
                    delivery_key=delivery_key,
                    payload_digest=payload_digest,
                    extra={"delivery_phase": FINALIZED_PHASE},
                ),
            ),
        )
        if not queued:
            return None
        receipt = recover_stale_receipt(self.delivery_state, delivery_key=delivery_key, payload_digest=payload_digest, metadata=accepted_metadata)
        return dict(receipt or existing) if isinstance(receipt or existing, Mapping) else None

    def _http_post(self, *, url: str, payload: Mapping[str, Any], timeout_s: int) -> Dict[str, Any]:
        return http_json("POST", url, dict(payload), timeout_s=int(timeout_s or 30), transport=self.transport)

    def _queue_callable(self, *, url: str, payload: Mapping[str, Any], timeout_s: int, delivery_key: str | None = None, payload_digest: str | None = None, delivered_metadata: Mapping[str, Any] | None = None) -> Callable[[], Dict[str, Any]]:
        def _run() -> Dict[str, Any]:
            out = self._http_post(url=url, payload=payload, timeout_s=timeout_s)
            result = dict(out or {}) if isinstance(out, dict) else {}
            ok = bool(result.get("ok")) if isinstance(result, dict) else True
            if ok and delivery_key and payload_digest:
                external_id = None
                if isinstance(result.get("result"), Mapping):
                    external_id = result.get("result", {}).get("message_id")
                mark_transport_delivered(self.delivery_state,
                    delivery_key=str(delivery_key),
                    external_id=None if external_id is None else str(external_id),
                    payload_digest=str(payload_digest),
                    metadata=dict(delivered_metadata or {}),
                )
            return result
        return _run

    def _enqueue_transport(self, *, method: str, chat_id: str | None, payload: Mapping[str, Any], priority: Any, critical: bool, meta: Mapping[str, Any], fn: Callable[[], Any]) -> bool:
        queue = self.outbound_queue
        if queue is None or not hasattr(queue, "enqueue"):
            return False
        enqueue = queue.enqueue
        numeric_chat_id = int(chat_id) if isinstance(chat_id, str) and chat_id.isdigit() else None
        payload_dict = dict(payload)
        meta_dict = dict(meta or {})
        attempts = (
            {"method": method, "chat_id": numeric_chat_id, "fn": fn, "meta": meta_dict, "priority": priority, "critical": bool(critical)},
            {"method": method, "chat_id": numeric_chat_id, "meta": meta_dict, "payload": payload_dict, "priority": priority, "critical": bool(critical), "fn": fn},
            {"method": method, "chat_id": numeric_chat_id, "meta": meta_dict, "payload": payload_dict, "priority": priority, "critical": bool(critical)},
        )
        for kwargs in attempts:
            try:
                result = enqueue(**kwargs)
                return True if result is None else bool(result)
            except TypeError:
                continue
            except Exception:
                raise
        try:
            sig = inspect.signature(enqueue)
            filtered = {key: value for key, value in attempts[0].items() if key in sig.parameters}
            if filtered:
                result = enqueue(**filtered)
                return True if result is None else bool(result)
        except Exception:
            pass
        return False

    def send_message(
        self,
        *,
        chat_id: str,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        priority: Any = "normal",
        critical: bool = True,
        timeout_s: int = 30,
    ) -> Tuple[bool, Dict[str, Any]]:
        token = _token()
        payload: Dict[str, Any] = {
            "chat_id": str(chat_id),
            "text": str(text),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if isinstance(reply_markup, dict):
            payload["reply_markup"] = reply_markup
        payload_digest = _payload_digest(payload)
        delivery_key = _delivery_key(method="sendMessage", chat_id=str(chat_id), payload=payload)
        existing = existing_receipt(self.delivery_state, delivery_key=delivery_key)
        url = f"{telegram_api_base()}/bot{token}/sendMessage" if token else ""
        if existing is not None:
            recovered = self._maybe_requeue_existing_receipt(
                existing=existing,
                method="sendMessage",
                chat_id=str(chat_id),
                payload=payload,
                priority=priority,
                critical=bool(critical),
                timeout_s=int(timeout_s or 30),
                url=url,
                delivery_key=delivery_key,
                payload_digest=payload_digest,
            )
            current = recovered or existing
            phase = receipt_phase(current)
            return True, {
                "mode": "queued_recovery" if recovered is not None else "dedup",
                "delivery_key": delivery_key,
                "payload_digest": payload_digest,
                "external_id": current.get("external_id"),
                "receipt": current,
                "delivery_phase": phase,
                "delivery_finalized": phase == FINALIZED_PHASE,
            }
        if not token:
            if _strict_token_required():
                return False, {"error": "TELEGRAM_BOT_TOKEN_MISSING", "delivery_key": delivery_key, "payload_digest": payload_digest}
            return True, {"mode": "noop", "reason": "TELEGRAM_BOT_TOKEN_MISSING", "delivery_key": delivery_key, "payload_digest": payload_digest}

        if self.outbound_queue is not None:
            try:
                accepted_metadata = delivery_metadata(
                    method="sendMessage",
                    chat_id=str(chat_id),
                    payload=payload,
                    timeout_s=int(timeout_s or 30),
                    priority=priority,
                    critical=bool(critical),
                    mode="queued",
                    delivery_key=delivery_key,
                    payload_digest=payload_digest,
                    extra={"delivery_phase": ACCEPTED_PHASE},
                )
                queued = self._enqueue_transport(
                    method="sendMessage",
                    chat_id=str(chat_id),
                    payload=payload,
                    priority=priority,
                    critical=bool(critical),
                    meta={**accepted_metadata, "delivery_phase": "queued"},
                    fn=self._queue_callable(
                        url=url,
                        payload=payload,
                        timeout_s=int(timeout_s or 30),
                        delivery_key=delivery_key,
                        payload_digest=payload_digest,
                        delivered_metadata=delivery_metadata(
                            method="sendMessage",
                            chat_id=str(chat_id),
                            payload=payload,
                            timeout_s=int(timeout_s or 30),
                            priority=priority,
                            critical=bool(critical),
                            mode="queued_worker",
                            delivery_key=delivery_key,
                            payload_digest=payload_digest,
                            extra={"delivery_phase": FINALIZED_PHASE},
                        ),
                    ),
                )
                if queued:
                    existing_phase = receipt_phase(existing, default=ACCEPTED_PHASE) if existing is not None else None
                    if existing_phase == ACCEPTED_PHASE:
                        recover_stale_receipt(self.delivery_state,
                            delivery_key=delivery_key,
                            payload_digest=payload_digest,
                            metadata={**accepted_metadata, "delivery_phase": RECOVERY_PHASE},
                        )
                    else:
                        mark_transport_accepted(self.delivery_state,
                            delivery_key=delivery_key,
                            payload_digest=payload_digest,
                            metadata=accepted_metadata,
                        )
                    receipt = existing_receipt(self.delivery_state, delivery_key=delivery_key)
                    phase = receipt_phase(receipt, default=ACCEPTED_PHASE)
                    return True, {"mode": "queued", "delivery_key": delivery_key, "payload_digest": payload_digest, "delivery_finalized": phase == "finalized", "delivery_phase": phase, "receipt": receipt}
            except Exception:
                swallow(__name__, "send_message.queue")
        try:
            out = self._http_post(url=url, payload=payload, timeout_s=int(timeout_s or 30))
            ok = bool(out.get("ok")) if isinstance(out, dict) else True
            result = dict(out or {}) if isinstance(out, dict) else {}
            external_id = None
            if isinstance(result.get("result"), Mapping):
                external_id = result.get("result", {}).get("message_id")
            meta = {"mode": "direct", "delivery_key": delivery_key, "payload_digest": payload_digest, "result": result, "external_id": None if external_id is None else str(external_id), "delivery_finalized": bool(ok)}
            if ok:
                mark_transport_delivered(self.delivery_state, delivery_key=delivery_key, external_id=external_id, payload_digest=payload_digest, metadata={"method": "sendMessage", "chat_id": str(chat_id), "mode": "direct"})
            return ok, meta
        except Exception as e:
            return False, {"mode": "direct", "error": str(e)[:200], "delivery_key": delivery_key, "payload_digest": payload_digest, "delivery_finalized": False}

    def send_audio(
        self,
        *,
        chat_id: str,
        audio_url: str,
        caption: str | None = None,
        priority: Any = "normal",
        critical: bool = True,
        timeout_s: int = 60,
    ) -> Tuple[bool, Dict[str, Any]]:
        token = _token()
        payload: Dict[str, Any] = {"chat_id": str(chat_id), "audio": str(audio_url)}
        if isinstance(caption, str) and caption.strip():
            payload["caption"] = caption.strip()
            payload["parse_mode"] = "HTML"
        payload_digest = _payload_digest(payload)
        delivery_key = _delivery_key(method="sendAudio", chat_id=str(chat_id), payload=payload)
        existing = existing_receipt(self.delivery_state, delivery_key=delivery_key)
        url = f"{telegram_api_base()}/bot{token}/sendAudio" if token else ""
        if existing is not None:
            recovered = self._maybe_requeue_existing_receipt(
                existing=existing,
                method="sendAudio",
                chat_id=str(chat_id),
                payload=payload,
                priority=priority,
                critical=bool(critical),
                timeout_s=int(timeout_s or 60),
                url=url,
                delivery_key=delivery_key,
                payload_digest=payload_digest,
            )
            current = recovered or existing
            phase = receipt_phase(current)
            return True, {"mode": "queued_recovery" if recovered is not None else "dedup", "delivery_key": delivery_key, "payload_digest": payload_digest, "external_id": current.get("external_id"), "receipt": current, "delivery_phase": phase, "delivery_finalized": phase == FINALIZED_PHASE}
        if not token:
            if _strict_token_required():
                return False, {"error": "TELEGRAM_BOT_TOKEN_MISSING", "delivery_key": delivery_key, "payload_digest": payload_digest}
            return True, {"mode": "noop", "reason": "TELEGRAM_BOT_TOKEN_MISSING", "delivery_key": delivery_key, "payload_digest": payload_digest}

        if self.outbound_queue is not None:
            try:
                accepted_metadata = delivery_metadata(
                    method="sendAudio",
                    chat_id=str(chat_id),
                    payload=payload,
                    timeout_s=int(timeout_s or 60),
                    priority=priority,
                    critical=bool(critical),
                    mode="queued",
                    delivery_key=delivery_key,
                    payload_digest=payload_digest,
                    extra={"delivery_phase": ACCEPTED_PHASE},
                )
                queued = self._enqueue_transport(
                    method="sendAudio",
                    chat_id=str(chat_id),
                    payload=payload,
                    priority=priority,
                    critical=bool(critical),
                    meta={**accepted_metadata, "delivery_phase": "queued"},
                    fn=self._queue_callable(
                        url=url,
                        payload=payload,
                        timeout_s=int(timeout_s or 60),
                        delivery_key=delivery_key,
                        payload_digest=payload_digest,
                        delivered_metadata=delivery_metadata(
                            method="sendAudio",
                            chat_id=str(chat_id),
                            payload=payload,
                            timeout_s=int(timeout_s or 60),
                            priority=priority,
                            critical=bool(critical),
                            mode="queued_worker",
                            delivery_key=delivery_key,
                            payload_digest=payload_digest,
                            extra={"delivery_phase": FINALIZED_PHASE},
                        ),
                    ),
                )
                if queued:
                    existing_phase = receipt_phase(existing, default=ACCEPTED_PHASE) if existing is not None else None
                    if existing_phase == ACCEPTED_PHASE:
                        recover_stale_receipt(self.delivery_state,
                            delivery_key=delivery_key,
                            payload_digest=payload_digest,
                            metadata={**accepted_metadata, "delivery_phase": RECOVERY_PHASE},
                        )
                    else:
                        mark_transport_accepted(self.delivery_state,
                            delivery_key=delivery_key,
                            payload_digest=payload_digest,
                            metadata=accepted_metadata,
                        )
                    receipt = existing_receipt(self.delivery_state, delivery_key=delivery_key)
                    phase = receipt_phase(receipt, default=ACCEPTED_PHASE)
                    return True, {"mode": "queued", "delivery_key": delivery_key, "payload_digest": payload_digest, "delivery_finalized": phase == "finalized", "delivery_phase": phase, "receipt": receipt}
            except Exception:
                swallow(__name__, "send_audio.queue")
        try:
            out = self._http_post(url=url, payload=payload, timeout_s=int(timeout_s or 60))
            ok = bool(out.get("ok")) if isinstance(out, dict) else True
            result = dict(out or {}) if isinstance(out, dict) else {}
            external_id = None
            if isinstance(result.get("result"), Mapping):
                external_id = result.get("result", {}).get("message_id")
            meta = {"mode": "direct", "delivery_key": delivery_key, "payload_digest": payload_digest, "result": result, "external_id": None if external_id is None else str(external_id), "delivery_finalized": bool(ok)}
            if ok:
                mark_transport_delivered(self.delivery_state, delivery_key=delivery_key, external_id=external_id, payload_digest=payload_digest, metadata={"method": "sendAudio", "chat_id": str(chat_id), "mode": "direct"})
            return ok, meta
        except Exception as e:
            return False, {"mode": "direct", "error": str(e)[:200], "delivery_key": delivery_key, "payload_digest": payload_digest, "delivery_finalized": False}
