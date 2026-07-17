from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI, Header, HTTPException, Request

from config.runtime_environment import load_telegram_settings
from config.validation import validate_telegram_settings
from interfaces.telegram.runner import TelegramRunnerConfig
from interfaces.telegram.webhook_runtime import (
    TelegramWebhookConfig,
    TelegramWebhookRuntime,
)
from runtime.boot.env import env_bool, env_int, resolve_telegram_bot_token
from runtime.decision_gateway import build_runtime_decision_callable
from runtime.handler_loader import import_internal_attr

log = logging.getLogger("runtime.telegram_webhook")

CANON_BOOT_WIRING_ONLY = True


def _load_internal_attr(module_name: str, attr_name: str) -> Any:
    return import_internal_attr(module_name, attr_name)


def _build_runner_config() -> TelegramRunnerConfig:
    return TelegramRunnerConfig(
        poll_timeout_s=env_int("TG_POLL_TIMEOUT_S", 20, lo=1, hi=60),
        poll_limit=env_int("TG_POLL_LIMIT", 50, lo=1, hi=100),
        reconcile_every_s=env_int(
            "PAYMENTS_RECONCILE_EVERY_S",
            30,
            lo=5,
            hi=3600,
        ),
        reconcile_window_min=env_int(
            "PAYMENTS_RECONCILE_WINDOW_MIN",
            30,
            lo=1,
            hi=24 * 60,
        ),
        ml_enabled=env_bool("SELF_DRIVING_ML_ENABLED", True),
        ml_train_every_s=env_int(
            "SELF_DRIVING_ML_TRAIN_EVERY_S",
            3600,
            lo=60,
            hi=24 * 3600,
        ),
        ml_monitor_every_s=env_int(
            "SELF_DRIVING_ML_MONITOR_EVERY_S",
            60,
            lo=10,
            hi=3600,
        ),
    )


def _register_webhook(settings, *, token: str) -> None:
    if not settings.webhook_enabled or not settings.webhook_auto_register:
        return
    effect_router_type = _load_internal_attr(
        "runtime._internal.effect_router",
        "EffectRouter",
    )
    router = effect_router_type()
    result = router.telegram_set_webhook(
        token=token,
        url=settings.webhook_url,
        secret_token=settings.webhook_secret,
        drop_pending_updates=settings.webhook_drop_pending_updates,
        max_connections=settings.webhook_max_connections,
        allowed_updates=settings.webhook_allowed_updates,
    )
    if not bool((result or {}).get("ok")):
        raise RuntimeError(
            f"telegram webhook registration failed: {result}"
        )
    log.info(
        "Telegram webhook registered url=%s path=%s",
        settings.webhook_url,
        settings.webhook_path,
    )


def _build_webhook_runtime(
    *,
    core: Any,
    executor: Any,
    event_store: Any,
    event_log: Any,
    payment_outbox: Any,
    learning_job: Any,
) -> TelegramWebhookRuntime:
    settings = validate_telegram_settings(load_telegram_settings())
    token = resolve_telegram_bot_token()
    if not token:
        raise RuntimeError("telegram_token_missing")
    webhook_runtime = TelegramWebhookRuntime(
        decide_fn=build_runtime_decision_callable(issuer=core),
        execute_fn=executor.execute,
        event_store=event_store,
        event_log=event_log,
        payment_outbox=payment_outbox,
        learning_job=learning_job,
        runner_config=_build_runner_config(),
        webhook_config=TelegramWebhookConfig(
            secret_token=settings.webhook_secret,
            webhook_path=settings.webhook_path,
        ),
    )
    _register_webhook(settings, token=token)
    return webhook_runtime


def build_telegram_webhook_app(
    *,
    core: Any,
    executor: Any,
    event_store: Any,
    event_log: Any,
    payment_outbox: Any,
    learning_job: Any,
) -> FastAPI:
    runtime = _build_webhook_runtime(
        core=core,
        executor=executor,
        event_store=event_store,
        event_log=event_log,
        payment_outbox=payment_outbox,
        learning_job=learning_job,
    )
    router = APIRouter()

    @router.get("/health")
    async def health():
        return {"status": "ok", "transport": "telegram_webhook"}

    @router.post(runtime.webhook_path)
    async def telegram_webhook(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ):
        expected = str(runtime.secret_token or "").strip()
        if (
            expected
            and x_telegram_bot_api_secret_token != expected
        ):
            raise HTTPException(
                status_code=401,
                detail="invalid webhook secret",
            )
        payload = await request.json()
        runtime.process_update(payload)
        return {"ok": True}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        del app
        runtime.start()
        try:
            yield
        finally:
            runtime.shutdown()

    app = FastAPI(lifespan=lifespan)
    app.include_router(router)
    return app


def create_telegram_webhook_app(
    *,
    core: Any,
    executor: Any,
    event_store: Any,
    event_log: Any,
    payment_outbox: Any,
    learning_job: Any,
) -> FastAPI:
    """Compatibility factory kept on the canonical webhook path."""

    return build_telegram_webhook_app(
        core=core,
        executor=executor,
        event_store=event_store,
        event_log=event_log,
        payment_outbox=payment_outbox,
        learning_job=learning_job,
    )


__all__ = [
    "build_telegram_webhook_app",
    "create_telegram_webhook_app",
]
