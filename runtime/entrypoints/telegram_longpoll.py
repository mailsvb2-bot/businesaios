"""BusinesAIOS Telegram entrypoint.

This module is intentionally thin, but it must expose the runtime surface used by
``main.py``:

- ``runtime_bootstrap()``
- ``build_system()``
- ``run_telegram()``
- ``WorldStateV1``

No Telegram SDK, socket, subprocess, urllib, httpx, requests, or direct private
``runtime._internal`` imports are allowed here. Real network I/O is routed through
``runtime.effects`` which delegates into the sealed private effects implementation.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from core.ai.world_state import WorldStateV1
from runtime.boot.env import (
    env_bool,
    env_int,
    env_str,
    mark_telegram_token_source,
    resolve_telegram_bot_token,
)
from runtime.bootstrap import bootstrap as _bootstrap

CANON_RUNTIME_ENTRYPOINT_THIN_SHIM = True
CANON_RUNTIME_ENTRYPOINT_BOOTSTRAP_DELEGATES_TO_SOVEREIGN_BOOTSTRAP = True
CANON_TELEGRAM_ENTRYPOINT_MAIN_CONTRACT = True
CANON_TELEGRAM_ENTRYPOINT_NO_SDK_IMPORTS = True

_LOG = logging.getLogger("businesaios.telegram.entrypoint")


def _telegram_api_base() -> str:
    return env_str("TELEGRAM_API_BASE", "https://api.telegram.org").strip().rstrip("/")


def _telegram_api_url(token: str, method: str) -> str:
    return f"{_telegram_api_base()}/bot{str(token).strip()}/{str(method).strip()}"


def _http_json(method: str, url: str, payload: dict[str, Any] | None = None, *, timeout_s: int = 30) -> Any:
    from runtime.effects import http_json

    return http_json(method, url, payload or {}, timeout_s=timeout_s)


def _response_payload(response: Any) -> dict[str, Any]:
    payload = getattr(response, "json", None)
    if isinstance(payload, dict):
        return payload
    return {}


def _append_event(event_log: Any, *, event_type: str, payload: dict[str, Any] | None = None) -> None:
    if event_log is None:
        return
    event = {
        "event_type": str(event_type),
        "timestamp_ms": int(time.time() * 1000),
        "payload": dict(payload or {}),
    }
    for name in ("append", "record", "emit"):
        fn = getattr(event_log, name, None)
        if callable(fn):
            try:
                fn(event)
                return
            except TypeError:
                continue


def _message_from_update(update: dict[str, Any]) -> dict[str, Any]:
    for key in ("message", "edited_message", "channel_post", "edited_channel_post"):
        value = update.get(key)
        if isinstance(value, dict):
            return value
    callback = update.get("callback_query")
    if isinstance(callback, dict):
        value = callback.get("message")
        if isinstance(value, dict):
            return value
    return {}


def _text_from_update(update: dict[str, Any], message: dict[str, Any]) -> str:
    callback = update.get("callback_query")
    if isinstance(callback, dict):
        data = str(callback.get("data") or "").strip()
        if data:
            return data
    return str(message.get("text") or message.get("caption") or "").strip()


def _chat_id(message: dict[str, Any]) -> str:
    chat = message.get("chat")
    if isinstance(chat, dict):
        value = chat.get("id")
        if value is not None:
            return str(value)
    return ""


def _sender_id(update: dict[str, Any], message: dict[str, Any]) -> str:
    callback = update.get("callback_query")
    if isinstance(callback, dict):
        sender = callback.get("from")
        if isinstance(sender, dict) and sender.get("id") is not None:
            return str(sender.get("id"))
    sender = message.get("from")
    if isinstance(sender, dict) and sender.get("id") is not None:
        return str(sender.get("id"))
    chat_id = _chat_id(message)
    return chat_id or env_str("DEMO_USER_ID", "telegram_user")


def _command_and_args(text: str) -> tuple[str, str]:
    stripped = str(text or "").strip()
    if not stripped.startswith("/"):
        return "", stripped
    head, _, tail = stripped.partition(" ")
    return head, tail.strip()


def _world_state_from_update(update: dict[str, Any]) -> WorldStateV1:
    message = _message_from_update(update)
    text = _text_from_update(update, message)
    command, args = _command_and_args(text)
    chat_id = _chat_id(message)
    user_id = _sender_id(update, message)
    message_date = int(message.get("date") or 0)
    timestamp_ms = message_date * 1000 if message_date > 0 else int(time.time() * 1000)
    tenant_id = env_str("TENANT_ID", "default").strip() or "default"

    return WorldStateV1(
        schema_version=1,
        user={
            "id": user_id,
            "telegram_user_id": user_id,
            "telegram_chat_id": chat_id,
            "timezone": env_str("SYSTEM_TZ", "Europe/Amsterdam"),
        },
        session={
            "source": "telegram",
            "text": text,
            "command": command,
            "args": args,
            "telegram_update_id": update.get("update_id"),
            "telegram_chat_id": chat_id,
        },
        product={
            "name": env_str("PRODUCT_NAME", "BusinesAIOS"),
            "channel": "telegram",
        },
        economy={},
        timestamp_ms=timestamp_ms,
        tenant_id=tenant_id,
        user_id=user_id,
        meta={
            "source": "telegram",
            "transport": "longpoll",
        },
    )


def _validate_startup(token: str) -> None:
    from runtime.effects import classify_startup

    timeout_s = max(1, env_int("TELEGRAM_STARTUP_TIMEOUT_S", 10))
    getme = _response_payload(_http_json("GET", _telegram_api_url(token, "getMe"), timeout_s=timeout_s))
    webhook = _response_payload(_http_json("GET", _telegram_api_url(token, "getWebhookInfo"), timeout_s=timeout_s))
    report = classify_startup(getme, webhook)
    if not report.ok and report.code == "TELEGRAM_WEBHOOK_ENABLED" and env_bool("TELEGRAM_AUTO_DELETE_WEBHOOK", True):
        _http_json(
            "POST",
            _telegram_api_url(token, "deleteWebhook"),
            {"drop_pending_updates": env_bool("TELEGRAM_DROP_PENDING_UPDATES_ON_START", False)},
            timeout_s=timeout_s,
        )
        webhook = _response_payload(_http_json("GET", _telegram_api_url(token, "getWebhookInfo"), timeout_s=timeout_s))
        report = classify_startup(getme, webhook)
    if not report.ok:
        raise RuntimeError(f"{report.code}: {report.hint}")


def _start_health_if_enabled(event_log: Any) -> Any:
    if not env_bool("TELEGRAM_HEALTH_ENABLED", True):
        return None
    port = env_int("TELEGRAM_HEALTH_PORT", 0)
    if port <= 0:
        return None
    from runtime.effects import start_health_server_in_thread
    from runtime.health.server import HealthSnapshot

    host = env_str("HEALTH_HOST", "127.0.0.1")
    snapshot = HealthSnapshot(event_log=event_log, name="telegram")
    return start_health_server_in_thread(snapshot=snapshot, host=host, port=port)


def runtime_bootstrap() -> None:
    """Explicit process bootstrap.

    Hard invariant: no side-effects on import. We load dotenv/token aliases only
    when the sovereign entrypoint explicitly boots the process.
    """

    mark_telegram_token_source()
    _bootstrap()


def build_system() -> Any:
    """Build the canonical runtime tuple expected by ``main.py``.

    The real wiring owner remains ``bootstrap.system_builder``; this entrypoint
    only preserves the public Telegram runtime contract.
    """

    from bootstrap.system_builder import build_system as _build_system

    return _build_system()


def run_telegram(
    *,
    core: Any,
    executor: Any,
    event_log: Any,
    event_store: Any = None,
    payment_outbox: Any = None,
    stack: Any = None,
    learning_job: Any = None,
) -> None:
    """Run Telegram long polling through the canonical decision/execution path.

    External I/O is sealed behind ``runtime.effects``. Each Telegram update is
    converted into the single canonical ``WorldStateV1`` and then routed through
    ``DecisionCore.optimize`` followed by ``RuntimeExecutor.execute``.
    """

    del event_store, payment_outbox, stack, learning_job

    token = resolve_telegram_bot_token()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required for RUN_MODE=telegram")

    _validate_startup(token)
    _start_health_if_enabled(event_log)

    poll_timeout_s = max(1, env_int("TELEGRAM_POLL_TIMEOUT_S", 30))
    request_timeout_s = max(poll_timeout_s + 5, env_int("TELEGRAM_REQUEST_TIMEOUT_S", poll_timeout_s + 5))
    idle_sleep_s = max(0, env_int("TELEGRAM_IDLE_SLEEP_MS", 250)) / 1000.0
    offset: int | None = None

    _append_event(event_log, event_type="telegram_started", payload={"mode": "longpoll"})
    _LOG.info("telegram long polling started")

    while True:
        try:
            payload: dict[str, Any] = {"timeout": poll_timeout_s}
            if offset is not None:
                payload["offset"] = offset
            response = _response_payload(
                _http_json(
                    "GET",
                    _telegram_api_url(token, "getUpdates"),
                    payload,
                    timeout_s=request_timeout_s,
                )
            )
            if not response.get("ok"):
                raise RuntimeError(str(response.get("description") or response))
            updates = response.get("result") if isinstance(response.get("result"), list) else []
            _append_event(event_log, event_type="telegram_polled", payload={"updates": len(updates)})
            for update in updates:
                if not isinstance(update, dict):
                    continue
                raw_update_id = update.get("update_id")
                if raw_update_id is not None:
                    offset = int(raw_update_id) + 1
                state = _world_state_from_update(update)
                envelope = core.optimize(state)
                result = executor.execute(envelope)
                _append_event(
                    event_log,
                    event_type="telegram_update_executed",
                    payload={
                        "update_id": raw_update_id,
                        "decision_id": str(getattr(result, "decision_id", "")),
                        "ok": bool(getattr(result, "ok", False)),
                    },
                )
            if not updates and idle_sleep_s > 0:
                time.sleep(idle_sleep_s)
        except KeyboardInterrupt:
            _append_event(event_log, event_type="telegram_stopped", payload={"reason": "keyboard_interrupt"})
            raise
        except Exception as exc:
            _append_event(
                event_log,
                event_type="telegram_poll_error",
                payload={"error": type(exc).__name__, "message": str(exc)},
            )
            _LOG.exception("telegram polling iteration failed")
            time.sleep(max(1, env_int("TELEGRAM_ERROR_SLEEP_S", 3)))


__all__ = [
    "CANON_RUNTIME_ENTRYPOINT_BOOTSTRAP_DELEGATES_TO_SOVEREIGN_BOOTSTRAP",
    "CANON_RUNTIME_ENTRYPOINT_THIN_SHIM",
    "CANON_TELEGRAM_ENTRYPOINT_MAIN_CONTRACT",
    "CANON_TELEGRAM_ENTRYPOINT_NO_SDK_IMPORTS",
    "WorldStateV1",
    "build_system",
    "run_telegram",
    "runtime_bootstrap",
]
