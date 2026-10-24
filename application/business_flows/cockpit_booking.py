"""Owner cockpit "add free time" picker (donor native_member_interactions booking-open flow).

Pure: offering -> month -> date -> start time -> duration -> confirm. The final button turns
into exactly the ``slot_opened`` fact ``/add_slot`` writes (one parser: bookings.parse_slot).
Callbacks stay within ``cpm:action:arg:arg`` (<=40 chars per part).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from application.business_flows import bookings as bk

CANON_COCKPIT_BOOKING = True
TZ = ZoneInfo("Europe/Moscow")
MAX_MONTHS = 6  # donor MAX_CALENDAR_MONTHS
MONTH_PAGE = 4
TIME_PAGE = 8
START_TIMES = tuple(f"{h:02d}:{m:02d}" for h in range(8, 22) for m in (0, 30))  # donor BOOKING_START_TIMES
DURATIONS = {30: "30 минут", 60: "1 час", 90: "1,5 часа", 120: "2 часа", 180: "3 часа"}
MONTHS_RU = ("Январь Февраль Март Апрель Май Июнь Июль Август Сентябрь Октябрь Ноябрь Декабрь").split()
PARENTS = {
    "bk-open": "cpm:bookings:0",
    "bk-months": "cpm:bk-open",
    "bk-dates": "cpm:bk-open",
    "bk-times": "cpm:bk-open",
    "bk-dur": "cpm:bk-open",
}
MUTATIONS = frozenset({"bk-new"})

Rows = list[list[tuple[str, str]]]


def offerings(admin: Any) -> list[str]:
    """Donor _active_booking_offerings: priced services, else one generic format."""
    return sorted((getattr(admin, "prices", None) or {}).keys()) or ["Встреча"]


def _offering(admin: Any, raw: str) -> tuple[int, str]:
    items = offerings(admin)
    if not raw.isdigit() or int(raw) >= len(items):
        raise ValueError("unknown offering")
    return int(raw), items[int(raw)]


def _today(now_ms: int) -> date:
    return datetime.fromtimestamp(now_ms / 1000, TZ).date()


def _months(now_ms: int) -> list[tuple[int, int]]:
    d = _today(now_ms)
    y, m, out = d.year, d.month, []
    for _ in range(MAX_MONTHS + 1):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _date(raw: str, now_ms: int) -> date:
    """Donor parse_calendar_date: today .. +MAX_MONTHS, otherwise stale."""
    try:
        d = datetime.strptime(raw, "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError("bad date") from exc
    last_y, last_m = _months(now_ms)[-1]
    if d < _today(now_ms) or (d.year, d.month) > (last_y, last_m):
        raise ValueError("date outside window")
    return d


def _stamp(raw: str, now_ms: int) -> tuple[date, str]:
    if len(raw) != 12 or not raw.isdigit() or f"{raw[8:10]}:{raw[10:]}" not in START_TIMES:
        raise ValueError("bad time")
    return _date(raw[:8], now_ms), f"{raw[8:10]}:{raw[10:]}"


def _page(args: tuple[str, ...], i: int) -> int:
    raw = args[i] if len(args) > i else "0"
    if not raw.isdigit():
        raise ValueError("bad page")
    return int(raw)


def _nav(prev: str | None, nxt: str | None) -> Rows:
    row = ([("⬅️ Раньше", prev)] if prev else []) + ([("Позже ➡️", nxt)] if nxt else [])
    return [row] if row else []


def screen(action: str, args: tuple[str, ...], admin: Any, *, now_ms: int) -> tuple[str, Rows]:
    if action == "bk-open":
        items = offerings(admin)[:8]
        return "🕒 Добавить свободное время\n\nВыберите услугу.", [
            [(f"🕒 {t[:30]}", f"cpm:bk-months:{i}")] for i, t in enumerate(items)
        ]
    oi, title = _offering(admin, args[0] if args else "")
    if action == "bk-months":
        months, page = _months(now_ms), _page(args, 1)
        start = page * MONTH_PAGE
        if start >= len(months):
            raise ValueError("month page")
        rows = [
            [(f"{MONTHS_RU[m - 1]} {y}", f"cpm:bk-dates:{oi}:{y}{m:02d}")]
            for y, m in months[start : start + MONTH_PAGE]
        ]
        rows += _nav(
            f"cpm:bk-months:{oi}:{page - 1}" if page else None,
            f"cpm:bk-months:{oi}:{page + 1}" if start + MONTH_PAGE < len(months) else None,
        )
        return f"📅 {title}\n\nВыберите месяц.", rows
    if action == "bk-dates":
        raw = args[1] if len(args) > 1 else ""
        if len(raw) != 6 or not raw.isdigit() or (int(raw[:4]), int(raw[4:])) not in _months(now_ms):
            raise ValueError("bad month")
        y, m = int(raw[:4]), int(raw[4:])
        d, days = date(y, m, 1), []
        while d.month == m:
            if d >= _today(now_ms):
                days.append(d)
            d += timedelta(days=1)
        rows: Rows = [
            [(x.strftime("%d.%m"), f"cpm:bk-times:{oi}:{x:%Y%m%d}") for x in days[i : i + 4]]
            for i in range(0, len(days), 4)
        ]
        return f"📅 {title} · {MONTHS_RU[m - 1]} {y}\n\nВыберите дату.", rows
    if action == "bk-times":
        raw = args[1] if len(args) > 1 else ""
        d = _date(raw[:8], now_ms)
        page = int(raw[9:]) if raw[8:9] == "p" and raw[9:].isdigit() else 0
        start = page * TIME_PAGE
        if start >= len(START_TIMES):
            raise ValueError("time page")
        rows = [
            [(t, f"cpm:bk-dur:{oi}:{d:%Y%m%d}{t.replace(':', '')}") for t in START_TIMES[start + i : start + i + 4]]
            for i in range(0, TIME_PAGE, 4)
        ]
        rows += _nav(
            f"cpm:bk-times:{oi}:{d:%Y%m%d}p{page - 1}" if page else None,
            f"cpm:bk-times:{oi}:{d:%Y%m%d}p{page + 1}" if start + TIME_PAGE < len(START_TIMES) else None,
        )
        return f"🕒 {title} · {d:%d.%m.%Y}\n\nВыберите время начала (МСК).", [r for r in rows if r]
    if action == "bk-dur":
        raw = args[1] if len(args) > 1 else ""
        d, t = _stamp(raw, now_ms)
        return f"⏱ {d:%d.%m.%Y} {t} · {title}\n\nВыберите длительность.", [
            [(label, f"cpm:bk-new:{oi}-{raw}:{minutes}")] for minutes, label in DURATIONS.items()
        ]
    raise ValueError(action)


def mutation(args: tuple[str, ...], admin: Any, *, now_ms: int) -> dict[str, Any]:
    """Donor _booking_create_from_selection -> the /add_slot fact via bookings.parse_slot."""
    if len(args) != 2 or "-" not in args[0] or not args[1].isdigit() or int(args[1]) not in DURATIONS:
        raise ValueError("booking selection")
    raw_oi, raw = args[0].split("-", 1)
    _, title = _offering(admin, raw_oi)
    d, t = _stamp(raw, now_ms)
    return bk.parse_slot(f"{d:%Y-%m-%d} {t} {args[1]} {title}", now_ms=now_ms)


def result_text(change: dict[str, Any]) -> str:
    """Donor _booking_open_create_message confirmation."""
    slot = bk.Slot(change["slot_id"], change["title"], change["starts_at_ms"], change["duration_min"])
    return f"✅ Свободное время добавлено: {bk.fmt(slot)}"


__all__ = ["CANON_COCKPIT_BOOKING", "MUTATIONS", "PARENTS", "mutation", "offerings", "result_text", "screen"]
