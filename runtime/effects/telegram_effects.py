from __future__ import annotations

"""Telegram effect helpers.

NOTE: External I/O MUST remain sealed inside runtime/_internal/_effects_impl.py.
This module contains only pure helpers and thin orchestration.
"""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class TelegramStartupReport:
    ok: bool
    code: str
    hint: str
    getme: Dict[str, Any] | None = None
    webhook: Dict[str, Any] | None = None


def classify_startup(getme: Dict[str, Any] | None, webhook: Dict[str, Any] | None) -> TelegramStartupReport:
    """Classify Telegram startup state from getMe + getWebhookInfo responses.

    Pure function. Must not embed network markers or tokens.
    """
    if not getme:
        return TelegramStartupReport(False, "TELEGRAM_TOKEN_CHECK_FAILED", "Could not validate token (no response).")

    if not getme.get("ok"):
        desc = str(getme.get("description") or "")
        hint = "Check that bot token is correct (BotFather)."
        if "Not Found" in desc or getme.get("error_code") in (404,):
            hint = "Token is invalid (404 Not Found). Paste the real token (not placeholders) and consider /revoke in BotFather if leaked."
        if getme.get("error_code") in (401,):
            hint = "Token is unauthorized (401). Verify token in BotFather."
        return TelegramStartupReport(False, "TELEGRAM_TOKEN_INVALID", hint, getme=getme, webhook=webhook)

    if webhook and webhook.get("ok") and webhook.get("result") and webhook["result"].get("url"):
        url = webhook["result"].get("url")
        return TelegramStartupReport(
            False,
            "TELEGRAM_WEBHOOK_ENABLED",
            f"Webhook is enabled; long polling will get no updates. Disable it: deleteWebhook(drop_pending_updates=true). url={url}",
            getme=getme,
            webhook=webhook,
        )

    return TelegramStartupReport(True, "OK", "", getme=getme, webhook=webhook)
