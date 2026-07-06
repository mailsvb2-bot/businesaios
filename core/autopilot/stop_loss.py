"""Auto stop-loss orchestration for Business Autopilot.

This module is deterministic: it only builds *plans* (actions) based on inputs.
It does NOT execute side-effects.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from core.autopilot.guardrails import GuardrailVerdict

STOP_LOSS_SETTING_KEY = "autopilot:stop_loss"

@dataclass(frozen=True)
class StopLossState:
    active: bool
    reason: str = ""
    since_ms: int = 0
    details: dict[str, Any] | None = None

    @staticmethod
    def from_settings(settings: Mapping[str, Any] | None) -> StopLossState:
        raw = (settings or {}).get(STOP_LOSS_SETTING_KEY) if isinstance(settings, Mapping) else None
        if not isinstance(raw, dict):
            return StopLossState(False)
        try:
            return StopLossState(
                active=bool(raw.get("active")),
                reason=str(raw.get("reason") or ""),
                since_ms=int(raw.get("since_ms") or 0),
                details=dict(raw.get("details") or {}) if isinstance(raw.get("details"), dict) else None,
            )
        except (TypeError, ValueError):
            return StopLossState(False)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "active": bool(self.active),
            "reason": str(self.reason or ""),
            "since_ms": int(self.since_ms or 0),
        }
        if isinstance(self.details, dict):
            out["details"] = dict(self.details)
        return out




def _format_stop_loss_details(details: dict[str, Any] | None) -> str:
    if not isinstance(details, dict) or not details:
        return ""

    def _fmt_money_minor(v: object) -> str:
        try:
            i = int(v)
        except (TypeError, ValueError):
            return str(v)
        sign = "-" if i < 0 else ""
        i = abs(i)
        return f"{sign}{i} (minor)"

    reason_lines = []
    for k in ("cac_minor", "profit_minor", "spend_minor", "limit", "days"):
        if k in details:
            val = details.get(k)
            if k in {"cac_minor", "profit_minor", "spend_minor", "limit"} and isinstance(val, int | float | str):
                with suppress(TypeError, ValueError):
                    val = _fmt_money_minor(val)
            reason_lines.append(f"• {k}: {val}")

    # include any other keys deterministically
    for k in sorted(details.keys()):
        if k in {"cac_minor", "profit_minor", "spend_minor", "limit", "days"}:
            continue
        reason_lines.append(f"• {k}: {details.get(k)}")
    return "\n" + "\n".join(reason_lines) + "\n"
def build_stop_loss_state_from_verdict(*, verdict: GuardrailVerdict, now_ms: int | None = None) -> StopLossState:
    if verdict.allow:
        return StopLossState(False)
    return StopLossState(
        True,
        reason=str(verdict.reason or "STOP_LOSS"),
        since_ms=int(now_ms if now_ms is not None else int(time.time() * 1000)),
        details=dict(verdict.details or {}) if isinstance(verdict.details, Mapping) else None,
    )


def build_stop_loss_plan(
    *,
    user_id: str,
    verdict: GuardrailVerdict,
    existing: StopLossState,
    session_patch: dict[str, Any] | None = None,
    callback_query_id: str | None = None,
) -> list[dict[str, Any]]:
    state = build_stop_loss_state_from_verdict(verdict=verdict)
    if existing.active and existing.reason == state.reason:
        return []
    payload = {
        "user_id": str(user_id),
        "stop_loss": state.to_dict(),
        "session_patch": dict(session_patch or {}),
        "reason_text": f"Автопилот остановлен: {state.reason}{_format_stop_loss_details(state.details)}",
    }
    actions: list[dict[str, Any]] = [
        {"action_type": "update_session", "payload": payload},
        {"action_type": "notify_user", "payload": {"user_id": str(user_id), "text": payload["reason_text"]}},
    ]
    if callback_query_id:
        actions.append({"action_type": "answer_callback", "payload": {"callback_query_id": callback_query_id, "text": "Автопилот остановлен"}})
    return actions
