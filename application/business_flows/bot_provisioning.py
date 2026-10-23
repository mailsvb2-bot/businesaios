"""Managed bot provisioning state machine (owner connects their own Telegram bot).

Raw bot tokens never enter events: only a credential *reference* may be
attached by the server-side secret intake. Verification (getMe/webhook) is a
separate server step that records ``verified``/``failed``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from application.business_flows.projection import stable_id

_USERNAME = re.compile(r"[a-z0-9_]{5,32}")
_CRED_REF = re.compile(r"(vault|secret|env):[A-Za-z0-9_./:-]{3,120}")


class ProvisioningStatus(StrEnum):
    AWAITING_SECRET = "awaiting_secret"
    READY = "ready"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


_S = ProvisioningStatus
_TRANSITIONS: dict[str, tuple[set[ProvisioningStatus], ProvisioningStatus]] = {
    "secret_attached": ({_S.AWAITING_SECRET}, _S.READY),
    "verify_started": ({_S.READY}, _S.VERIFYING),
    "verified": ({_S.VERIFYING}, _S.COMPLETED),
    "failed": ({_S.VERIFYING, _S.READY}, _S.FAILED),
    "retry": ({_S.FAILED}, _S.AWAITING_SECRET),
    "cancel": ({_S.AWAITING_SECRET, _S.READY, _S.VERIFYING, _S.FAILED}, _S.CANCELLED),
}
TERMINAL = frozenset({_S.COMPLETED, _S.CANCELLED})


@dataclass(frozen=True)
class Provisioning:
    request_id: str
    username: str
    status: ProvisioningStatus
    credential_ref: str = ""
    error_code: str = ""


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
            state[rid] = Provisioning(rid, str(p.get("username") or ""), _S.AWAITING_SECRET)
        elif rid in state and p.get("status"):
            cur = state[rid]
            state[rid] = Provisioning(
                rid,
                cur.username,
                _S(str(p["status"])),
                str(p.get("credential_ref") or cur.credential_ref),
                str(p.get("error_code") or ""),
            )
    return state


def active(state: dict[str, Provisioning]) -> Provisioning | None:
    live = [item for item in state.values() if item.status not in TERMINAL]
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


__all__ = ["Provisioning", "ProvisioningStatus", "active", "normalize_username", "replay", "request", "transition"]
