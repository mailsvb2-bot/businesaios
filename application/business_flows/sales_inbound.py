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
    key = f"customer-message:{channel}:{src}:{eid}"
    if key in seen_keys(payloads):
        return None
    fact = {
        "step": "lead_inbound",
        "lead_id": stable_id("lead", f"channel:{channel}:{src}:{subj}"),
        "name": (str(name or "").strip() or f"Клиент {subj[-6:]}")[:80],
        "source": channel,
        "customer_id": subj,
        "dedupe_key": key,
    }
    if ai_allowed:
        fact["note"] = ("💬 " + body)[:300]
    return fact


__all__ = ["CANON_SALES_INBOUND", "extract_text", "normalize_text", "printable", "record_message", "seen_keys"]
