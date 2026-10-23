"""Event bookings: owner opens slots, participants book/cancel, reminder plan.

Tenant-wide projection over ``bookings@v1`` facts. Reminders are a pure plan
(24h and 1h before start); dispatch stays with the existing provider queue -
this module never schedules or sends anything itself.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from application.business_flows.projection import stable_id

REMINDER_OFFSETS_MIN: tuple[tuple[int, str], ...] = ((24 * 60, "за 24 часа"), (60, "за 1 час"))
MAX_DURATION_MIN = 8 * 60


@dataclass(frozen=True)
class Slot:
    slot_id: str
    title: str
    starts_at_ms: int
    duration_min: int
    status: str = "open"  # open | booked | closed
    customer_id: str = ""


def replay(payloads: list[dict[str, Any]]) -> dict[str, Slot]:
    slots: dict[str, Slot] = {}
    for p in payloads:
        sid, step = str(p.get("slot_id") or ""), str(p.get("step") or "")
        if step == "slot_opened" and sid not in slots:
            slots[sid] = Slot(
                sid, str(p.get("title") or ""), int(p.get("starts_at_ms") or 0), int(p.get("duration_min") or 0)
            )
        elif sid in slots:
            if step == "booked":
                slots[sid] = replace(slots[sid], status="booked", customer_id=str(p.get("customer_id") or ""))
            elif step == "booking_cancelled":
                slots[sid] = replace(slots[sid], status="open", customer_id="")
            elif step == "slot_closed":
                slots[sid] = replace(slots[sid], status="closed")
    return slots


def upcoming(
    slots: dict[str, Slot], *, now_ms: int, status: str | None = None, customer_id: str | None = None
) -> list[Slot]:
    rows = [
        s
        for s in slots.values()
        if s.starts_at_ms > now_ms
        and (status is None or s.status == status)
        and (customer_id is None or s.customer_id == customer_id)
    ]
    return sorted(rows, key=lambda s: (s.starts_at_ms, s.slot_id))


def parse_slot(arg: str, *, now_ms: int, tz: str = "Europe/Moscow") -> dict[str, Any]:
    """``YYYY-MM-DD HH:MM [minutes] title`` in the business timezone."""
    parts = str(arg or "").split()
    if len(parts) < 3:
        raise ValueError("slot_format: /add_slot 2026-10-30 15:00 60 Название")
    try:
        start = datetime.strptime(f"{parts[0]} {parts[1]}", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(tz))
    except ValueError as exc:
        raise ValueError("slot_datetime_invalid") from exc
    duration, rest = (int(parts[2]), parts[3:]) if parts[2].isdigit() else (60, parts[2:])
    title = " ".join(rest).strip()[:120]
    starts_at_ms = int(start.timestamp() * 1000)
    if not title or not 5 <= duration <= MAX_DURATION_MIN:
        raise ValueError("slot_title_or_duration_invalid")
    if starts_at_ms <= now_ms:
        raise ValueError("slot_in_past")
    return {
        "step": "slot_opened",
        "slot_id": stable_id("slot", starts_at_ms, title),
        "title": title,
        "starts_at_ms": starts_at_ms,
        "duration_min": duration,
    }


def book(slots: dict[str, Slot], slot: Slot | None, *, customer_id: str, now_ms: int) -> dict[str, Any]:
    if slot is None or slot.status != "open" or slot.starts_at_ms <= now_ms:
        raise ValueError("slot_unavailable")
    if any(s.customer_id == customer_id and s.starts_at_ms == slot.starts_at_ms for s in slots.values()):
        raise ValueError("booking_time_conflict")
    return {
        "step": "booked",
        "slot_id": slot.slot_id,
        "customer_id": customer_id,
        "reminders_at_ms": [ms for ms, _ in reminder_plan(slot, now_ms=now_ms)],
    }


def cancel(slot: Slot | None, *, customer_id: str, now_ms: int) -> dict[str, Any]:
    if slot is None or slot.status != "booked" or slot.customer_id != customer_id:
        raise ValueError("booking_not_found")
    if slot.starts_at_ms <= now_ms:
        raise ValueError("booking_already_started")
    return {"step": "booking_cancelled", "slot_id": slot.slot_id, "customer_id": customer_id}


def reminder_plan(slot: Slot, *, now_ms: int) -> list[tuple[int, str]]:
    plan = [(slot.starts_at_ms - m * 60_000, label) for m, label in REMINDER_OFFSETS_MIN]
    return [(ms, label) for ms, label in plan if ms > now_ms]


def due_reminders(slots: dict[str, Slot], *, now_ms: int, sent: set[tuple[str, int]]) -> list[tuple[Slot, int, str]]:
    """Reminders whose time has come and which were not yet delivered (idempotent key: slot, offset)."""
    out = []
    for slot in slots.values():
        if slot.status != "booked" or slot.starts_at_ms <= now_ms:
            continue
        for minutes, label in REMINDER_OFFSETS_MIN:
            at = slot.starts_at_ms - minutes * 60_000
            if at <= now_ms and (slot.slot_id, minutes) not in sent:
                out.append((slot, minutes, label))
    return out


def sent_reminders(payloads: list[dict[str, Any]]) -> set[tuple[str, int]]:
    return {(str(p.get("slot_id")), int(p.get("minutes") or 0)) for p in payloads if p.get("step") == "reminder_sent"}


def fmt(slot: Slot, tz: str = "Europe/Moscow") -> str:
    when = datetime.fromtimestamp(slot.starts_at_ms / 1000, ZoneInfo(tz)).strftime("%d.%m %H:%M")
    return f"{when} МСК · {slot.title} ({slot.duration_min} мин)"


__all__ = [
    "REMINDER_OFFSETS_MIN",
    "Slot",
    "book",
    "cancel",
    "due_reminders",
    "fmt",
    "parse_slot",
    "reminder_plan",
    "replay",
    "sent_reminders",
    "upcoming",
]
