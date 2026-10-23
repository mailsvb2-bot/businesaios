"""Booking-scoped messenger verification links (donor ``application/event_registration_channels``).

A participant who booked a slot can prove control of one exact Telegram/VK/MAX account for that
booking via ``/start ecv_<token>``. Tokens are random, stored only as sha256 digests in
``bookings@v1`` facts, single-use, platform-bound and expire in 60..3600 s. Pure: the handler
writes the returned facts; nothing here sends or schedules.
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Iterable
from typing import Any

PREFIX = "ecv_"
PLATFORMS = ("telegram", "vk", "max")


class LinkRejected(ValueError):
    """An event-scoped messenger verification token cannot be consumed safely."""


def extract_token(value: object) -> str | None:
    raw = " ".join(str(value or "").strip().split())
    payload = raw
    low = raw.casefold()
    if low.startswith("/start ") or low.startswith("start "):
        payload = raw.split(maxsplit=1)[1].strip()
    if not payload.casefold().startswith(PREFIX):
        return None
    return payload[len(PREFIX) :].strip() or None


def marketing_platforms(values: Iterable[object]) -> frozenset[str]:
    norm = {str(v or "").strip().lower() for v in values if str(v or "").strip()}
    if norm - set(PLATFORMS):
        raise ValueError("unsupported event messenger marketing channel")
    return frozenset(norm)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue(
    slot: Any, *, customer_id: str, marketing: Iterable[object] = (), now_ms: int, ttl_seconds: int = 3600
) -> tuple[dict[str, str], dict[str, Any]]:
    """Return ({platform: token}, fact). Only an active booking of this customer can issue links."""
    wanted = marketing_platforms(marketing)
    if slot is None or slot.status != "booked" or slot.customer_id != customer_id or slot.starts_at_ms <= now_ms:
        raise LinkRejected("booking is not available for messenger verification")
    expires = now_ms + min(max(int(ttl_seconds), 60), 3600) * 1000
    tokens = {p: secrets.token_urlsafe(32) for p in PLATFORMS}
    fact = {
        "step": "channel_links_issued",
        "slot_id": slot.slot_id,
        "customer_id": customer_id,
        "expires_at_ms": expires,
        "links": [{"platform": p, "digest": _digest(t), "marketing": p in wanted} for p, t in tokens.items()],
    }
    return tokens, fact


def channels(payloads: list[dict[str, Any]]) -> dict[tuple[str, str, str], str]:
    """(slot, customer, platform) -> verified external subject."""
    return {
        (str(p["slot_id"]), str(p["customer_id"]), str(p["platform"])): str(p["external_subject"])
        for p in payloads
        if p.get("step") == "channel_verified"
    }


def consume(
    payloads: list[dict[str, Any]], slots: dict[str, Any], *, token: str, platform: str, external_subject: str, now_ms: int
) -> dict[str, Any]:
    raw = str(token or "").strip()
    if not 20 <= len(raw) <= 160:
        raise LinkRejected("event messenger verification token is invalid")
    plat, subject = str(platform or "").strip().lower(), str(external_subject or "").strip()
    if plat not in PLATFORMS or not subject:
        raise LinkRejected("event messenger verification requires Telegram, VK or MAX")
    digest = _digest(raw)
    consumed = {str(p.get("digest")) for p in payloads if p.get("step") == "channel_verified"}
    hit = next(
        ((p, link) for p in payloads if p.get("step") == "channel_links_issued" for link in p.get("links") or []
         if link.get("digest") == digest),
        None,
    )
    if hit is None:
        raise LinkRejected("event messenger verification token was not found")
    issued, link = hit
    slot = slots.get(str(issued["slot_id"]))
    if slot is None or slot.status != "booked" or slot.customer_id != issued["customer_id"]:
        raise LinkRejected("event messenger verification token was not found")
    if link["platform"] != plat:
        raise LinkRejected("event messenger verification token belongs to another platform")
    if digest in consumed:
        raise LinkRejected("event messenger verification token was already consumed")
    if int(issued["expires_at_ms"]) <= now_ms:
        raise LinkRejected("event messenger verification token expired")
    key = (slot.slot_id, str(issued["customer_id"]), plat)
    existing = channels(payloads).get(key)
    if existing is not None and existing != subject:
        raise LinkRejected("this booking is already verified to another messenger account")
    return {
        "step": "channel_verified",
        "slot_id": slot.slot_id,
        "customer_id": issued["customer_id"],
        "platform": plat,
        "external_subject": subject,
        "digest": digest,
        "marketing_consent": bool(link.get("marketing")),
    }


__all__ = ["PLATFORMS", "PREFIX", "LinkRejected", "channels", "consume", "extract_token", "issue", "marketing_platforms"]
