"""BusinesAIOS Telegram transport entrypoint.

Telegram is only one transport. Incoming updates are normalized through the
canonical messaging ingress adapter before they reach DecisionCore. This keeps
Telegram, WhatsApp, VK, Max, Slack, Discord, Viber, SMS, email, and webchat on
one WorldState contract instead of creating channel-specific decision paths.
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
from runtime.messaging_ingress import messaging_event_to_world_state, telegram_update_to_messaging_event

CANON_RUNTIME_ENTRYPOINT_THIN_SHIM = True
CANON_RUNTIME_ENTRYPOINT_BOOTSTRAP_DELEGATES_TO_SOVEREIGN_BOOTSTRAP = True
CANON_TELEGRAM_ENTRYPOINT_MAIN_CONTRACT = True
CANON_TELEGRAM_ENTRYPOINT_NO_SDK_IMPORTS = True
CANON_TELEGRAM_WEBHOOK_AND_LONGPOLL_SHARED_DECISION_PATH = True
CANON_TELEGRAM_USES_CANONICAL_MESSAGING_INGRESS = True

_LOG = logging.getLogger("businesaios.telegram.entrypoint")


def _now_ms() -> int:
    return int(time.time() * 1000)


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
        "timestamp_ms": _now_ms(),
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


def _copy_world_state(state: WorldStateV1, *, user: dict[str, Any], session: dict[str, Any], meta: dict[str, Any], timestamp_ms: int) -> WorldStateV1:
    return WorldStateV1(
        schema_version=state.schema_version,
        user=user,
        session=session,
        product=dict(state.product or {}),
        economy=dict(state.economy or {}),
        timestamp_ms=int(timestamp_ms or state.timestamp_ms or _now_ms()),
        tenant_id=state.tenant_id,
        meta=meta,
        user_id=state.user_id,
        safe_mode=state.safe_mode,
        capital=state.capital,
        horizon_state=state.horizon_state,
        behavior=state.behavior,
        price_constraints=state.price_constraints,
        deployment_proposal=state.deployment_proposal,
        manual_override=state.manual_override,
    )


def _world_state_from_update(update: dict[str, Any], *, transport: str = "longpoll") -> WorldStateV1:
    event = telegram_update_to_messaging_event(
        update,
        tenant_id=env_str("TENANT_ID", "default").strip() or "default",
        product_name=env_str("PRODUCT_NAME", "BusinesAIOS"),
        timezone=env_str("SYSTEM_TZ", "Europe/Amsterdam"),
    )
    timestamp_ms = int(event.timestamp_ms or 0) or _now_ms()
    state = messaging_event_to_world_state(event)

    user = {
        **dict(state.user or {}),
        "telegram_user_id": event.user_id,
        "telegram_chat_id": event.chat_id,
    }
    session = {
        **dict(state.session or {}),
        "telegram_update_id": event.update_id,
        "telegram_chat_id": event.chat_id,
    }
    meta = {
        **dict(state.meta or {}),
        "transport": str(transport or "telegram"),
    }
    return _copy_world_state(state, user=user, session=session, meta=meta, timestamp_ms=timestamp_ms)


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


def _execute_update(*, core: Any, executor: Any, event_log: Any, update: dict[str, Any], transport: str) -> None:
    raw_update_id = update.get("update_id")
    state = _world_state_from_update(update, transport=transport)
    envelope = core.optimize(state)
    result = executor.execute(envelope)
    _append_event(
        event_log,
        event_type="telegram_update_executed",
        payload={
            "transport": transport,
            "update_id": raw_update_id,
            "decision_id": str(getattr(result, "decision_id", "")),
            "ok": bool(getattr(result, "ok", False)),
        },
    )


def _run_longpoll(*, token: str, core: Any, executor: Any, event_log: Any) -> None:
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
                _execute_update(core=core, executor=executor, event_log=event_log, update=update, transport="longpoll")
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


def _webhook_public_url(path: str) -> str:
    explicit = env_str("TELEGRAM_WEBHOOK_URL", "").strip()
    if explicit:
        return explicit
    base = env_str("TELEGRAM_WEBHOOK_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not base:
        return ""
    normalized_path = "/" + str(path or "").strip().lstrip("/")
    return f"{base}{normalized_path}"


def _set_webhook_if_configured(*, token: str, path: str, secret_token: str) -> None:
    webhook_url = _webhook_public_url(path)
    if not webhook_url:
        return
    payload: dict[str, Any] = {
        "url": webhook_url,
        "drop_pending_updates": env_bool("TELEGRAM_DROP_PENDING_UPDATES_ON_START", False),
    }
    if secret_token:
        payload["secret_token"] = secret_token
    timeout_s = max(1, env_int("TELEGRAM_STARTUP_TIMEOUT_S", 10))
    response = _response_payload(_http_json("POST", _telegram_api_url(token, "setWebhook"), payload, timeout_s=timeout_s))
    if not response.get("ok"):
        raise RuntimeError(str(response.get("description") or response))


def _run_webhook(*, token: str, core: Any, executor: Any, event_log: Any) -> None:
    from runtime.effects import start_telegram_webhook_server_in_thread
    from runtime.health.server import HealthSnapshot

    host = env_str("TELEGRAM_WEBHOOK_HOST", env_str("HEALTH_HOST", "0.0.0.0"))
    port = env_int("TELEGRAM_WEBHOOK_PORT", env_int("TELEGRAM_HEALTH_PORT", 8088))
    path = env_str("TELEGRAM_WEBHOOK_PATH", "/telegram-webhook/")
    secret_token = env_str("TELEGRAM_WEBHOOK_SECRET_TOKEN", env_str("TELEGRAM_WEBHOOK_SECRET", ""))

    def _on_update(update: dict[str, Any]) -> None:
        _append_event(event_log, event_type="telegram_webhook_received", payload={"update_id": update.get("update_id")})
        _execute_update(core=core, executor=executor, event_log=event_log, update=update, transport="webhook")

    snapshot = HealthSnapshot(event_log=event_log, name="telegram-webhook")
    start_telegram_webhook_server_in_thread(
        host=host,
        port=port,
        path=path,
        on_update=_on_update,
        secret_token=secret_token,
        snapshot=snapshot,
    )
    _set_webhook_if_configured(token=token, path=path, secret_token=secret_token)
    _append_event(event_log, event_type="telegram_started", payload={"mode": "webhook", "port": port, "path": path})
    _LOG.info("telegram webhook receiver started")
    while True:
        time.sleep(max(1, env_int("TELEGRAM_WEBHOOK_IDLE_SLEEP_S", 3600)))


def runtime_bootstrap() -> None:
    mark_telegram_token_source()
    _bootstrap()


def build_system() -> Any:
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
    del event_store, payment_outbox, stack, learning_job

    token = resolve_telegram_bot_token()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required for RUN_MODE=telegram")

    if env_bool("TELEGRAM_USE_WEBHOOK", False) or env_bool("TELEGRAM_WEBHOOK_ENABLED", False):
        _run_webhook(token=token, core=core, executor=executor, event_log=event_log)
        return
    _run_longpoll(token=token, core=core, executor=executor, event_log=event_log)


__all__ = [
    "CANON_RUNTIME_ENTRYPOINT_BOOTSTRAP_DELEGATES_TO_SOVEREIGN_BOOTSTRAP",
    "CANON_RUNTIME_ENTRYPOINT_THIN_SHIM",
    "CANON_TELEGRAM_ENTRYPOINT_MAIN_CONTRACT",
    "CANON_TELEGRAM_ENTRYPOINT_NO_SDK_IMPORTS",
    "CANON_TELEGRAM_WEBHOOK_AND_LONGPOLL_SHARED_DECISION_PATH",
    "CANON_TELEGRAM_USES_CANONICAL_MESSAGING_INGRESS",
    "WorldStateV1",
    "build_system",
    "run_telegram",
    "runtime_bootstrap",
]
