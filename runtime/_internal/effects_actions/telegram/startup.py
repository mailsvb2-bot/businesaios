from __future__ import annotations

import logging
import sys

from runtime._internal.effects_clients.http_client import http_json as _http_json
from runtime._internal.effects_clients.telegram_endpoint import (
    delete_webhook_fix_hint,
    telegram_method_url,
)
from runtime._internal.effects_clients.telegram_startup import classify_startup
from runtime.observability.error_handling import swallow
from runtime.platform.config.env_flags import env_str


def telegram_self_check_effect(self, *, token: str | None = None) -> dict:
    t = (token or env_str("TELEGRAM_BOT_TOKEN", "")).strip()
    if not t:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN_MISSING: set TELEGRAM_BOT_TOKEN "
            "in .env or environment"
        )

    transport = getattr(self, "http_transport", None)
    getme = _http_json(
        "GET",
        telegram_method_url(t, "getMe"),
        None,
        timeout_s=20,
        transport=transport,
    )
    webhook = _http_json(
        "GET",
        telegram_method_url(t, "getWebhookInfo"),
        None,
        timeout_s=20,
        transport=transport,
    )
    report = classify_startup(
        getme if isinstance(getme, dict) else None,
        webhook if isinstance(webhook, dict) else None,
    )
    if not report.ok:
        msg = f"{report.code}: {report.hint}"
        if report.code == "TELEGRAM_WEBHOOK_ENABLED":
            msg += delete_webhook_fix_hint()
        raise RuntimeError(msg)

    if not self._telegram_startup_checked:
        source = env_str("TELEGRAM_TOKEN_SOURCE", "unknown").strip() or "unknown"
        line = (
            f"[telegram] OK: token valid (source={source}), "
            "webhook off, polling ready"
        )
        try:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
        except Exception:
            swallow(__name__, "runtime/_internal/_effects_impl.py")
        logging.getLogger(__name__).info(line)
        self._telegram_startup_checked = True
    self._telegram_me = report.getme
    return {
        "ok": True,
        "code": "OK",
        "bot": (report.getme or {}).get("result"),
        "webhook": (
            (report.webhook or {}).get("result")
            if isinstance(report.webhook, dict)
            else report.webhook
        ),
    }
