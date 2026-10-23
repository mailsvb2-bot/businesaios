"""Customer invites: one-time codes the owner hands out (port of clientplatform invites screens).

Only a SHA-256 of the code is stored in facts; the raw code is shown to the owner once.
A customer claims with ``/join cpj_<код>``; a code works once and expires after 7 days.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from application.business_flows.projection import stable_id

PREFIX = "cpj_"
TTL_MS = 7 * 24 * 3600 * 1000


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass
class Invite:
    invite_id: str
    token_hash: str
    expires_ms: int
    claimed_by: str = ""


def replay(payloads: list[dict[str, Any]]) -> dict[str, Invite]:
    out: dict[str, Invite] = {}
    for p in payloads:
        step = p.get("step")
        if step == "invite_issued" and p["invite_id"] not in out:
            out[p["invite_id"]] = Invite(p["invite_id"], p["token_hash"], int(p["expires_ms"]))
        elif step == "invite_claimed" and p.get("invite_id") in out and not out[p["invite_id"]].claimed_by:
            out[p["invite_id"]].claimed_by = str(p["customer_user_id"])
    return out


def issue(token: str, *, now_ms: int) -> dict[str, Any]:
    if len(token) < 8:
        raise ValueError("invite_token_too_short")
    h = _hash(token)
    return {"step": "invite_issued", "invite_id": stable_id("inv", h), "token_hash": h, "expires_ms": now_ms + TTL_MS}


def claim(invites: dict[str, Invite], code: str, *, customer_user_id: str, now_ms: int) -> dict[str, Any]:
    code = str(code or "").strip()
    if not code.startswith(PREFIX):
        raise ValueError("invite_code_invalid")
    h = _hash(code.removeprefix(PREFIX))
    inv = next((i for i in invites.values() if i.token_hash == h), None)
    if inv is None:
        raise ValueError("invite_code_invalid")
    if inv.claimed_by:
        raise ValueError("invite_already_used")
    if now_ms > inv.expires_ms:
        raise ValueError("invite_expired")
    return {"step": "invite_claimed", "invite_id": inv.invite_id, "customer_user_id": str(customer_user_id)}


def stats(invites: dict[str, Invite], *, now_ms: int) -> tuple[int, int]:
    active = sum(1 for i in invites.values() if not i.claimed_by and now_ms <= i.expires_ms)
    return active, sum(1 for i in invites.values() if i.claimed_by)


def invites_text(invites: dict[str, Invite], *, now_ms: int, customers: int) -> str:
    active, claimed = stats(invites, now_ms=now_ms)
    total = active + claimed
    pct = round(claimed * 100 / total) if total else 0
    return (
        "🎁 Приглашения и рекомендации\n\n"
        f"Активных кодов: {active}\nИспользовано: {claimed}\n"
        f"Конверсия в подключение: {pct}%\nКлиентов всего: {customers}\n\n/invite_new — новый код"
    )


def issued_text(token: str) -> str:
    code = PREFIX + token
    return (
        "✅ Одноразовый код клиента создан. Он действует 7 дней.\n\n"
        f"Код: {code}\n\nКлиент отправляет боту:\n/join {code}\n\nОдин код предназначен для одного клиента."
    )
