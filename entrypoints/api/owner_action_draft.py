from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from entrypoints.api.headless_runtime_provider import HeadlessRuntimeProvider, build_default_headless_runtime_provider

CANON_OWNER_ACTION_DRAFT_PROJECTION = True
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_SUPPORTED_ACTION = "send_message@v1"
_PROVIDER_BY_CHANNEL = {"vk": "vk_messaging", "max": "max_messaging", "email": "email_connector"}
_PLACEHOLDERS = {"", "anonymous", "system", "unknown", "default", "none", "null"}


class OwnerActionDraftError(ValueError):
    def __init__(self, code: str, *, status_code: int = 409) -> None:
        super().__init__(code)
        self.code = str(code)
        self.status_code = int(status_code)


def _text(value: object) -> str:
    return str(value or "").strip()


def _safe_recipient(value: object) -> str:
    recipient = _text(value)
    lowered = recipient.casefold()
    if lowered in _PLACEHOLDERS or (recipient.startswith("{") and recipient.endswith("}")):
        return ""
    return recipient


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(frozen=True)
class OwnerActionDraftProjector:
    """Projects one persisted DecisionCore step into an editable owner draft.

    This boundary never executes, signs, approves, queues, or dispatches an action.
    The existing /actions/execute -> approval -> provider queue path remains the
    only execution path after the owner reviews the draft.
    """

    runtime_provider: HeadlessRuntimeProvider = field(default_factory=build_default_headless_runtime_provider)

    def project(self, *, tenant_id: str, business_id: str, run_id: str, decision_id: str, action_id: str) -> dict[str, Any]:
        safe_run_id = _text(run_id)
        if not _RUN_ID.fullmatch(safe_run_id):
            raise OwnerActionDraftError("decision_run_id_invalid", status_code=422)
        decision_id, action_id = _text(decision_id), _text(action_id)
        if not decision_id or not action_id:
            raise OwnerActionDraftError("decision_step_identity_required", status_code=422)
        try:
            record = self.runtime_provider.get_runtime().ledger.read(safe_run_id)
        except (FileNotFoundError, OSError, ValueError):
            raise OwnerActionDraftError("decision_run_not_found", status_code=404) from None
        if _text(record.get("tenant_id")) != _text(tenant_id) or _text(record.get("business_id")) != _text(business_id):
            raise OwnerActionDraftError("decision_run_not_found", status_code=404)
        artifact = _mapping(record.get("canonical_run_artifact"))
        raw_steps = artifact.get("step_artifacts")
        steps = [dict(row) for row in raw_steps if isinstance(row, Mapping)] if isinstance(raw_steps, list) else []
        matches = [row for row in steps if _text(row.get("decision_id")) == decision_id and _text(row.get("action_id")) == action_id]
        if len(matches) != 1:
            raise OwnerActionDraftError("decision_step_not_found", status_code=404)
        step = matches[0]
        if _text(step.get("action_type")) != _SUPPORTED_ACTION:
            raise OwnerActionDraftError("decision_action_not_handoff_eligible")
        if bool(step.get("executed")) or bool(step.get("verified")):
            raise OwnerActionDraftError("decision_action_already_executed")
        payload = _mapping(step.get("payload"))
        channel = _text(payload.get("channel")).casefold()
        recipient = _safe_recipient(
            payload.get("recipient") or payload.get("user_id") or payload.get("email") or payload.get("peer_id")
            or payload.get("chat_id") or payload.get("channel_id") or payload.get("recipient_id") or payload.get("to") or payload.get("receiver")
        ) if channel in _PROVIDER_BY_CHANNEL else ""
        message = _text(payload.get("text") or payload.get("body") or payload.get("message"))
        return {
            "source": "decision_core_ledger",
            "run_id": safe_run_id,
            "decision_id": decision_id,
            "action_id": action_id,
            "action_type": _SUPPORTED_ACTION,
            "goal": _text(record.get("goal")),
            "status": _text(step.get("status")),
            "operator_required": bool(step.get("operator_required")),
            "text": message,
            "subject": _text(payload.get("subject")),
            "recipient": recipient,
            "suggested_channel": channel if channel in _PROVIDER_BY_CHANNEL else "",
            "suggested_provider_key": _PROVIDER_BY_CHANNEL.get(channel, ""),
            "requires_recipient": not bool(recipient),
            "requires_channel": channel not in _PROVIDER_BY_CHANNEL,
            "editable": True,
            "execution_allowed": False,
            "next_boundary": "/actions/execute",
        }


__all__ = ["CANON_OWNER_ACTION_DRAFT_PROJECTION", "OwnerActionDraftError", "OwnerActionDraftProjector"]
