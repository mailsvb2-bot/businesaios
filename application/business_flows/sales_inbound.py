"""Inbound customer message -> sales evidence (port of ClientPlatform sales_intelligence).

Pure: builds sales_pipeline@v1 facts; never replies. Message text is kept only when the
business allowed sales AI (donor ``business_sales_ai_enabled_in_conn`` gate).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from application.business_flows.projection import stable_id

CANON_SALES_INBOUND = True
MAX_CHARS = 12_000
CHANNELS = ("telegram", "vk", "max")


def normalize_text(value: object) -> str | None:
    t = re.sub(r"\s+", " ", str(value or "").replace("\x00", " ")).strip()
    if not t or t.startswith("/"):
        return None
    return t[:MAX_CHARS].rstrip() or None


def extract_text(update: Mapping[str, Any]) -> str | None:
    """Text (or caption) of a Telegram ``message``/``edited_message``; commands are not evidence."""
    msg = next((update[k] for k in ("message", "edited_message") if isinstance(update.get(k), Mapping)), None)
    if msg is None:
        return None
    raw = msg.get("text")
    return normalize_text(msg.get("caption") if raw is None else raw)


def printable(value: str, *, field_name: str, maximum: int) -> str:
    t = str(value or "").strip()
    if not t or len(t) > maximum:
        raise ValueError(f"{field_name} must be 1..{maximum} characters")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in t):
        raise ValueError(f"{field_name} contains control characters")
    return t


def seen_keys(payloads: list[dict[str, Any]]) -> set[str]:
    return {str(p["dedupe_key"]) for p in payloads if p.get("step") == "lead_inbound"}


def record_message(
    payloads: list[dict[str, Any]],
    *,
    channel: str,
    subject: str,
    name: str,
    source_ref: str,
    event_id: str,
    text: object,
    ai_allowed: bool,
    surface: str = "messenger",
    opportunity_key: str | None = None,
    source_event_key: str | None = None,
) -> dict[str, Any] | None:
    """One ``lead_inbound`` fact: create-or-refresh lead + inbound transition; replays yield None.

    ``sales.replay`` applies it (new lead, DISCOVERED->ENGAGED, stop pending follow-up,
    text note only when ``ai_allowed``).
    """
    if channel not in CHANNELS:
        raise ValueError("sales ingress supports only Telegram, VK or MAX")
    subj = printable(subject, field_name="external_subject", maximum=512)
    src = printable(source_ref, field_name="source_ref", maximum=200)
    eid = printable(event_id, field_name="provider_event_id", maximum=160)
    body = normalize_text(text)
    if body is None:
        raise ValueError("message_text must contain non-command customer text")
    if not isinstance(ai_allowed, bool):
        raise ValueError("runtime_ai_enabled must be a boolean")
    surf = printable(surface, field_name="surface", maximum=80)
    key = source_event_key or f"customer-message:{channel}:{src}:{eid}"
    opp = opportunity_key or f"channel:{channel}:{src}:{subj}"
    for field_name, value in (("opportunity_key", opp), ("source_event_key", key)):
        printable(value, field_name=field_name, maximum=240)
    if key in seen_keys(payloads):
        return None
    fact = {
        "step": "lead_inbound",
        "lead_id": stable_id("lead", opp),
        "surface": surf,
        "name": (str(name or "").strip() or f"Клиент {subj[-6:]}")[:80],
        "source": channel,
        "customer_id": subj,
        "dedupe_key": key,
    }
    if ai_allowed:
        fact["note"] = ("💬 " + body)[:300]
    return fact


def record_managed_bot_message(
    payloads: list[dict[str, Any]],
    *,
    route_business_id: str,
    link_business_id: str,
    managed_bot_id: str,
    telegram_user_id: int,
    update_id: object,
    name: str,
    text: object,
    ai_allowed: bool,
) -> dict[str, Any] | None:
    """Managed-bot Telegram wrapper keeping the donor's durable managed-bot keys."""
    if route_business_id != link_business_id:
        raise ValueError("managed bot route and customer link belong to different businesses")
    if isinstance(telegram_user_id, bool) or not isinstance(telegram_user_id, int) or telegram_user_id <= 0:
        raise ValueError("telegram_user_id must be a positive integer")
    uid = str(update_id or "").strip()
    if not uid.isdigit() or len(uid) > 32:
        raise ValueError("provider_update_id must be a positive decimal identifier")
    bot = printable(managed_bot_id, field_name="managed_bot_id", maximum=64)
    return record_message(
        payloads, channel="telegram", subject=str(telegram_user_id), name=name,
        source_ref=f"managed-bot:{bot}", event_id=uid, text=text, ai_allowed=ai_allowed,
        surface="managed_bot", opportunity_key=f"managed-bot:{bot}:telegram:{telegram_user_id}",
        source_event_key=f"managed-bot-message:{bot}:{uid}",
    )


__all__ = [
    "CANON_SALES_INBOUND", "extract_text", "normalize_text", "printable", "record_managed_bot_message",
    "record_message", "seen_keys",
]
