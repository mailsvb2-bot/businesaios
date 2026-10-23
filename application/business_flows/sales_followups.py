"""Per-lead customer follow-ups (port of ClientPlatform sales follow-up interactions).

Pure. A follow-up goes only through the lead's original channel (Telegram here), only
after the owner's explicit command, never at night (shifted to 08:00 business time),
and never after the customer asked not to be written to (opt-out is permanent).
A customer reply cancels the pending follow-up (see ``sales.replay``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from application.business_flows import sales as sl
from application.business_flows.automation_policy import in_quiet_hours
from application.business_flows.projection import stable_id

CANON_SALES_FOLLOWUPS = True
HOURS = (1, 24, 72)
CHANNELS = ("telegram",)
CLOSED = (sl.Stage.WON, sl.Stage.LOST)


def allowed(lead: sl.Lead) -> bool:
    return lead.source in CHANNELS and bool(lead.customer_id) and not lead.followup_suppressed


def shift_out_of_night(due_ms: int, tz: str) -> int:
    if not in_quiet_hours(due_ms, tz):
        return due_ms
    local = datetime.fromtimestamp(due_ms / 1000, UTC).astimezone(ZoneInfo(tz or "UTC"))
    morning = local.replace(hour=8, minute=0, second=0, microsecond=0)
    if local.hour >= 22:
        morning += timedelta(days=1)
    return int(morning.timestamp() * 1000)


def status(lead: sl.Lead) -> str:
    """Donor _sales_followup_message lines."""
    if lead.stage in CLOSED:
        return "Обращение закрыто."
    if lead.followup_suppressed:
        return "Клиент попросил больше не писать по этому каналу."
    if lead.followup_id:
        day = datetime.fromtimestamp(lead.followup_due_ms / 1000, UTC).strftime("%d.%m %H:%M UTC")
        return f"Напоминание уже запланировано: {day}. Отменить: /lead_followup_cancel"
    if allowed(lead):
        return (
            "Сообщение уйдёт только по исходному каналу клиента после явной команды:\n"
            "/lead_followup N | 24 | Текст клиенту (1, 24 или 72 ч; ночью — перенос на 8:00).\n"
            "Если клиент попросил не писать: /lead_optout N | подтвердить"
        )
    return "Для этого обращения автоматическое напоминание сейчас недоступно."


def plan(st: sl.State, arg: str, *, now_ms: int, tz: str) -> dict[str, Any]:
    parts = [x.strip() for x in str(arg or "").split("|")]
    if len(parts) < 3 or not parts[2]:
        raise ValueError("формат: /lead_followup N | 24 | Текст клиенту")
    lead = sl.pick(st, parts[0])
    if lead.stage in CLOSED:
        raise ValueError("обращение закрыто")
    if not allowed(lead):
        raise ValueError("напоминание недоступно (нет исходного канала или клиент отказался)")
    if lead.followup_id:
        raise ValueError("напоминание уже запланировано, сначала /lead_followup_cancel N")
    if not parts[1].isdigit() or int(parts[1]) not in HOURS:
        raise ValueError("через сколько часов: 1, 24 или 72")
    due = shift_out_of_night(now_ms + int(parts[1]) * 3_600_000, tz)
    return {
        "step": "followup_planned",
        "lead_id": lead.lead_id,
        "followup_id": stable_id("fup", lead.lead_id, now_ms),
        "due_ms": due,
        "text": parts[2][:1000],
    }


def cancel(st: sl.State, ref: str) -> dict[str, Any]:
    lead = sl.pick(st, ref)
    if not lead.followup_id:
        raise ValueError("активного напоминания нет")
    return {"step": "followup_cancelled", "lead_id": lead.lead_id, "followup_id": lead.followup_id}


def optout(st: sl.State, arg: str) -> dict[str, Any]:
    ref, _, confirm = (x.strip() for x in str(arg or "").partition("|"))
    if confirm.casefold() != "подтвердить":
        raise ValueError("подтвердите: /lead_optout N | подтвердить")
    lead = sl.pick(st, ref)
    if lead.followup_suppressed:
        raise ValueError("уже запрещено")
    return {"step": "followup_optout", "lead_id": lead.lead_id}


def due(st: sl.State, *, now_ms: int) -> list[sl.Lead]:
    return [
        x
        for x in st.leads.values()
        if x.followup_id and x.followup_due_ms <= now_ms and allowed(x) and x.stage not in CLOSED
    ]


__all__ = ["CANON_SALES_FOLLOWUPS", "allowed", "cancel", "due", "optout", "plan", "shift_out_of_night", "status"]
