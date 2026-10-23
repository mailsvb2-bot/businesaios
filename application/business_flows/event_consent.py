"""Channel-scoped commercial consent for event follow-ups (port of donor event_commercial_consent).

Registration consent (``public_events.register``) stays separate and mandatory; commercial consent
is optional, versioned and revocable. Evidence lives in append-only ``event_commercial_consent_*``
facts; current channel state is a replay. Revocation emits ``event_dispatch_cancelled`` so the
executor drops not-started commercial dispatches. This module sends nothing.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from application.business_flows import public_events as pe

VERSION = "2026-09-event-commercial-v1"
CHANNELS = ("email", "vk", "max", "telegram")


def normalize_channels(values: Iterable[object]) -> tuple[str, ...]:
    out: list[str] = []
    for raw in values:
        v = str(raw or "").strip().lower()
        if v and v not in CHANNELS:
            raise ValueError("unsupported marketing channel")
        if v and v not in out:
            out.append(v)
    if not out:
        raise ValueError("at least one marketing channel is required")
    return tuple(out)


def advertiser_label(brand_display_name: object, business_name: object) -> str | None:
    label = " ".join(str(brand_display_name or "").split()) or " ".join(str(business_name or "").split())
    return label[:240] or None


def consent_text(label: object) -> str:
    lb = " ".join(str(label or "").split())
    if not lb or len(lb) > 240:
        raise ValueError("advertiser label is unavailable")
    return (
        f"Я согласен получать от «{lb}» информационные и рекламные сообщения "
        "о продуктах, услугах и мероприятиях по выбранным каналам. "
        "Согласие можно отозвать в любой момент по ссылке в сообщении."
    )


def text_sha256(label: object) -> str:
    return hashlib.sha256(consent_text(label).encode("utf-8")).hexdigest()


def active_channels(payloads: list[dict[str, Any]], registration_id: str) -> tuple[str, ...]:
    state: set[str] = set()
    for p in payloads:
        if p.get("registration_id") != registration_id:
            continue
        if p.get("step") == "event_commercial_consent_granted":
            state |= set(p["channels"])
        elif p.get("step") == "event_commercial_consent_revoked":
            state.clear()
    return tuple(sorted(state))


def is_authorized(payloads: list[dict[str, Any]], registration_id: str, platform: str) -> bool:
    return str(platform or "").strip().lower() in active_channels(payloads, registration_id)


def grant(b: pe.Board, *, registration_id: str, channels: Iterable[object], label: str,
          expected_sha256: str | None = None, now: datetime) -> dict[str, Any]:
    chans = normalize_channels(channels)
    r = b.registrations.get(registration_id)
    if r is None or r.status != "registered":
        raise ValueError("event registration is unavailable for commercial consent")
    sha = text_sha256(label)
    if expected_sha256 is not None and str(expected_sha256).strip().lower() != sha:
        raise ValueError("commercial consent text changed; reload the event page")
    return {"step": "event_commercial_consent_granted", "registration_id": r.registration_id,
            "event_id": r.event_id, "channels": list(chans), "advertiser_label": " ".join(label.split()),
            "consent_text_version": VERSION, "consent_text_sha256": sha,
            "occurred_at": pe._dt(now).isoformat()}


def revoke_by_token(b: pe.Board, payloads: list[dict[str, Any]], token: str) -> list[dict[str, Any]]:
    """Revoke all commercial channels; the registration itself stays active."""
    th = pe._h(str(token or "").strip())
    r = next((x for x in b.registrations.values() if x.token_hash == th), None)
    if r is None:
        raise ValueError("event registration token is invalid")
    chans = active_channels(payloads, r.registration_id)
    out: list[dict[str, Any]] = []
    if chans:
        out.append({"step": "event_commercial_consent_revoked", "registration_id": r.registration_id,
                    "channels": list(chans)})
    out.append({"step": "event_dispatch_cancelled", "event_id": r.event_id,
                "registration_ids": [r.registration_id], "reason": "event_commercial_consent_revoked",
                "scope": "commercial"})
    return out
