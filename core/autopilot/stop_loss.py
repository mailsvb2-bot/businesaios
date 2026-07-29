"""Deterministic stop-loss action construction for Business Autopilot.

This module never executes effects and never reads the wall clock. It builds one
canonical ``set_user_setting@v1`` payload, whose existing effect owner persists
the state and optionally notifies the user under the same signed decision.
"""

from __future__ import annotations

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
    def from_settings(settings: Mapping[str, Any] | None) -> "StopLossState":
        raw = (
            (settings or {}).get(STOP_LOSS_SETTING_KEY)
            if isinstance(settings, Mapping)
            else None
        )
        if not isinstance(raw, dict):
            return StopLossState(False)
        try:
            return StopLossState(
                active=bool(raw.get("active")),
                reason=str(raw.get("reason") or ""),
                since_ms=int(raw.get("since_ms") or 0),
                details=(
                    dict(raw.get("details") or {})
                    if isinstance(raw.get("details"), dict)
                    else None
                ),
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

    def _fmt_money_minor(value: object) -> str:
        try:
            amount = int(value)
        except (TypeError, ValueError):
            return str(value)
        sign = "-" if amount < 0 else ""
        return f"{sign}{abs(amount)} (minor)"

    lines = []
    primary_keys = ("cac_minor", "profit_minor", "spend_minor", "limit", "days")
    for key in primary_keys:
        if key not in details:
            continue
        value = details.get(key)
        if key in {"cac_minor", "profit_minor", "spend_minor", "limit"}:
            with suppress(TypeError, ValueError):
                value = _fmt_money_minor(value)
        lines.append(f"• {key}: {value}")

    for key in sorted(details):
        if key not in primary_keys:
            lines.append(f"• {key}: {details.get(key)}")
    return "\n" + "\n".join(lines) + "\n"


def build_stop_loss_state_from_verdict(
    *,
    verdict: GuardrailVerdict,
    now_ms: int,
    existing: StopLossState | None = None,
) -> StopLossState:
    """Project a guardrail verdict into deterministic persisted state."""

    if verdict.allow:
        return StopLossState(False)
    previous = existing or StopLossState(False)
    reason = str(verdict.reason or "STOP_LOSS")
    since_ms = (
        int(previous.since_ms)
        if previous.active and previous.reason == reason and previous.since_ms > 0
        else max(0, int(now_ms))
    )
    return StopLossState(
        active=True,
        reason=reason,
        since_ms=since_ms,
        details=(
            dict(verdict.details or {})
            if isinstance(verdict.details, Mapping)
            else None
        ),
    )


def build_stop_loss_plan(
    *,
    tenant_id: str,
    user_id: str,
    verdict: GuardrailVerdict,
    existing: StopLossState,
    now_ms: int,
    callback_query_id: str | None = None,
) -> dict[str, Any]:
    """Build the single canonical setting action payload for activation.

    The historical function name is retained as a stable import surface. The
    returned value is intentionally one action payload, not an unsigned bundle
    of nested effects.
    """

    state = build_stop_loss_state_from_verdict(
        verdict=verdict,
        now_ms=now_ms,
        existing=existing,
    )
    return {
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "key": STOP_LOSS_SETTING_KEY,
        "value": state.to_dict(),
        "notify_text": (
            f"Автопилот остановлен: {state.reason}"
            f"{_format_stop_loss_details(state.details)}"
        ),
        "callback_query_id": callback_query_id,
        "channel": "telegram",
    }


def build_clear_stop_loss_plan(
    *,
    tenant_id: str,
    user_id: str,
    callback_query_id: str | None = None,
) -> dict[str, Any]:
    """Build one signed setting action that clears stop-loss and confirms it."""

    return {
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "key": STOP_LOSS_SETTING_KEY,
        "value": StopLossState(False).to_dict(),
        "notify_text": "Stop-loss сброшен. Автопилот можно запустить снова.",
        "callback_query_id": callback_query_id,
        "channel": "telegram",
    }


__all__ = [
    "STOP_LOSS_SETTING_KEY",
    "StopLossState",
    "build_clear_stop_loss_plan",
    "build_stop_loss_plan",
    "build_stop_loss_state_from_verdict",
]
