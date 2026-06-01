from __future__ import annotations

from typing import Any

from runtime._internal.effects_actions.telegram.runtime_mode import is_telegram_mode
from runtime._internal.effects_clients.http_client import http_json
from runtime._internal.effects_clients.telegram_startup import classify_startup
from runtime._internal.http_transport import HttpTransport
from runtime.observability.error_handling import swallow
from runtime.platform.config.env_flags import env_bool, env_str


def _telegram_api_base() -> str:
    return env_str("TELEGRAM_API_BASE", "https://api.telegram.org").strip().rstrip("/")


def _get_json(url: str, *, timeout_s: int, transport: HttpTransport | None = None) -> dict | None:
    try:
        return http_json(
            "GET",
            str(url),
            None,
            headers={"Content-Type": "application/json"},
            timeout_s=int(timeout_s),
            transport=transport,
        )
    except Exception:
        return None


def _delete_webhook_fix_hint() -> str:
    return (
        " | FIX (Windows CMD): python -c \"import os,requests; "
        "t=os.environ['TELEGRAM_BOT_TOKEN']; assert t; "
        "env=os.environ; "
        "base=env.get('TELEGRAM_API_BASE','https://api.telegram.org'); "
        "print(requests.get(f'{base}/bot{t}/deleteWebhook', params={'drop_pending_updates': True}, timeout=20).text)\""
    )


def poll_telegram_updates_effect(
    effects: Any,
    *,
    offset: int | None = None,
    timeout_s: int = 30,
    limit: int = 50,
) -> Any:
    if not is_telegram_mode():
        return {
            "ok": True,
            "updates": [],
            "mode": "stub",
            "reason": "RUN_MODE!=telegram",
            "meta": {"mode": "stub", "reason": "RUN_MODE!=telegram"},
        }

    token = env_str("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return {
            "ok": False,
            "updates": [],
            "error": "TELEGRAM_BOT_TOKEN_MISSING: set TELEGRAM_BOT_TOKEN in .env or environment",
            "meta": {"mode": "error", "reason": "missing TELEGRAM_BOT_TOKEN"},
        }

    token = str(token).strip()
    if token.startswith("<") and token.endswith(">"):
        token = token[1:-1].strip()
    token = token.strip("\"'")

    api_base = _telegram_api_base()
    transport = getattr(effects, "http_transport", None)
    if not getattr(effects, "_telegram_startup_checked", False):
        effects._telegram_startup_checked = True
        getme = _get_json(f"{api_base}/bot{token}/getMe", timeout_s=10, transport=transport)
        webhook = _get_json(f"{api_base}/bot{token}/getWebhookInfo", timeout_s=10, transport=transport)

        try:
            if isinstance(getme, dict) and bool(getme.get("ok")):
                res = getme.get("result") if isinstance(getme.get("result"), dict) else {}
                username = str((res or {}).get("username") or "").strip().lstrip("@")
                if username:
                    import os
                    os.environ.setdefault("BOT_USERNAME", username)
                    os.environ.setdefault("PUBLIC_BOT_USERNAME", username)
        except Exception:
            swallow(__name__, "runtime/_internal/_effects_impl.py")

        try:
            report = classify_startup(
                getme if isinstance(getme, dict) else None,
                webhook if isinstance(webhook, dict) else None,
            )
        except Exception:
            report = None

        if report is not None and not report.ok:
            auto_clear = env_bool("TELEGRAM_AUTO_CLEAR_WEBHOOK", False)
            if report.code == "TELEGRAM_WEBHOOK_ENABLED" and auto_clear and not bool(getattr(effects, "_telegram_webhook_cleared", False)):
                _ = http_json(
                    "GET",
                    f"{api_base}/bot{token}/deleteWebhook",
                    {"drop_pending_updates": "true"},
                    headers={"Content-Type": "application/json"},
                    timeout_s=2,
                    transport=transport,
                )
                effects._telegram_webhook_cleared = True
            else:
                hint = _delete_webhook_fix_hint() if report.code == "TELEGRAM_WEBHOOK_ENABLED" else ""
                return {
                    "ok": False,
                    "updates": [],
                    "error": f"{report.code}: {report.hint}{hint}",
                    "meta": {"mode": "error", "reason": report.code},
                }

    params: dict[str, int] = {"timeout": int(timeout_s), "limit": int(limit)}
    if offset is not None:
        params["offset"] = int(offset)
    try:
        data = http_json(
            "GET",
            f"{api_base}/bot{token}/getUpdates",
            params,
            headers={"Content-Type": "application/json"},
            timeout_s=int(timeout_s) + 10,
            transport=transport,
        )
    except Exception as exc:
        return {
            "ok": False,
            "updates": [],
            "error": f"TELEGRAM_POLL_FAILED: {exc.__class__.__name__}",
            "meta": {"mode": "error", "reason": "poll_failed"},
        }

    if not isinstance(data, dict) or not data.get("ok"):
        return {
            "ok": False,
            "updates": [],
            "error": str((data or {}).get("description") or "telegram poll failed"),
            "meta": {"mode": "error", "reason": "telegram_not_ok"},
        }

    updates = data.get("result") or []
    if not isinstance(updates, list):
        updates = []
    return {"ok": True, "updates": updates, "meta": {"mode": "telegram"}}
