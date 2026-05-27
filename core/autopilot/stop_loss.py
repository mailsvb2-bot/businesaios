from __future__ import annotations

"""Auto stop-loss orchestration for Business Autopilot.

This module is deterministic: it only builds *plans* (actions) based on inputs.
It does NOT execute side-effects.
"""

import time
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from core.autopilot.guardrails import GuardrailVerdict

STOP_LOSS_SETTING_KEY = "autopilot:stop_loss"


@dataclass(frozen=True)
class StopLossState:
    active: bool
    reason: str = ""
    since_ms: int = 0
    details: Dict[str, Any] | None = None

    @staticmethod
    def from_settings(settings: Mapping[str, Any] | None) -> "StopLossState":
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

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "active": bool(self.active),
            "reason": str(self.reason or ""),
            "since_ms": int(self.since_ms or 0),
        }
        if isinstance(self.details, dict):
            out["details"] = dict(self.details)
        return out




def _format_stop_loss_details(details: Dict[str, Any] | None) -> str:
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
            if k in {"cac_minor", "profit_minor", "spend_minor", "limit"} and isinstance(val, (int, float, str)):
                try:
                    val = _fmt_money_minor(val)
                except (TypeError, ValueError):
                    pass
            reason_lines.append(f"• {k}: {val}")

    # include any other keys deterministically
    for k in sorted(details.keys()):
        if k in {"cac_minor", "profit_minor", "spend_minor", "limit", "days"}:
            continue
        reason_lines.append(f"• {k}: {details.get(k)}")
    return "\n" + "\n".join(reason_lines) + "\n"
def build_stop_loss_state_from_verdict(*, verdict: GuardrailVerdict, now_ms: Optional[int] = None) -> StopLossState:
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
    session_patch: Dict[str, Any] | None = None,
    callback_query_id: str | None = None,
    emit_event: bool = True,
) -> Dict[str, Any]:
    """Build an execute_plan@v1 payload to activate stop-loss.

    It sets user setting autopilot:stop_loss and optionally patches autopilot:session.
    """

    now_ms = int(time.time() * 1000)
    st = existing
    if not st.active:
        st = build_stop_loss_state_from_verdict(verdict=verdict, now_ms=now_ms)

    steps = []
    if emit_event:
        steps.append(
            {
                "action": "emit_event@v1",
                "payload": {
                    "user_id": str(user_id),
                    "event_type": "autopilot_stop_loss_triggered@v1",
                    "payload": {"reason": str(st.reason), "details": dict(st.details or {})},
                    "source": "autopilot",
                },
            }
        )

    steps.append(
        {
            "action": "set_user_setting@v1",
            "payload": {"user_id": str(user_id), "key": STOP_LOSS_SETTING_KEY, "value": st.to_dict()},
        }
    )

    if isinstance(session_patch, dict) and session_patch:
        steps.append(
            {
                "action": "set_user_setting@v1",
                "payload": {
                    "user_id": str(user_id),
                    "key": "autopilot:session",
                    "value": dict(session_patch),
                },
            }
        )

    msg = (
        "⚠️ Авто-stop-loss сработал.\n\n"
        f"Причина: {st.reason}\n"
        "Автопилот перешёл в режим *аудита* (без изменений).\n\n"
        "Что делать:\n"
        "1) Проверь трекинг конверсий/оплат\n"
        "2) Проверь оффер и цену\n"
        "3) Если всё ок — сбрось stop-loss в меню Autopilot."
    )

    steps.append(
        {
            "action": "send_message@v1",
            "payload": {
                "user_id": str(user_id),
                "text": msg,
                "reply_markup": {"inline_keyboard": [[{"text": "⬅️ Назад", "callback_data": "autopilot:menu"}]]},
                "callback_query_id": callback_query_id,
                "track_event_type": "autopilot_stop_loss_notified@v1",
                "track_payload": {"reason": str(st.reason)},
            },
        }
    )

    return {"user_id": str(user_id), "steps": steps}


def build_clear_stop_loss_plan(*, user_id: str, callback_query_id: str | None = None) -> Dict[str, Any]:
    steps = [
        {
            "action": "set_user_setting@v1",
            "payload": {
                "user_id": str(user_id),
                "key": STOP_LOSS_SETTING_KEY,
                "value": {"active": False, "reason": "", "since_ms": 0},
            },
        },
        {
            "action": "emit_event@v1",
            "payload": {"user_id": str(user_id), "event_type": "autopilot_stop_loss_cleared@v1", "payload": {}, "source": "autopilot"},
        },
        {
            "action": "send_message@v1",
            "payload": {
                "user_id": str(user_id),
                "text": "✅ Stop-loss сброшен. Автопилот снова может предлагать изменения.",
                "reply_markup": {"inline_keyboard": [[{"text": "⬅️ Назад", "callback_data": "autopilot:menu"}]]},
                "callback_query_id": callback_query_id,
            },
        },
    ]
    return {"user_id": str(user_id), "steps": steps}
