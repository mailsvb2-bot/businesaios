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

# Donor event_notifications offsets: 24h / 3h / 15m before each session.
REMINDER_OFFSETS_MIN: tuple[tuple[int, str], ...] = (
    (24 * 60, "за 24 часа"),
    (3 * 60, "за 3 часа"),
    (15, "за 15 минут"),
)
REMINDER_KIND = {24 * 60: "24h", 3 * 60: "3h", 15: "15m"}
MAX_SESSIONS = 14
MAX_DURATION_MIN = 8 * 60


@dataclass(frozen=True)
class Slot:
    slot_id: str
    title: str
    starts_at_ms: int
    duration_min: int
    status: str = "open"  # open | booked | closed
    customer_id: str = ""
    revision: int = 0  # bumps on reschedule: unsent reminders of older revisions are void
    series_id: str = ""
    position: int = 1
    session_count: int = 1


def _expand(payloads: list[dict[str, Any]]):
    for p in payloads:
        if p.get("step") == "sessions_opened":
            yield from (dict(x, step="slot_opened") for x in p.get("sessions") or [])
        elif p.get("step") == "series_rescheduled":  # owner series schedule edit (event_schedule_edit)
            yield from (dict(x) for x in p.get("changes") or [])
        else:
            yield p


def replay(payloads: list[dict[str, Any]]) -> dict[str, Slot]:
    slots: dict[str, Slot] = {}
    for p in _expand(payloads):
        sid, step = str(p.get("slot_id") or ""), str(p.get("step") or "")
        if step == "slot_opened" and sid not in slots:
            slots[sid] = Slot(
                sid,
                str(p.get("title") or ""),
                int(p.get("starts_at_ms") or 0),
                int(p.get("duration_min") or 0),
                series_id=str(p.get("series_id") or ""),
                position=int(p.get("position") or 1),
                session_count=int(p.get("session_count") or 1),
            )
        elif sid in slots:
            if step == "booked":
                slots[sid] = replace(slots[sid], status="booked", customer_id=str(p.get("customer_id") or ""))
            elif step == "booking_cancelled":
                slots[sid] = replace(slots[sid], status="open", customer_id="")
            elif step == "slot_rescheduled":
                slots[sid] = replace(
                    slots[sid], starts_at_ms=int(p.get("starts_at_ms") or 0), revision=int(p.get("revision") or 0)
                )
            elif step == "slot_edited":
                cur = slots[sid]
                slots[sid] = replace(
                    cur,
                    title=str(p.get("title") or cur.title),
                    duration_min=int(p.get("duration_min") or cur.duration_min),
                )
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


def parse_sessions(arg: str, *, now_ms: int, tz: str = "Europe/Moscow") -> list[dict[str, Any]]:
    """``YYYY-MM-DD HH:MM minutes N title``: N daily sessions of one event (donor EventSession model)."""
    parts = str(arg or "").split()
    if len(parts) < 5 or not parts[2].isdigit() or not parts[3].isdigit():
        raise ValueError("sessions_format: /add_sessions 2026-10-30 19:00 60 3 Марафон")
    count = int(parts[3])
    if not 2 <= count <= MAX_SESSIONS:
        raise ValueError("sessions_count_invalid")
    first = parse_slot(" ".join(parts[:3] + parts[4:]), now_ms=now_ms, tz=tz)
    series = stable_id("series", first["starts_at_ms"], first["title"], count)
    out = []
    for i in range(count):
        at = first["starts_at_ms"] + i * 86_400_000
        out.append(
            dict(
                first,
                slot_id=stable_id("slot", at, first["title"], series),
                starts_at_ms=at,
                series_id=series,
                position=i + 1,
                session_count=count,
            )
        )
    return out


def edit(slot: Slot | None, arg: str) -> dict[str, Any]:
    """Owner edits title and/or duration: ``[minutes] [new title]``."""
    if slot is None or slot.status == "closed":
        raise ValueError("slot_not_found")
    parts = str(arg or "").split()
    duration = int(parts.pop(0)) if parts and parts[0].isdigit() else 0
    title = " ".join(parts).strip()[:120]
    if not title and not duration:
        raise ValueError("edit_format: /edit_slot N [минуты] [название]")
    if duration and not 5 <= duration <= MAX_DURATION_MIN:
        raise ValueError("slot_title_or_duration_invalid")
    return {"step": "slot_edited", "slot_id": slot.slot_id, "title": title, "duration_min": duration}


def reschedule(slot: Slot | None, arg: str, *, now_ms: int, tz: str = "Europe/Moscow") -> dict[str, Any]:
    """Owner moves a session (donor ``reschedule_event_notifications``): new revision voids unsent reminders."""
    if slot is None or slot.status == "closed":
        raise ValueError("slot_not_found")
    parts = str(arg or "").split()
    if len(parts) != 2:
        raise ValueError("reschedule_format: /reschedule_slot N 2026-10-30 15:00")
    try:
        start = datetime.strptime(f"{parts[0]} {parts[1]}", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(tz))
    except ValueError as exc:
        raise ValueError("slot_datetime_invalid") from exc
    at = int(start.timestamp() * 1000)
    if at <= now_ms:
        raise ValueError("slot_in_past")
    if at == slot.starts_at_ms:
        raise ValueError("slot_time_unchanged")
    return {
        "step": "slot_rescheduled",
        "slot_id": slot.slot_id,
        "starts_at_ms": at,
        "previous_starts_at_ms": slot.starts_at_ms,
        "revision": slot.revision + 1,
        "reminders_at_ms": [ms for ms, _ in reminder_plan(replace(slot, starts_at_ms=at), now_ms=now_ms)],
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


def customer_booking(
    slots: dict[str, Slot], slot_id: str, *, customer_id: str, now_ms: int, is_member: bool = False
) -> Slot:
    """Donor bookings.get_customer_booking: own booked slot, only while its start is still future.

    Staff (active members) are not customers of their own business (customer_role_guard).
    """
    if is_member:
        raise ValueError("customer_role_required")
    slot = slots.get(slot_id)
    if slot is None or slot.status != "booked" or slot.customer_id != customer_id:
        raise ValueError("booking_not_found")
    if slot.starts_at_ms <= now_ms:
        raise ValueError("booking_already_started")
    return slot


def customer_businesses(
    slots_by_business: dict[str, dict[str, Slot]], *, customer_id: str, member_business_ids: set[str]
) -> list[str]:
    """Donor bookings.list_customer_businesses: businesses with this customer's bookings, minus staff ones."""
    return sorted(
        b
        for b, slots in slots_by_business.items()
        if b not in member_business_ids and any(s.customer_id == customer_id for s in slots.values())
    )


def reminder_plan(slot: Slot, *, now_ms: int) -> list[tuple[int, str]]:
    plan = [(slot.starts_at_ms - m * 60_000, label) for m, label in REMINDER_OFFSETS_MIN]
    return [(ms, label) for ms, label in plan if ms > now_ms]


def due_reminders(
    slots: dict[str, Slot], *, now_ms: int, sent: set[tuple[str, int, int]]
) -> list[tuple[Slot, int, str]]:
    """Due, undelivered reminders. Idempotency key (slot, offset, revision); only the closest offset is sent
    when several came due at once (late booking), the skipped earlier ones are implied."""
    out = []
    for slot in slots.values():
        if slot.status != "booked" or slot.starts_at_ms <= now_ms:
            continue
        ready = [
            (minutes, label)
            for minutes, label in REMINDER_OFFSETS_MIN
            if slot.starts_at_ms - minutes * 60_000 <= now_ms
        ]
        if not ready:
            continue
        minutes, label = min(ready)
        if not any((slot.slot_id, m, slot.revision) in sent for m, _ in ready if m <= minutes):
            out.append((slot, minutes, label))
    return out


def sent_reminders(payloads: list[dict[str, Any]]) -> set[tuple[str, int]]:
    return {
        (str(p.get("slot_id")), int(p.get("minutes") or 0), int(p.get("revision") or 0))
        for p in payloads
        if p.get("step") == "reminder_sent"
    }


def fmt(slot: Slot, tz: str = "Europe/Moscow") -> str:
    when = datetime.fromtimestamp(slot.starts_at_ms / 1000, ZoneInfo(tz)).strftime("%d.%m %H:%M")
    day = f" · день {slot.position}/{slot.session_count}" if slot.session_count > 1 else ""
    return f"{when} МСК · {slot.title} ({slot.duration_min} мин){day}"


__all__ = [
    "REMINDER_OFFSETS_MIN",
    "Slot",
    "book",
    "cancel",
    "due_reminders",
    "edit",
    "fmt",
    "parse_sessions",
    "parse_slot",
    "reminder_plan",
    "replay",
    "reschedule",
    "sent_reminders",
    "upcoming",
]
