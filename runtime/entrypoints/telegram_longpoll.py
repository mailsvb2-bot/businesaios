"""BusinesAIOS Telegram transport entrypoint.

DecisionCore.issue(WorldState) is the only decision source.

Telegram is only one transport. Incoming updates are normalized through the
canonical messaging ingress adapter before they reach the runtime decision
gateway. This keeps Telegram, WhatsApp, VK, Max, Slack, Discord, Viber, SMS,
email, and webchat on one WorldState contract instead of creating
channel-specific decision paths.
"""

from __future__ import annotations

import logging
import time
from dataclasses import replace
from typing import Any

from application.business_flows.bot_gateway import SESSION_SOURCE as CUSTOMER_SOURCE
from core.ai.world_state import WorldStateV1
from runtime.boot.env import (
    env_bool,
    env_int,
    env_str,
    mark_telegram_token_source,
    resolve_telegram_bot_token,
)
from runtime.bootstrap import bootstrap as _bootstrap
from runtime.decision_gateway import execute_runtime_decision
from runtime.effects import telegram_method_url
from runtime.integration.managed_bot_updates import SESSION_SOURCE as MANAGED_SOURCE
from runtime.integration.managed_bot_updates import allowed_updates_param, parse_managed_bot_update
from runtime.messaging_ingress import (
    messaging_event_to_world_state,
    telegram_update_to_messaging_event,
)
from runtime.safety import verified_inbound_reply_scope

CANON_RUNTIME_ENTRYPOINT_THIN_SHIM = True
CANON_RUNTIME_ENTRYPOINT_BOOTSTRAP_DELEGATES_TO_SOVEREIGN_BOOTSTRAP = True
CANON_TELEGRAM_ENTRYPOINT_MAIN_CONTRACT = True
CANON_TELEGRAM_ENTRYPOINT_NO_SDK_IMPORTS = True
CANON_TELEGRAM_WEBHOOK_AND_LONGPOLL_SHARED_DECISION_PATH = True
CANON_TELEGRAM_USES_CANONICAL_MESSAGING_INGRESS = True
CANON_TELEGRAM_EXECUTES_ONLY_THROUGH_DECISION_GATEWAY = True

_LOG = logging.getLogger("businesaios.telegram.entrypoint")

def _now_ms() -> int:
    return int(time.time() * 1000)

def _telegram_api_url(token: str, method: str) -> str:
    """Compatibility helper delegating to the sole endpoint owner."""

    return telegram_method_url(token, method)

def _http_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout_s: int = 30,
) -> Any:
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
    event = {"event_type": str(event_type), "timestamp_ms": _now_ms(), "payload": dict(payload or {})}
    for name in ("append", "record", "emit"):
        fn = getattr(event_log, name, None)
        if not callable(fn):
            continue
        try:
            fn(event)
            return
        except (TypeError, ValueError):
            continue
        except Exception:
            _LOG.warning("telegram diagnostic event append failed", exc_info=True)
            return

def _copy_world_state(
    state: WorldStateV1,
    *,
    user: dict[str, Any],
    session: dict[str, Any],
    meta: dict[str, Any],
    timestamp_ms: int,
    product: dict[str, Any] | None = None,
) -> WorldStateV1:
    # Evolve the canonical state without manually cloning every governance field.
    return replace(state, user=user, session=session, meta=meta,
                   product=dict(state.product or {}) if product is None else dict(product),
                   timestamp_ms=int(timestamp_ms or state.timestamp_ms or _now_ms()))

_SCOPE_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")


def _operator_scope_id(name: str) -> str:
    value = env_str(name, "").strip()
    if not value or len(value) > 80 or not value[0].isalnum() or not set(value) <= _SCOPE_ID_CHARS:
        return ""
    return value


def _operator_product_binding(product: dict[str, Any]) -> dict[str, Any]:
    """Trusted operator-only product/business binding; never from chat input."""
    bound = dict(product or {})
    for key, env_name in (("product_id", "PRODUCT_ID"), ("business_id", "BUSINESS_ID")):
        value = _operator_scope_id(env_name)
        if value and not str(bound.get(key) or "").strip():
            bound[key] = value
    return bound


def _configured_telegram_tenant_id() -> str:
    """Reject legacy default routing in strict production."""
    tenant_id = env_str("TENANT_ID", "").strip() or env_str("SMOKE_TENANT_ID", "").strip()
    if not tenant_id or tenant_id == "default":
        from governance.economic_layer_env import is_strict_mode
        if is_strict_mode():
            raise RuntimeError("telegram_production_tenant_id_required")
        return "default"
    return tenant_id

def _world_state_from_update(
    update: dict[str, Any],
    *,
    transport: str = "longpoll",
    customer_route: Any = None,
) -> WorldStateV1:
    event = telegram_update_to_messaging_event(
        update,
        tenant_id=customer_route.tenant_id if customer_route is not None else _configured_telegram_tenant_id(),
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
    callback = update.get("callback_query")
    callback = callback if isinstance(callback, dict) else {}
    session = {
        **dict(state.session or {}),
        "telegram_update_id": event.update_id,
        "telegram_chat_id": event.chat_id,
        "is_callback": bool(callback),
        "callback_data": str(callback.get("data") or "") if callback else "",
        "callback_query_id": str(callback.get("id")) if callback.get("id") is not None else None,
    }
    meta = {
        **dict(state.meta or {}),
        "transport": str(transport or "telegram"),
    }
    if customer_route is None:
        from core.ux.unified_messenger_menu import validated_onboarding_url
        meta["operator_links"] = {
            "onboarding_url": validated_onboarding_url(env_str("CLIENT_ONBOARDING_URL", "")),
        }
    product = dict(state.product or {})
    managed = parse_managed_bot_update(update)
    meta["operator_flags"] = {}
    if managed is None and customer_route is None:
        product = _operator_product_binding(product)
        meta["operator_flags"] = {
            "telegram_checkout": bool(env_bool("TELEGRAM_CHECKOUT_ENABLED", False)),
            "autopilot_execute": bool(env_bool("TELEGRAM_AUTOPILOT_EXECUTE_ENABLED", False)),
            "ads_apply_live": bool(env_bool("TELEGRAM_ADS_APPLY_LIVE_ENABLED", False)),
        }
    if managed is not None:  # Bot API managed_bot update: the creator is the acting user, no chat text
        uid = managed["user_id"]
        user = {**user, "id": uid, "messaging_user_id": uid, "telegram_user_id": uid, "telegram_chat_id": uid}
        session = {**session, "telegram_chat_id": uid, "source": MANAGED_SOURCE, "managed_bot": dict(managed)}
        state = replace(state, user_id=uid)
    elif customer_route is not None:  # update from a tenant's own bot (customer side)
        bot = {"bot_id": customer_route.external_bot_id, "username": customer_route.username,
               "request_id": customer_route.request_id, "tenant_id": customer_route.tenant_id,
               "business": dict(customer_route.business)}  # fmt: skip
        session = {**session, "source": CUSTOMER_SOURCE, "customer_bot": bot}
    return _copy_world_state(state, user=user, session=session, meta=meta,
                             timestamp_ms=timestamp_ms, product=product)

def _validate_startup(token: str) -> None:
    from runtime.effects import classify_startup

    timeout_s = max(1, env_int("TELEGRAM_STARTUP_TIMEOUT_S", 10))
    def check(method: str, payload: dict | None = None) -> dict:
        return _response_payload(_http_json(
            "GET" if payload is None else "POST", _telegram_api_url(token, method),
            payload, timeout_s=timeout_s))

    getme, webhook = check("getMe"), check("getWebhookInfo")
    report = classify_startup(getme, webhook)
    if (not report.ok and report.code == "TELEGRAM_WEBHOOK_ENABLED"
            and env_bool("TELEGRAM_AUTO_DELETE_WEBHOOK", True)):
        check("deleteWebhook", {"drop_pending_updates": env_bool("TELEGRAM_DROP_PENDING_UPDATES_ON_START", False)})
        report = classify_startup(getme, check("getWebhookInfo"))
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
    return start_health_server_in_thread(
        snapshot=snapshot,
        host=host,
        port=port,
    )

def _execute_with_budget_notice(*, core: Any, executor: Any, state: Any) -> Any:
    """After a pre-effect budget denial, explain via the SAME sealed decision path."""
    try:
        return execute_runtime_decision(issuer=core, executor=executor, state=state)
    except Exception as exc:
        if str(exc) != "DECISION_BLOCKED:action_budget_exceeded":
            raise
        return execute_runtime_decision(issuer=core, executor=executor, state=replace(
            state, session={**dict(state.session or {}), "action_budget_denial_notice": True}))


def _execute_update(
    *,
    core: Any,
    executor: Any,
    event_log: Any,
    update: dict[str, Any],
    transport: str,
    read_store: Any = None,
) -> Any:
    started = time.monotonic()
    raw_update_id = update.get("update_id")
    state = _world_state_from_update(update, transport=transport)
    normalized_ms = int((time.monotonic() - started) * 1000)
    if read_store is not None and parse_managed_bot_update(update) is None:
        from interfaces.telegram.read_models.user_bundle import hydrate_world_state_user

        state = hydrate_world_state_user(state, event_store=read_store)
    hydrated_ms = int((time.monotonic() - started) * 1000) - normalized_ms
    session = dict(state.session or {})
    customer_bot = session.get("customer_bot")
    bot_id = str(customer_bot.get("bot_id") or "primary") if isinstance(customer_bot, dict) else "primary"
    chat_id = str(session.get("chat_id") or session.get("messaging_chat_id") or session.get("telegram_chat_id") or "")
    with verified_inbound_reply_scope(
        tenant_id=str(state.tenant_id), channel="telegram", user_id=str(state.user_id),
        update_id=raw_update_id, chat_id=chat_id, bot_id=bot_id,
    ):
        result = _execute_with_budget_notice(core=core, executor=executor, state=state)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    message = update.get("message")
    sent_s = message.get("date") if isinstance(message, dict) else None
    transport_age_ms = max(0, int(time.time() * 1000) - sent_s * 1000) if type(sent_s) is int else None
    if elapsed_ms >= 1500 or (transport_age_ms is not None and transport_age_ms >= 3000):
        _LOG.warning("telegram update slow update_id=%s transport_age_ms=%s normalized_ms=%s hydrated_ms=%s execution_ms=%s total_ms=%s",
                     raw_update_id, transport_age_ms, normalized_ms, hydrated_ms,
                     max(0, elapsed_ms - normalized_ms - hydrated_ms), elapsed_ms)
    _append_event(
        event_log,
        event_type="telegram_update_executed",
        payload={
            "transport": transport,
            "update_id": raw_update_id,
            "decision_id": str(getattr(result, "decision_id", "")),
            "ok": bool(getattr(result, "ok", False)),
            "normalized_ms": normalized_ms,
            "hydrated_ms": hydrated_ms,
            "execution_ms": max(0, elapsed_ms - normalized_ms - hydrated_ms),
            "total_ms": elapsed_ms,
            "transport_age_ms": transport_age_ms,
        },
    )
    return result

def _customer_dispatch(*, core: Any, executor: Any, event_log: Any):
    def dispatch(update: dict[str, Any], route: Any) -> None:
        state = _world_state_from_update(update, transport="customer_bot", customer_route=route)
        session = dict(state.session or {})
        customer_bot = session.get("customer_bot")
        bot_id = str(route.external_bot_id or (customer_bot.get("bot_id") if isinstance(customer_bot, dict) else "") or "primary")
        chat_id = str(session.get("chat_id") or session.get("messaging_chat_id") or session.get("telegram_chat_id") or "")
        with verified_inbound_reply_scope(
            tenant_id=str(state.tenant_id), channel="telegram", user_id=str(state.user_id),
            update_id=update.get("update_id"), chat_id=chat_id, bot_id=bot_id,
        ):
            result = _execute_with_budget_notice(core=core, executor=executor, state=state)
        _append_event(event_log, event_type="customer_bot_update_executed",
                      payload={"bot_id": route.external_bot_id, "update_id": update.get("update_id"),
                               "ok": bool(getattr(result, "ok", False))})  # fmt: skip

    return dispatch


def _run_longpoll(
    *,
    token: str,
    core: Any,
    executor: Any,
    event_log: Any,
    customer_gateway: Any = None,
    read_store: Any = None,
) -> None:
    _validate_startup(token)
    _start_health_if_enabled(event_log)

    poll_timeout_s = max(1, env_int("TELEGRAM_POLL_TIMEOUT_S", 30))
    poll_timeout_s = min(poll_timeout_s, 2) if customer_gateway is not None else poll_timeout_s
    request_timeout_s = max(
        poll_timeout_s + 5,
        env_int("TELEGRAM_REQUEST_TIMEOUT_S", poll_timeout_s + 5),
    )
    idle_sleep_s = max(0, env_int("TELEGRAM_IDLE_SLEEP_MS", 250)) / 1000.0
    from runtime.platform.telegram_inbox import TelegramInbox, TelegramTerminalOutcome
    inbox = TelegramInbox(token)
    offset = inbox.cursor()

    def replay_pending() -> None:
        for update in inbox.due(limit=100):
            update_id = update["update_id"]
            try:
                outcome = _execute_update(core=core, executor=executor, event_log=event_log,
                                          update=update, transport="longpoll", read_store=read_store)
                if not bool(getattr(outcome, "ok", False)):
                    output = getattr(outcome, "output", None)
                    if isinstance(output, dict) and output.get("idempotency_resolution") == "rejected_terminal_failed":
                        # The old effect might have executed. Do not waste 12
                        # automatic retries or falsely acknowledge delivery.
                        raise TelegramTerminalOutcome("telegram_ambiguous_effect_requires_reconciliation")
                    error = str(getattr(outcome, "error", "") or "")
                    from runtime.platform.telegram_inbox import is_terminal_failure

                    refusal = RuntimeError(error)
                    if is_terminal_failure(refusal):
                        raise refusal
                    raise RuntimeError("telegram_update_outcome_unconfirmed")
                inbox.complete(update_id)
            except Exception as exc:
                status = inbox.failed(update_id, exc)
                _LOG.exception("telegram update %s retained in durable inbox status=%s", update_id, status)


    _append_event(
        event_log,
        event_type="telegram_started",
        payload={"mode": "longpoll"},
    )
    _LOG.info("telegram long polling started (durable ingress)")

    # Recover pending work even when Telegram no longer returns old updates.
    backlog = inbox.backlog_counts()
    _LOG.info("telegram inbox recovery started pending=%d dead_letter=%d",
              backlog["pending"], backlog["dead_letter"])
    replay_pending()
    backlog = inbox.backlog_counts()
    _LOG.info("telegram inbox recovery finished pending=%d dead_letter=%d",
              backlog["pending"], backlog["dead_letter"])
    while True:
        try:
            payload: dict[str, Any] = {"timeout": poll_timeout_s}
            if offset is not None:
                payload["offset"] = offset
            payload.update(allowed_updates_param())  # opt-in managed_bot delivery
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
            updates = (
                response.get("result")
                if isinstance(response.get("result"), list)
                else []
            )
            _append_event(
                event_log,
                event_type="telegram_polled",
                payload={"updates": len(updates)},
            )
            # The remote cursor is never advanced until every returned update
            # is durably staged, including those whose execution may fail.
            offset = inbox.stage(updates) if updates else inbox.cursor()
            replay_pending()
            if customer_gateway is not None:
                customer_started = time.monotonic()
                try:
                    customer_gateway.tick()
                except Exception:
                    _LOG.exception("customer bot gateway tick failed")
                if (elapsed_ms := int((time.monotonic() - customer_started) * 1000)) >= 1500:
                    _LOG.warning("telegram customer gateway slow tick_ms=%s", elapsed_ms)
            if not updates and idle_sleep_s > 0:
                time.sleep(idle_sleep_s)
        except KeyboardInterrupt:
            _append_event(
                event_log,
                event_type="telegram_stopped",
                payload={"reason": "keyboard_interrupt"},
            )
            raise
        except Exception as exc:
            _append_event(
                event_log,
                event_type="telegram_poll_error",
                payload={
                    "error": type(exc).__name__,
                    "message": str(exc),
                },
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

def _set_webhook_if_configured(
    *,
    token: str,
    path: str,
    secret_token: str,
) -> None:
    webhook_url = _webhook_public_url(path)
    if not webhook_url:
        return
    payload: dict[str, Any] = {
        "url": webhook_url,
        "drop_pending_updates": env_bool(
            "TELEGRAM_DROP_PENDING_UPDATES_ON_START",
            False,
        ),
    }
    if secret_token:
        payload["secret_token"] = secret_token
    timeout_s = max(1, env_int("TELEGRAM_STARTUP_TIMEOUT_S", 10))
    response = _response_payload(
        _http_json(
            "POST",
            _telegram_api_url(token, "setWebhook"),
            payload,
            timeout_s=timeout_s,
        )
    )
    if not response.get("ok"):
        raise RuntimeError(str(response.get("description") or response))

def _run_webhook(
    *,
    token: str,
    core: Any,
    executor: Any,
    event_log: Any,
    read_store: Any = None,
) -> None:
    from runtime.effects import start_telegram_webhook_server_in_thread
    from runtime.health.server import HealthSnapshot

    host = env_str(
        "TELEGRAM_WEBHOOK_HOST",
        env_str("HEALTH_HOST", "0.0.0.0"),
    )
    port = env_int(
        "TELEGRAM_WEBHOOK_PORT",
        env_int("TELEGRAM_HEALTH_PORT", 8088),
    )
    path = env_str("TELEGRAM_WEBHOOK_PATH", "/telegram-webhook/")
    secret_token = env_str(
        "TELEGRAM_WEBHOOK_SECRET_TOKEN",
        env_str("TELEGRAM_WEBHOOK_SECRET", ""),
    )

    def _on_update(update: dict[str, Any]) -> None:
        _append_event(
            event_log,
            event_type="telegram_webhook_received",
            payload={"update_id": update.get("update_id")},
        )
        _execute_update(
            core=core,
            executor=executor,
            event_log=event_log,
            update=update,
            transport="webhook",
            read_store=read_store,
        )

    snapshot = HealthSnapshot(
        event_log=event_log,
        name="telegram-webhook",
    )
    start_telegram_webhook_server_in_thread(
        host=host,
        port=port,
        path=path,
        on_update=_on_update,
        secret_token=secret_token,
        snapshot=snapshot,
    )
    _set_webhook_if_configured(
        token=token,
        path=path,
        secret_token=secret_token,
    )
    _append_event(
        event_log,
        event_type="telegram_started",
        payload={"mode": "webhook", "port": port, "path": path},
    )
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
    del payment_outbox, stack, learning_job

    token = resolve_telegram_bot_token()
    if not token:
        raise RuntimeError(
            "telegram_token_missing_for_longpoll"
        )

    if env_bool("TELEGRAM_USE_WEBHOOK", False) or env_bool(
        "TELEGRAM_WEBHOOK_ENABLED",
        False,
    ):
        _run_webhook(
            token=token,
            core=core,
            executor=executor,
            event_log=event_log,
            read_store=event_store if event_store is not None else event_log,
        )
        return
    import os

    from runtime.integration.customer_bot_gateway import build_customer_bot_gateway

    gateway = build_customer_bot_gateway(
        event_store=event_store,
        tenant_id=_configured_telegram_tenant_id(),
        dispatch=_customer_dispatch(core=core, executor=executor, event_log=event_log),
        env=dict(os.environ),
    )
    _run_longpoll(
        token=token,
        core=core,
        executor=executor,
        event_log=event_log,
        customer_gateway=gateway,
        read_store=event_store if event_store is not None else event_log,
    )


__all__ = [
    "CANON_RUNTIME_ENTRYPOINT_BOOTSTRAP_DELEGATES_TO_SOVEREIGN_BOOTSTRAP",
    "CANON_RUNTIME_ENTRYPOINT_THIN_SHIM",
    "CANON_TELEGRAM_ENTRYPOINT_MAIN_CONTRACT",
    "CANON_TELEGRAM_ENTRYPOINT_NO_SDK_IMPORTS",
    "CANON_TELEGRAM_WEBHOOK_AND_LONGPOLL_SHARED_DECISION_PATH",
    "CANON_TELEGRAM_USES_CANONICAL_MESSAGING_INGRESS",
    "CANON_TELEGRAM_EXECUTES_ONLY_THROUGH_DECISION_GATEWAY",
    "WorldStateV1",
    "build_system",
    "run_telegram",
    "runtime_bootstrap",
]
