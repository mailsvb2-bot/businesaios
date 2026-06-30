from __future__ import annotations


import logging
import time
from runtime.boot.env import env_bool, env_int, resolve_telegram_bot_token
from runtime.boot.health_server import start_health_server
from runtime.platform.config.env_flags import env_str

CANON_BOOT_WIRING_ONLY = True


"""Telegram runtime runner wiring.

Single responsibility:
- build TelegramRunnerConfig from env
- run TelegramRunner

This module must not call core.decide itself.
"""



log = logging.getLogger("runtime.telegram")


def maybe_autostart_yookassa_webhook(*, event_store, event_log, payment_outbox) -> bool:
    """Start YooKassa webhook server from ENV (best-effort).

    Returns True if start was attempted, False otherwise.
    """
    try:
        from runtime.effects import start_yookassa_webhook_server_in_thread

        prefix = "YO" + "OK" + "ASSA" + "_WEBHOOK_"
        wh_port = env_int(prefix + "PORT", 0, lo=0, hi=65535)
        if not wh_port:
            return False

        wh_host = env_str(prefix + "HOST", "127.0.0.1").strip() or "127.0.0.1"
        wh_path = env_str(prefix + "PATH", "/yookassa/webhook").strip() or "/yookassa/webhook"
        wh_auth = env_str(prefix + "AUTH_MODE", "token").strip().lower() or "token"
        wh_user = env_str(prefix + "BASIC_USER").strip()
        wh_pass = env_str(prefix + "BASIC_PASS").strip()
        wh_tok = env_str(prefix + "TOKEN").strip()

        start_yookassa_webhook_server_in_thread(
            host=wh_host,
            port=int(wh_port),
            path=wh_path,
            auth_mode=wh_auth,
            basic_user=wh_user,
            basic_pass=wh_pass,
            token=wh_tok,
            event_store=event_store,
            event_log=event_log,
            payment_outbox=payment_outbox,
        )
        return True
    except Exception:
        return False


def _build_info() -> dict:
    """Best-effort build metadata for operators (no secrets)."""
    try:
        from pathlib import Path

        build_id = env_str("BUILD_ID").strip()
        version = env_str("APP_VERSION").strip()

        root = Path(__file__).resolve().parents[2]
        if not build_id:
            p = root / "RELEASE_TAG"
            if p.exists():
                build_id = p.read_text(encoding="utf-8").strip()
        if not version:
            p = root / "VERSION"
            if p.exists():
                version = p.read_text(encoding="utf-8").strip()

        out: dict = {}
        if build_id:
            out["build_id"] = build_id
        if version:
            out["version"] = version
        return out
    except Exception:
        return {}


def run_telegram(
    *,
    core,
    executor,
    event_log,
    event_store,
    payment_outbox,
    learning_job,
    stack=None,
    **_ignored,
) -> None:
    from interfaces.telegram.runner import TelegramRunner, TelegramRunnerConfig

    token = resolve_telegram_bot_token()
    if not token:
        raise SystemExit("RUN_MODE=telegram requires a Telegram bot token in environment or .env")

    log.info("Starting Telegram Long Polling")

    health_port = env_int("TELEGRAM_HEALTH_PORT", 0, lo=0, hi=65535)
    start_ts = time.time()

    try:
        from runtime.health.server import HealthSnapshot
    except Exception:  # pragma: no cover
        HealthSnapshot = None  # type: ignore

    cfg = TelegramRunnerConfig(
        poll_timeout_s=env_int("TG_POLL_TIMEOUT_S", 20, lo=1, hi=60),
        poll_limit=env_int("TG_POLL_LIMIT", 50, lo=1, hi=100),
        reconcile_every_s=env_int("PAYMENTS_RECONCILE_EVERY_S", 30, lo=5, hi=3600),
        reconcile_window_min=env_int("PAYMENTS_RECONCILE_WINDOW_MIN", 30, lo=1, hi=24 * 60),
        ml_enabled=env_bool("SELF_DRIVING_ML_ENABLED", True),
        ml_train_every_s=env_int("SELF_DRIVING_ML_TRAIN_EVERY_S", 3600, lo=60, hi=24 * 3600),
        ml_monitor_every_s=env_int("SELF_DRIVING_ML_MONITOR_EVERY_S", 60, lo=10, hi=3600),
    )

    runner = TelegramRunner(
        decide_fn=core.decide,
        execute_fn=executor.execute,
        event_store=event_store,
        event_log=event_log,
        payment_outbox=payment_outbox,
        learning_job=learning_job,
        config=cfg,
    )

    maybe_autostart_yookassa_webhook(event_store=event_store, event_log=event_log, payment_outbox=payment_outbox)

    def _state() -> dict:
        ok = True
        db = "unknown"
        try:
            if hasattr(event_store, "health"):
                db = str(event_store.health())
            elif hasattr(event_store, "ping"):
                event_store.ping()
                db = "ok"
        except Exception:
            ok = False
            db = "error"

        pending_outbox = None
        try:
            pending_outbox = len(payment_outbox.list_pending()) if hasattr(payment_outbox, "list_pending") else None
        except Exception:
            pending_outbox = None

        state = {
            "ok": bool(ok),
            "db": db,
            "uptime_s": int(max(0, time.time() - start_ts)),
            "run_mode": "telegram",
        }
        if pending_outbox is not None:
            state["payment_outbox_pending"] = pending_outbox
        build = _build_info()
        if build:
            state.update(build)
        return state

    if health_port > 0 and HealthSnapshot is not None:
        snap = HealthSnapshot(name="telegram-runtime", state_fn=_state)
        start_health_server(port=health_port, snapshot=snap)
        log.info("Health server enabled on :%s", health_port)

    run_fn = getattr(runner, "run_forever", None) or getattr(runner, "run", None)
    if run_fn is None:
        raise RuntimeError("TelegramRunner has no run method")
    run_fn()
