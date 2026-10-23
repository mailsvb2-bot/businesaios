from __future__ import annotations

import json
from typing import Any

from runtime._internal.effects_actions.telegram.runtime_mode import is_telegram_mode
from runtime._internal.effects_clients.http_client import http_json
from runtime._internal.effects_clients.telegram_endpoint import (
    delete_webhook_fix_hint,
    telegram_method_url,
)
from runtime._internal.effects_clients.telegram_startup import classify_startup
from runtime._internal.http_transport import HttpTransport
from runtime.integration.managed_bot_updates import allowed_updates_param
from runtime.observability.error_handling import swallow
from runtime.platform.config.env_flags import env_bool, env_str


def _get_json(
    url: str,
    *,
    timeout_s: int,
    transport: HttpTransport | None = None,
) -> dict | None:
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


def poll_telegram_updates_effect(
    effects: Any,
    *,
    offset: int | None = None,
    timeout_s: int = 30,
    limit: int = 50,
    token: str | None = None,
    allowed_updates: list[str] | None = None,
) -> Any:
    """getUpdates for the platform bot, or for a tenant bot when ``token`` is given.

    Tenant bots skip the platform startup checks (their webhook was removed at verification)."""
    if not is_telegram_mode():
        return {
            "ok": True,
            "updates": [],
            "mode": "stub",
            "reason": "RUN_MODE!=telegram",
            "meta": {"mode": "stub", "reason": "RUN_MODE!=telegram"},
        }

    tenant = bool(str(token or "").strip())
    token = str(token).strip() if tenant else env_str("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return {
            "ok": False,
            "updates": [],
            "error": (
                "TELEGRAM_BOT_TOKEN_MISSING: set TELEGRAM_BOT_TOKEN "
                "in .env or environment"
            ),
            "meta": {"mode": "error", "reason": "missing TELEGRAM_BOT_TOKEN"},
        }

    token = str(token).strip()
    if token.startswith("<") and token.endswith(">"):
        token = token[1:-1].strip()
    token = token.strip("\"'")

    transport = getattr(effects, "http_transport", None)
    if not tenant and not getattr(effects, "_telegram_startup_checked", False):
        effects._telegram_startup_checked = True
        getme = _get_json(
            telegram_method_url(token, "getMe"),
            timeout_s=10,
            transport=transport,
        )
        webhook = _get_json(
            telegram_method_url(token, "getWebhookInfo"),
            timeout_s=10,
            transport=transport,
        )

        try:
            if isinstance(getme, dict) and bool(getme.get("ok")):
                res = (
                    getme.get("result")
                    if isinstance(getme.get("result"), dict)
                    else {}
                )
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
            if (
                report.code == "TELEGRAM_WEBHOOK_ENABLED"
                and auto_clear
                and not bool(
                    getattr(effects, "_telegram_webhook_cleared", False)
                )
            ):
                _ = http_json(
                    "GET",
                    telegram_method_url(token, "deleteWebhook"),
                    {"drop_pending_updates": "true"},
                    headers={"Content-Type": "application/json"},
                    timeout_s=2,
                    transport=transport,
                )
                effects._telegram_webhook_cleared = True
            else:
                hint = (
                    delete_webhook_fix_hint()
                    if report.code == "TELEGRAM_WEBHOOK_ENABLED"
                    else ""
                )
                return {
                    "ok": False,
                    "updates": [],
                    "error": f"{report.code}: {report.hint}{hint}",
                    "meta": {"mode": "error", "reason": report.code},
                }

    params: dict[str, Any] = {
        "timeout": int(timeout_s),
        "limit": int(limit),
    }
    if offset is not None:
        params["offset"] = int(offset)
    if allowed_updates is not None:
        params["allowed_updates"] = json.dumps([str(u) for u in allowed_updates])
    else:
        params.update(allowed_updates_param(tenant=tenant))

    try:
        data = http_json(
            "GET",
            telegram_method_url(token, "getUpdates"),
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
            "error": str(
                (data or {}).get("description") or "telegram poll failed"
            ),
            "meta": {"mode": "error", "reason": "telegram_not_ok"},
        }

    updates = data.get("result") or []
    if not isinstance(updates, list):
        updates = []
    return {"ok": True, "updates": updates, "meta": {"mode": "telegram"}}



def managed_bot_token_effect(effects: Any, *, managed_bot_id: str) -> dict:
    """Bot API ``getManagedBotToken`` called with the platform (manager) bot token.

    Returns {"ok", "token"} or {"ok": False, "error"}; the caller seals the token, never logs it."""
    bid = str(managed_bot_id or "").strip()
    if not bid.isdigit():
        return {"ok": False, "error": "managed_bot_id_invalid"}
    if not is_telegram_mode():
        return {"ok": False, "error": "telegram_mode_disabled"}
    manager = env_str("TELEGRAM_BOT_TOKEN", "").strip()
    if not manager:
        return {"ok": False, "error": "manager_token_missing"}
    try:
        data = http_json(
            "GET",
            telegram_method_url(manager, "getManagedBotToken"),
            {"user_id": bid},
            headers={"Content-Type": "application/json"},
            timeout_s=20,
            transport=getattr(effects, "http_transport", None),
        )
    except Exception as exc:
        return {"ok": False, "error": f"managed_bot_token_failed:{exc.__class__.__name__}"}
    result = data.get("result") if isinstance(data, dict) and data.get("ok") else None
    if not isinstance(result, str) or not result.strip():
        return {"ok": False, "error": "managed_bot_token_unavailable"}
    return {"ok": True, "token": result.strip()}
