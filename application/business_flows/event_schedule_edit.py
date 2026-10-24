"""Owner edits a whole event series schedule (donor native_member_interactions
``_event_edit_message`` / ``_event_edit_result``).

Pure: one line per session ``ДД.ММ.ГГГГ ЧЧ:ММ-ЧЧ:ММ``; counts must match, sessions must stay
chronological and never overlap (event_wizard.validate_session_sequence). Rooms/titles are kept;
each moved session gets a new revision so unsent reminders are recomputed. Nothing is changed
unless every line is valid. The caller appends the single ``series_rescheduled`` fact.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from application.business_flows import bookings as bk
from application.business_flows.event_wizard import validate_session_sequence

_LINE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})\s+(\d{1,2}):(\d{2})\s*[-–—]\s*(\d{1,2}):(\d{2})$")
FORMAT = "ДД.ММ.ГГГГ ЧЧ:ММ-ЧЧ:ММ"


def _plural(n: int) -> str:
    return "строку" if n == 1 else "строки" if n in {2, 3, 4} else "строк"


def parse_window(line: str, *, tz: str) -> tuple[int, int]:
    m = _LINE.fullmatch(" ".join(str(line or "").split()))
    if m is None:
        raise ValueError("session_window_format")
    d, mo, y, h1, m1, h2, m2 = (int(x) for x in m.groups())
    try:
        start = datetime(y, mo, d, h1, m1, tzinfo=ZoneInfo(tz))
        end = datetime(y, mo, d, h2, m2, tzinfo=ZoneInfo(tz))
    except ValueError as exc:
        raise ValueError("session_window_format") from exc
    if end <= start:
        raise ValueError("session_end_before_start")
    return int(start.timestamp() * 1000), int((end - start).total_seconds() // 60)


def _window(s: bk.Slot, tz: str) -> str:
    zone = ZoneInfo(tz)
    start = datetime.fromtimestamp(s.starts_at_ms / 1000, zone)
    end = datetime.fromtimestamp((s.starts_at_ms + s.duration_min * 60_000) / 1000, zone)
    return f"{start:%d.%m.%Y %H:%M}-{end:%H:%M}"


def edit_message(series: list[bk.Slot], *, tz: str = "Europe/Moscow") -> str:
    live = [s for s in series if s.status != "closed"]
    if not live:
        return "Это событие больше недоступно."
    n = len(live)
    return (
        "🕒 Изменить расписание вебинара\n\n"
        f"Эфиров: {n}. Пришлите ровно {n} {_plural(n)} — по одной на каждый эфир.\n"
        f"Формат: {FORMAT}\n\nТекущее расписание:\n" + "\n".join(_window(s, tz) for s in live)
        + "\n\nКомнаты и площадки сохранятся. Напоминания клиентам будут пересчитаны автоматически."
    )  # fmt: skip


def edit_result(series: list[bk.Slot], raw: str, *, now_ms: int, tz: str = "Europe/Moscow"):
    """-> (text, change | None, moved [(old, new)]) ; change is None when nothing was applied."""
    live = [s for s in series if s.status != "closed"]
    if not live:
        return "Это событие больше недоступно.", None, []
    lines = [x.strip() for x in str(raw or "").splitlines() if x.strip()]
    if len(lines) != len(live):
        return (f"Нужно {len(live)} {_plural(len(live))} — по одной на каждый эфир. "
                "Ничего не изменено. Пришлите расписание ещё раз."), None, []  # fmt: skip
    changes: list[dict[str, Any]] = []
    moved: list[tuple[bk.Slot, bk.Slot]] = []
    prev = None
    try:
        for pos, (line, cur) in enumerate(zip(lines, live, strict=True), start=1):
            at, minutes = parse_window(line, tz=tz)
            if at <= now_ms:
                raise ValueError(f"эфир {pos} в прошлом")
            if not 5 <= minutes <= bk.MAX_DURATION_MIN:
                raise ValueError(f"эфир {pos}: длительность")
            prev = validate_session_sequence({"starts_at_ms": at, "duration_min": minutes}, previous=prev)
            if minutes != cur.duration_min:
                changes.append({"step": "slot_edited", "slot_id": cur.slot_id, "title": "", "duration_min": minutes})
            if at != cur.starts_at_ms:
                new = replace(cur, starts_at_ms=at, duration_min=minutes, revision=cur.revision + 1)
                changes.append({
                    "step": "slot_rescheduled", "slot_id": cur.slot_id, "starts_at_ms": at,
                    "previous_starts_at_ms": cur.starts_at_ms, "revision": new.revision,
                    "reminders_at_ms": [ms for ms, _ in bk.reminder_plan(new, now_ms=now_ms)],
                })  # fmt: skip
                moved.append((cur, new))
    except ValueError as exc:
        return f"Строка не распознана ({exc}). Формат: {FORMAT}. Ничего не изменено.", None, []
    if not changes:
        return "Расписание не изменилось.", None, []
    text = f"✅ Расписание обновлено: {len(changes)} изм." + ("\nНапоминания пересчитаны." if moved else "")
    return text, {"step": "series_rescheduled", "series_id": live[0].series_id, "changes": changes}, moved


__all__ = ["FORMAT", "edit_message", "edit_result", "parse_window"]
