"""Channel-scoped commercial consent for event follow-ups (port of donor event_commercial_consent).

Registration consent (``public_events.register``) stays separate and mandatory; commercial consent
is optional, versioned and revocable. Evidence lives in append-only ``event_commercial_consent_*``
facts; current channel state is a replay. Revocation emits ``event_dispatch_cancelled`` so the
executor drops not-started commercial dispatches. This module sends nothing.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
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


def grant(
    b: pe.Board,
    *,
    registration_id: str,
    channels: Iterable[object],
    label: str,
    expected_sha256: str | None = None,
    now: datetime,
) -> dict[str, Any]:
    chans = normalize_channels(channels)
    r = b.registrations.get(registration_id)
    if r is None or r.status != "registered":
        raise ValueError("event registration is unavailable for commercial consent")
    sha = text_sha256(label)
    if expected_sha256 is not None and str(expected_sha256).strip().lower() != sha:
        raise ValueError("commercial consent text changed; reload the event page")
    return {
        "step": "event_commercial_consent_granted",
        "registration_id": r.registration_id,
        "event_id": r.event_id,
        "channels": list(chans),
        "advertiser_label": " ".join(label.split()),
        "consent_text_version": VERSION,
        "consent_text_sha256": sha,
        "occurred_at": pe._dt(now).isoformat(),
    }


def revoke_by_token(b: pe.Board, payloads: list[dict[str, Any]], token: str) -> list[dict[str, Any]]:
    """Revoke all commercial channels; the registration itself stays active."""
    th = pe._h(str(token or "").strip())
    r = next((x for x in b.registrations.values() if x.token_hash == th), None)
    if r is None:
        raise ValueError("event registration token is invalid")
    chans = active_channels(payloads, r.registration_id)
    out: list[dict[str, Any]] = []
    if chans:
        out.append(
            {"step": "event_commercial_consent_revoked", "registration_id": r.registration_id, "channels": list(chans)}
        )
    out.append(
        {
            "step": "event_dispatch_cancelled",
            "event_id": r.event_id,
            "registration_ids": [r.registration_id],
            "reason": "event_commercial_consent_revoked",
            "scope": "commercial",
        }
    )
    return out


# --- event funnel analytics & verified-payment linking (donor event_analytics) ---

MARKS = {
    "join_clicked": "pub_registration_join_clicked",
    "attendance_confirmed": "pub_registration_attended",
    "offer_clicked": "pub_registration_offer_clicked",
}


def _rate(n: int, d: int) -> float:
    return 0.0 if d <= 0 else round(n / d, 4)


@dataclass(frozen=True)
class Funnel:
    registered: int
    join_clicked: int
    attendance_confirmed: int
    offer_clicked: int
    paid: int
    revenue: tuple[tuple[str, int], ...]

    @property
    def join_click_rate(self) -> float:
        return _rate(self.join_clicked, self.registered)

    @property
    def confirmed_attendance_rate(self) -> float:
        return _rate(self.attendance_confirmed, self.registered)

    @property
    def registration_to_paid_rate(self) -> float:
        return _rate(self.paid, self.registered)


def mark(registration_id: str, what: str) -> dict[str, Any]:
    if what not in MARKS:
        raise ValueError("unknown funnel mark")
    return {"step": MARKS[what], "registration_id": registration_id}


def funnel(payloads: list[dict[str, Any]], event_id: str) -> Funnel:
    regs = {
        r.registration_id
        for r in pe.replay(payloads).registrations.values()
        if r.event_id == event_id and r.status == "registered"
    }
    seen: dict[str, set[str]] = {k: set() for k in MARKS}
    paid: set[str] = set()
    links: set[tuple[str, str]] = set()
    rev: dict[str, int] = {}
    for p in payloads:
        rid = p.get("registration_id")
        for k, step in MARKS.items():
            if p.get("step") == step and rid in regs:
                seen[k].add(rid)
        if p.get("step") == "event_payment_linked" and p.get("event_id") == event_id:
            if (rid, p["payment_ref"]) in links:
                continue
            links.add((rid, p["payment_ref"]))
            paid.add(rid)
            if p.get("amount_minor") is not None:
                rev[p["currency"]] = rev.get(p["currency"], 0) + int(p["amount_minor"])
    return Funnel(
        len(regs),
        len(seen["join_clicked"]),
        len(seen["attendance_confirmed"]),
        len(seen["offer_clicked"]),
        len(paid),
        tuple(sorted(rev.items())),
    )


def link_verified_payment(
    payloads: list[dict[str, Any]],
    *,
    event_id: str,
    registration_id: str,
    payment_ref: str,
    amount_minor: int | None,
    currency: str | None,
    occurred_at: datetime,
) -> list[dict[str, Any]]:
    ref = str(payment_ref or "").strip()
    if not ref or len(ref) > 512:
        raise ValueError("payment_ref must be 1..512 characters")
    if amount_minor is not None and (
        isinstance(amount_minor, bool) or not isinstance(amount_minor, int) or amount_minor < 0
    ):
        raise ValueError("amount_minor must be a non-negative integer")
    cur = None if currency is None else str(currency).strip().upper()
    if cur is not None and (len(cur) != 3 or not cur.isalpha()):
        raise ValueError("currency must be a three-letter code")
    if amount_minor is not None and cur is None:
        raise ValueError("currency is required when amount is present")
    r = pe.replay(payloads).registrations.get(registration_id)
    if r is None or r.event_id != event_id:
        raise ValueError("event registration does not belong to the supplied business/event")
    dup = any(
        p.get("step") == "event_payment_linked"
        and p.get("registration_id") == registration_id
        and p.get("payment_ref") == ref
        for p in payloads
    )
    out = (
        []
        if dup
        else [
            {
                "step": "event_payment_linked",
                "event_id": event_id,
                "registration_id": registration_id,
                "payment_ref": ref,
                "amount_minor": amount_minor,
                "currency": cur,
                "occurred_at": pe._dt(occurred_at).isoformat(),
            }
        ]
    )
    return [
        *out,
        {
            "step": "event_dispatch_cancelled",
            "event_id": event_id,
            "registration_ids": [registration_id],
            "reason": "event_offer_paid",
            "scope": "commercial",
        },
    ]
