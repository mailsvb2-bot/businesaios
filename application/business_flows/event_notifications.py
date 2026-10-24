"""Event notification copy and reschedule notice (donor ``application/event_notifications``).

Pure rendering only. Delivery stays with the bookings handler: reminders are derived from
``bookings@v1`` facts (``bookings.due_reminders``) and each delivery records its own idempotent
``reminder_sent`` fact keyed (slot, offset, revision) - the replacement for the donor outbox keys.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from application.business_flows.bookings import REMINDER_KIND, Slot

KINDS = ("registration_confirmed", "24h", "3h", "15m")


def local_label(slot: Slot, tz: str = "Europe/Moscow") -> str:
    """Donor ``_session_local_start_label``: dd.mm.YYYY HH:MM in the business timezone."""
    return datetime.fromtimestamp(slot.starts_at_ms / 1000, ZoneInfo(tz)).strftime("%d.%m.%Y %H:%M")


def render(kind: str, slot: Slot, *, name: str = "", tz: str = "Europe/Moscow") -> tuple[str, str]:
    """(subject, body) per donor ``_render``; the personal join URL becomes the /my_bookings command."""
    who = name.strip() or "Здравствуйте"
    when = local_label(slot, tz)
    join = "Ваши записи: /my_bookings"
    if kind == "registration_confirmed":
        return (
            f"Вы зарегистрированы: {slot.title}",
            f"{who}, регистрация подтверждена.\n\n{slot.title}\n{when}\n\n{join}",
        )
    day = f"День {slot.position} из {slot.session_count}.\n" if slot.session_count > 1 else ""
    if kind == "24h":
        return f"Скоро: {slot.title}", f"{who}, напоминаем о мероприятии.\n\n{slot.title}\n{day}{when}\n\n{join}"
    if kind == "3h":
        return f"Через 3 часа: {slot.title}", f"{who}, {day.lower()}начинаем примерно через 3 часа.\n\n{join}"
    if kind == "15m":
        return f"Через 15 минут: {slot.title}", f"{who}, {day.lower()}начинаем примерно через 15 минут.\n\n{join}"
    raise ValueError("unsupported event notification kind")


def reminder_text(slot: Slot, minutes: int, *, name: str = "", tz: str = "Europe/Moscow") -> str:
    subject, body = render(REMINDER_KIND[minutes], slot, name=name, tz=tz)
    return f"⏰ {subject}\n{body}"


def rescheduled_text(slot: Slot, previous_ms: int, tz: str = "Europe/Moscow") -> str:
    old = datetime.fromtimestamp(previous_ms / 1000, ZoneInfo(tz)).strftime("%d.%m.%Y %H:%M")
    return (
        f"🔁 Время изменено: {slot.title}\nБыло: {old}\nСтало: {local_label(slot, tz)}\n\n"
        "Напоминания перенесены на новое время. Отменить: /my_bookings"
    )


__all__ = ["KINDS", "local_label", "reminder_text", "render", "rescheduled_text"]
