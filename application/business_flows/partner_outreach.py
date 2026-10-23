"""Partner outreach gates (port of donor application/partner_runtime) over ``partners@v1`` facts.

Builds on ``partners.Partner`` and the ``partners.statuses`` pipeline. Pure: it only produces
``partner_contact_authorized``, ``partner_outreach_queued`` and ``partner_reply`` facts, and the
executor's outbox does any real send. Automatic Telegram contact needs opt-in or an existing
relationship. A first email to a public business contact needs an explicit owner approval.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from application.business_flows import partners as pt

_CHAT_ID = re.compile(r"-?[1-9][0-9]{0,19}")
REVOKING = frozenset({"declined", "do_not_contact", "invalid"})
REPLYABLE = frozenset({"contacted", "replied", "agreed"})  # donor accepted == agreed


@dataclass(frozen=True)
class SendConnection:
    id: str
    label: str


@dataclass(frozen=True)
class Reply:
    occurred_at: str
    reply_text: str


def send_connections(connections: list[dict[str, Any]], platform: str = "telegram") -> list[SendConnection]:
    sel = str(platform or "").strip().lower()
    types = {"telegram": {"telegram_shared_bot", "telegram_managed_bot"}, "email": {"email_smtp"}}.get(sel)
    if types is None:
        raise ValueError("partner send platform must be telegram or email")
    prefix, fallback = ("Telegram", "бот") if sel == "telegram" else ("Email", "отправитель")
    rows = sorted(
        (c for c in connections if c.get("platform") == sel and c.get("status") == "active" and c.get("type") in types),
        key=lambda c: (str(c.get("created_at", "")), str(c["id"])),
    )
    return [
        SendConnection(str(c["id"]), f"{prefix} · {str(c.get('external_account_id') or fallback)[:80]}") for c in rows
    ]


def authorize_telegram_contact(partner: pt.Partner | None, status: str, *, chat_id: str, basis: str) -> dict[str, Any]:
    if basis not in {"opted_in", "existing"}:
        raise PermissionError("automatic partner contact requires opt-in or an existing relationship")
    subject = str(chat_id or "").strip()
    if not _CHAT_ID.fullmatch(subject):
        raise ValueError("Telegram chat id must be numeric")
    if partner is None:
        raise ValueError("partner_not_found")
    if partner.competitor or status in REVOKING:
        raise PermissionError("candidate cannot be authorized for outreach")
    return {
        "step": "partner_contact_authorized",
        "partner_id": partner.partner_id,
        "channel": "telegram",
        "contact": subject,
        "basis": basis,
    }


def contacts(payloads: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(p["partner_id"]): p for p in payloads if p.get("step") == "partner_contact_authorized"}


def queue_outreach(
    partner: pt.Partner,
    status: str,
    *,
    contact: dict[str, Any] | None,
    connection_id: str,
    explicit_owner_approval: bool = False,
) -> dict[str, Any]:
    """Proposal for the executor's outbox, never sent here."""
    if partner.competitor or status in REVOKING:
        raise PermissionError("candidate cannot be contacted")
    if contact is not None and contact["basis"] in {"opted_in", "existing"}:
        channel, to = contact["channel"], contact["contact"]
    elif partner.basis == "public" and "@" in partner.contact:
        if not explicit_owner_approval:
            raise PermissionError("explicit email approval is only for a public business contact")
        channel, to = "email", partner.contact
    else:
        raise PermissionError("no lawful contact basis for partner outreach")
    return {
        "step": "partner_outreach_queued",
        "partner_id": partner.partner_id,
        "connection_id": str(connection_id),
        "channel": channel,
        "to": to,
        "owner_approved": bool(explicit_owner_approval),
    }


def record_reply_if_expected(
    payloads: list[dict[str, Any]],
    *,
    connection_id: str,
    external_subject: str,
    provider_event_key: str,
    reply_text: str,
    at: str,
) -> list[dict[str, Any]]:
    """Match authenticated Telegram ingress to the latest *sent* outreach. Idempotent per event key."""
    subject, key = str(external_subject or "").strip(), str(provider_event_key or "").strip()
    if not subject or not key or len(key) > 128:
        return []
    if any(
        p.get("step") == "partner_reply"
        and p.get("connection_id") == connection_id
        and p.get("provider_event_key") == key
        for p in payloads
    ):
        return []
    st = pt.statuses(payloads)
    sent = [
        p
        for p in payloads
        if p.get("step") == "partner_outreach_sent"
        and p.get("connection_id") == connection_id
        and p.get("channel") == "telegram"
        and p.get("to") == subject
        and st.get(str(p["partner_id"]), "") in REPLYABLE
    ]
    if not sent:
        return []
    pid = str(sent[-1]["partner_id"])
    out = [
        {
            "step": "partner_reply",
            "partner_id": pid,
            "connection_id": connection_id,
            "provider_event_key": key,
            "reply_text": str(reply_text or "").replace("\x00", " ").strip()[:4000],
            "occurred_at": at,
        }
    ]
    if st.get(pid) == "contacted":
        out.append({"step": "partner_status", "partner_id": pid, "status": "replied"})
    return out


def replies(payloads: list[dict[str, Any]], partner_id: str, *, limit: int = 20) -> list[Reply]:
    rows = [p for p in payloads if p.get("step") == "partner_reply" and p.get("partner_id") == partner_id]
    rows.sort(key=lambda p: str(p["occurred_at"]), reverse=True)
    return [Reply(str(p["occurred_at"]), str(p["reply_text"])) for p in rows[: max(1, min(int(limit), 100))]]


def stats(payloads: list[dict[str, Any]]) -> dict[str, int]:
    st = pt.statuses(payloads)
    out = {"candidates": len(pt.replay(payloads))}
    for s in st.values():
        out[s] = out.get(s, 0) + 1
    out["queued"] = sum(p.get("step") == "partner_outreach_queued" for p in payloads)
    out["replies"] = sum(p.get("step") == "partner_reply" for p in payloads)
    return out
