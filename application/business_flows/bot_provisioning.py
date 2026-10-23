"""Managed bot provisioning state machine (owner connects their own Telegram bot).

Raw bot tokens never enter events: only a credential *reference* may be
attached by the server-side secret intake. Verification (getMe/webhook) is a
separate server step that records ``verified``/``failed``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from application.business_flows.projection import stable_id

_USERNAME = re.compile(r"[a-z0-9_]{5,32}")
_CRED_REF = re.compile(r"(vault|secret|env):[A-Za-z0-9_./:-]{3,120}")


class ProvisioningStatus(StrEnum):
    AWAITING_BOT = "awaiting_bot"  # Telegram Managed Bots: owner is creating the child bot
    AWAITING_SECRET = "awaiting_secret"
    READY = "ready"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DISABLED = "disabled"  # owner paused the bot; reversible via activate (re-verified)
    REVOKED = "revoked"  # credential reference retired; terminal


_S = ProvisioningStatus
_TRANSITIONS: dict[str, tuple[set[ProvisioningStatus], ProvisioningStatus]] = {
    "secret_attached": ({_S.AWAITING_SECRET}, _S.READY),
    "verify_started": ({_S.READY}, _S.VERIFYING),
    "verified": ({_S.VERIFYING, _S.READY}, _S.COMPLETED),
    "failed": ({_S.VERIFYING, _S.READY}, _S.FAILED),
    "retry": ({_S.FAILED}, _S.AWAITING_SECRET),
    "cancel": ({_S.AWAITING_BOT, _S.AWAITING_SECRET, _S.READY, _S.VERIFYING, _S.FAILED}, _S.CANCELLED),
    "bot_created": ({_S.AWAITING_BOT}, _S.AWAITING_SECRET),
    "disable": ({_S.COMPLETED}, _S.DISABLED),
    "activated": ({_S.DISABLED}, _S.COMPLETED),
    "revoke": ({_S.COMPLETED, _S.DISABLED}, _S.REVOKED),
}
TERMINAL = frozenset({_S.COMPLETED, _S.CANCELLED, _S.DISABLED, _S.REVOKED})
EVENT_CLOCK_SKEW_MS = 60_000


@dataclass(frozen=True)
class Provisioning:
    request_id: str
    username: str
    status: ProvisioningStatus
    credential_ref: str = ""
    error_code: str = ""
    external_bot_id: str = ""
    user_id: str = ""
    created_ms: int = 0
    source: str = "botfather"


def normalize_username(value: str) -> str:
    name = str(value or "").strip().lstrip("@").lower()
    if not _USERNAME.fullmatch(name) or not name.endswith("bot"):
        raise ValueError("bot_username_invalid")
    return name


def replay(payloads: list[dict[str, Any]]) -> dict[str, Provisioning]:
    state: dict[str, Provisioning] = {}
    for p in payloads:
        rid, step = str(p.get("request_id") or ""), str(p.get("step") or "")
        if step == "requested" and rid not in state:
            state[rid] = Provisioning(
                rid,
                str(p.get("username") or ""),
                _S(str(p.get("status") or _S.AWAITING_SECRET.value)),
                user_id=str(p.get("user_id") or ""),
                created_ms=int(p.get("at_ms") or 0),
                source=str(p.get("source") or "botfather"),
            )
        elif rid in state and p.get("status"):
            cur = state[rid]
            status = _S(str(p["status"]))
            state[rid] = replace(
                cur,
                username=str(p.get("username") or cur.username),
                status=status,
                credential_ref="" if status is _S.REVOKED else str(p.get("credential_ref") or cur.credential_ref),
                error_code=str(p.get("error_code") or ""),
                external_bot_id=str(p.get("bot_id") or p.get("external_bot_id") or cur.external_bot_id),
            )
    return state


def active(state: dict[str, Provisioning]) -> Provisioning | None:
    live = [item for item in state.values() if item.status not in TERMINAL]
    return live[-1] if live else None


def owned(state: dict[str, Provisioning]) -> Provisioning | None:
    """The tenant's live bot (connected or paused) — target of owner disable/activate/revoke."""
    live = [i for i in state.values() if i.status in {_S.COMPLETED, _S.DISABLED}]
    return live[-1] if live else None


def request(state: dict[str, Provisioning], *, tenant_id: str, user_id: str, username: str) -> dict[str, Any]:
    name = normalize_username(username)
    current = active(state)
    if current is not None:
        raise ValueError("bot_provisioning_already_active")
    rid = stable_id("botprov", tenant_id, user_id, name, len(state))
    return {"request_id": rid, "step": "requested", "username": name, "status": _S.AWAITING_SECRET.value}


def transition(item: Provisioning, step: str, *, credential_ref: str = "", error_code: str = "") -> dict[str, Any]:
    if step not in _TRANSITIONS:
        raise ValueError("bot_provisioning_step_unknown")
    allowed, target = _TRANSITIONS[step]
    if item.status not in allowed:
        raise ValueError(f"bot_provisioning_invalid_transition:{item.status.value}->{target.value}")
    if step == "secret_attached" and not _CRED_REF.fullmatch(credential_ref):
        raise ValueError("bot_provisioning_credential_reference_required")
    out = {"request_id": item.request_id, "step": step, "status": target.value}
    if credential_ref:
        out["credential_ref"] = credential_ref
    if error_code:
        out["error_code"] = error_code
    return out


def begin_managed(
    state: dict[str, Provisioning], *, tenant_id: str, user_id: str, now_ms: int
) -> dict[str, Any] | None:
    """Donor begin_telegram_managed_bot_onboarding: one durable request per user (idempotent -> None)."""
    if pending_for_user(state, user_id) is not None:
        return None
    if active(state) is not None:
        raise ValueError("bot_provisioning_already_active")
    rid = stable_id("botprov", tenant_id, user_id, "managed", len(state))
    return {
        "request_id": rid,
        "step": "requested",
        "source": "managed",
        "user_id": str(user_id),
        "at_ms": int(now_ms),
        "status": _S.AWAITING_BOT.value,
    }


def pending_for_user(state: dict[str, Provisioning], user_id: str) -> Provisioning | None:
    live = [
        i for i in state.values() if i.source == "managed" and i.user_id == str(user_id) and i.status not in TERMINAL
    ]
    return live[-1] if live else None


def assert_event_is_current(item: Provisioning, event_ms: int | None) -> None:
    if event_ms is not None and int(event_ms) + EVENT_CLOCK_SKEW_MS < item.created_ms:
        raise ValueError("managed bot creation event predates the active request")


def record_created(
    item: Provisioning, *, external_bot_id: str, username: str, event_ms: int | None = None
) -> dict[str, Any] | None:
    """Persist the child identity before the token is fetched; a repeat with the same identity is a no-op."""
    assert_event_is_current(item, event_ms)
    name, bid = normalize_username(username), str(external_bot_id or "").strip()
    if not bid.isdigit():
        raise ValueError("managed_bot_external_id_invalid")
    if item.status is not _S.AWAITING_BOT:
        if (item.external_bot_id, item.username) == (bid, name):
            return None
        raise ValueError("managed bot creation identity does not match the active request")
    return {**transition(item, "bot_created"), "username": name, "external_bot_id": bid}


def has_active_bot(state: dict[str, Provisioning]) -> bool:
    return any(i.status is _S.COMPLETED for i in state.values())


def identity_error(item: Provisioning, getme: dict[str, Any] | None) -> str:
    """'' when getMe proves the token belongs to this request's bot (username and, if known, id)."""
    bot = (getme or {}).get("bot") if isinstance(getme, dict) else None
    if not isinstance(bot, dict) or bot.get("is_bot") is not True:
        return "getme_not_a_bot"
    if str(bot.get("username") or "").lower() != item.username:
        return "getme_username_mismatch"
    if item.external_bot_id and str(bot.get("id") or "") != item.external_bot_id:
        return "getme_bot_id_mismatch"
    return ""


def verify_identity(item: Provisioning, getme: dict[str, Any] | None) -> dict[str, Any]:
    """Map a Telegram getMe result onto ``verified``/``failed``."""
    error = identity_error(item, getme)
    if error:
        return transition(item, "failed", error_code=error)
    return {**transition(item, "verified"), "bot_id": int(getme["bot"].get("id") or 0)}  # type: ignore[index]


__all__ = [
    "Provisioning",
    "ProvisioningStatus",
    "active",
    "assert_event_is_current",
    "begin_managed",
    "has_active_bot",
    "identity_error",
    "owned",
    "pending_for_user",
    "record_created",
    "normalize_username",
    "replay",
    "request",
    "transition",
    "verify_identity",
]
