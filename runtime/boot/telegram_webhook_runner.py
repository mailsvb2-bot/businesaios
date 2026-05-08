from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI, Header, HTTPException, Request

from config.runtime_environment import load_telegram_settings
from config.validation import validate_telegram_settings
from interfaces.telegram.runner import TelegramRunnerConfig
from interfaces.telegram.webhook_runtime import TelegramWebhookConfig, TelegramWebhookRuntime
from runtime.boot.env import env_bool, env_int, resolve_telegram_bot_token
from runtime.platform.config.env_flags import env_str

log = logging.getLogger('runtime.telegram_webhook')


def _build_runner_config() -> TelegramRunnerConfig:
    return TelegramRunnerConfig(
        poll_timeout_s=env_int('TG_POLL_TIMEOUT_S', 20, lo=1, hi=60),
        poll_limit=env_int('TG_POLL_LIMIT', 50, lo=1, hi=100),
        reconcile_every_s=env_int('PAYMENTS_RECONCILE_EVERY_S', 30, lo=5, hi=3600),
        reconcile_window_min=env_int('PAYMENTS_RECONCILE_WINDOW_MIN', 30, lo=1, hi=24 * 60),
        ml_enabled=env_bool('SELF_DRIVING_ML_ENABLED', True),
        ml_train_every_s=env_int('SELF_DRIVING_ML_TRAIN_EVERY_S', 3600, lo=60, hi=24 * 3600),
        ml_monitor_every_s=env_int('SELF_DRIVING_ML_MONITOR_EVERY_S', 60, lo=10, hi=3600),
    )


def _register_webhook(settings, *, token: str) -> None:
    if not settings.webhook_enabled or not settings.webhook_auto_register:
        return
    from runtime._internal.effect_router import EffectRouter

    router = EffectRouter()
    result = router.telegram_set_webhook(
        token=token,
        url=settings.webhook_url,
        secret_token=settings.webhook_secret,
        drop_pending_updates=settings.webhook_drop_pending_updates,
        max_connections=settings.webhook_max_connections,
        allowed_updates=settings.webhook_allowed_updates,
    )
    if not bool((result or {}).get('ok')):
        raise RuntimeError(f"telegram webhook registration failed: {result}")
    log.info('Telegram webhook registered url=%s path=%s', settings.webhook_url, settings.webhook_path)


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
        raise RuntimeError('telegram_token_missing')
    webhook_runtime = TelegramWebhookRuntime(
        decide_fn=core.decide,
        execute_fn=executor.execute,
        event_store=event_store,
        event_log=event_log,
        payment_outbox=payment_outbox,
        learning_job=learning_job,
        runner_config=_build_runner_config(),
        webhook_config=TelegramWebhookConfig(
            secret_token=settings.webhook_secret,
            webhook_path=settings.webhook_path,
            periodic_tick_interval_s=float(env_str('TELEGRAM_WEBHOOK_TICK_INTERVAL_S', '1.0') or '1.0'),
        ),
    )
    _register_webhook(settings, token=token)
    return webhook_runtime


def create_telegram_webhook_app(
    *,
    core: Any,
    executor: Any,
    event_store: Any,
    event_log: Any,
    payment_outbox: Any,
    learning_job: Any,
) -> FastAPI:
    settings = validate_telegram_settings(load_telegram_settings())
    runtime = _build_webhook_runtime(
        core=core,
        executor=executor,
        event_store=event_store,
        event_log=event_log,
        payment_outbox=payment_outbox,
        learning_job=learning_job,
    )
    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        runtime.start()
        try:
            yield
        finally:
            runtime.shutdown()

    app = FastAPI(title='BusinesAIOS Telegram Webhook', version='1.0.0', lifespan=_lifespan)
    app.state.telegram_webhook_runtime = runtime

    router = APIRouter()

    @router.get('/health')
    async def health() -> dict[str, Any]:
        return {'ok': True, 'run_mode': 'telegram_webhook', **runtime.health_snapshot()}

    @router.post(runtime.webhook_path)
    async def telegram_webhook(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        header_token = str(x_telegram_bot_api_secret_token or '').strip()
        if header_token != runtime.secret_token:
            raise HTTPException(status_code=401, detail='invalid telegram webhook secret token')
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail='telegram update must be a JSON object')
        runtime.process_update(payload)
        return {'ok': True}

    app.include_router(router)
    return app


def run_telegram_webhook(
    *,
    core: Any,
    executor: Any,
    event_log: Any,
    event_store: Any,
    payment_outbox: Any,
    learning_job: Any,
    stack: Any = None,
    **_ignored: Any,
) -> None:
    try:
        import uvicorn
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f'uvicorn_required_for_telegram_webhook:{type(exc).__name__}:{exc}') from exc

    settings = validate_telegram_settings(load_telegram_settings())
    app = create_telegram_webhook_app(
        core=core,
        executor=executor,
        event_store=event_store,
        event_log=event_log,
        payment_outbox=payment_outbox,
        learning_job=learning_job,
    )
    uvicorn.run(app, host=settings.webhook_listen_host, port=int(settings.webhook_listen_port))


__all__ = ['create_telegram_webhook_app', 'run_telegram_webhook']
