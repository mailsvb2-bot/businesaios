"""Native event wizard: guided button flow that opens a bookable event slot.

Port of clientplatform ``native_event_wizard``. The wizard is stateless between
taps: every step's choices travel in compact callback data
``cpe:<YYYYMMDD>:<HHMM>:<minutes>:<warmup>:<mode>:<days>`` (well under Telegram's 64-byte limit);
only the title draft is a fact (``event_series@v1`` ``wizard_draft``). The final
tap reuses ``bookings.parse_slot`` and ``event_series.parse_warmup_days`` - the
wizard has no slot or warm-up logic of its own.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from application.business_flows import bookings as bk
from application.business_flows import event_series as es

PREFIX = "cpe:"
DATE_DAYS = 14
TIMES = ("1000", "1200", "1500", "1800", "1900", "2000")
DURATIONS = ("30", "60", "90", "120")
WARMUPS = {"0": (), "1": (1,), "31": (3, 1), "731": (7, 3, 1)}
MODES = {"on": "онлайн", "off": "офлайн"}
DAY_COUNTS = ("1", "2", "3", "5")
MAX_EVENT_SESSIONS = 31
MOSCOW_TIMEZONE = "Europe/Moscow"
MAX_PLACE = 300
WEEKDAYS = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")
Rows = list[list[tuple[str, str]]]


def draft(user_id: str, title: str) -> dict[str, Any]:
    value = " ".join(str(title or "").split())[:120]
    if not value:
        raise ValueError("wizard_title: /new_event Название встречи")
    return {"step": "wizard_draft", "user_id": user_id, "title": value}


def draft_title(payloads: list[dict[str, Any]], user_id: str) -> str:
    title = ""
    for p in payloads:
        if p.get("step") == "wizard_draft" and p.get("user_id") == user_id:
            title = str(p.get("title") or "")
        elif p.get("step") == "wizard_done" and p.get("user_id") == user_id:
            title = ""
    return title


def _parse(data: str) -> list[str]:
    if not data.startswith(PREFIX):
        return []
    parts = data[len(PREFIX) :].split(":")
    return [p for p in parts if p][:6]


def step(title: str, data: str, *, now_ms: int, tz: str = "Europe/Moscow") -> tuple[str, Rows, dict[str, Any] | None]:
    """Return (text, keyboard rows, finished-result or None) for the current tap."""
    if not title:
        raise ValueError("wizard_no_draft: начните с /new_event Название")
    parts = _parse(data)
    back = [("⬅️ Назад", PREFIX + ":".join(parts[:-1]))] if parts else []
    head = f"🧭 Новая встреча «{title}»\n"
    if not parts:
        today = datetime.fromtimestamp(now_ms / 1000, ZoneInfo(tz)).date()
        days = [today + timedelta(days=i) for i in range(1, DATE_DAYS + 1)]
        btns = [(f"{WEEKDAYS[d.weekday()]} {d:%d.%m}", f"{PREFIX}{d:%Y%m%d}") for d in days]
        return head + "Шаг 1/6 — дата:", [btns[i : i + 4] for i in range(0, len(btns), 4)], None
    if len(parts) == 1:
        return head + "Шаг 2/6 — время (МСК):", [[(f"{t[:2]}:{t[2:]}", f"{data}:{t}") for t in TIMES], back], None
    if len(parts) == 2:
        return head + "Шаг 3/6 — длительность:", [[(f"{m} мин", f"{data}:{m}") for m in DURATIONS], back], None
    if len(parts) == 3:
        labels = {"0": "без прогрева", "1": "за 1 день", "31": "за 3 и 1 день", "731": "за 7, 3, 1"}
        return head + "Шаг 4/6 — прогрев:", [[(labels[k], f"{data}:{k}") for k in WARMUPS], back], None
    if len(parts) == 4:
        return (
            head + "Шаг 5/6 — формат:",
            [[(f"💻 {MODES['on']}", f"{data}:on"), (f"📍 {MODES['off']}", f"{data}:off")], back],
            None,
        )
    if len(parts) == 5:
        return head + "Шаг 6/6 — сколько дней подряд:", [[(f"{n} дн.", f"{data}:{n}") for n in DAY_COUNTS], back], None
    d, t, m, w, mode, n = parts[:6]
    if (
        t not in TIMES
        or m not in DURATIONS
        or w not in WARMUPS
        or mode not in MODES
        or n not in DAY_COUNTS
        or len(d) != 8
    ):
        raise ValueError("wizard_choice_invalid")
    first = datetime.strptime(d, "%Y%m%d")
    slots, prev = [], None
    for i in range(parse_session_count(n)):
        day = first + timedelta(days=i)
        slot = bk.parse_slot(f"{day:%Y-%m-%d} {t[:2]}:{t[2:]} {m} {title}", now_ms=now_ms, tz=tz)
        prev = validate_session_sequence(slot, previous=prev)
        slots.append(slot)
    warm = es.parse_warmup_days(",".join(map(str, WARMUPS[w]))) if WARMUPS[w] else None
    return "", [], {"slot": slots[0], "slots": slots, "warmup": warm, "mode": mode_fact(title, mode)}


def parse_session_count(value: object) -> int:
    """Donor parse_session_count (1..31, Russian forms)."""
    raw = " ".join(str(value or "").strip().casefold().split())
    raw = {"один": "1", "один день": "1", "два": "2", "два дня": "2"}.get(raw, raw)
    for suffix in (" дней", " дня", " день", " дн."):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)].strip()
            break
    if not raw.isdigit() or not 1 <= int(raw) <= MAX_EVENT_SESSIONS:
        raise ValueError(f"session_count: 1..{MAX_EVENT_SESSIONS}")
    return int(raw)


def normalize_event_timezone(value: object) -> str:
    """Donor normalize_event_timezone: Moscow aliases or a valid IANA zone."""
    raw = " ".join(str(value or "").strip().split())
    if raw.casefold() in {
        "москва",
        "московское",
        "московское время",
        "мск",
        "msk",
        "moscow",
        MOSCOW_TIMEZONE.casefold(),
    }:
        return MOSCOW_TIMEZONE
    if not raw or len(raw) > 80:
        raise ValueError("timezone_invalid")
    try:
        ZoneInfo(raw)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("timezone_invalid") from exc
    return raw


def validate_session_sequence(slot: dict[str, Any], *, previous: dict[str, Any] | None) -> dict[str, Any]:
    """Donor validate_session_sequence: sessions are chronological and never overlap."""
    if previous is not None and slot["starts_at_ms"] < previous["starts_at_ms"] + previous["duration_min"] * 60_000:
        raise ValueError("sessions_overlap")
    return slot


def normalize_session_join_url(value: object, *, existing_urls: tuple[str, ...] = ()) -> str | None:
    """Donor normalize_session_join_url: HTTPS only, one room per session, '-'/'позже' = not yet."""
    raw = str(value or "").strip()
    if raw.casefold() in {"", "-", "позже"}:
        return None
    if not raw.startswith("https://") or any(c.isspace() for c in raw) or len(raw) > MAX_PLACE:
        raise ValueError("join_url: только https://")
    if raw in set(existing_urls):
        raise ValueError("join_url_duplicate")
    return raw


def _key(title: str) -> str:
    k = " ".join(str(title or "").split()).casefold()[:120]
    if not k:
        raise ValueError("event_title_missing")
    return k


def mode_fact(title: str, mode: str) -> dict[str, Any]:
    if mode not in MODES:
        raise ValueError("event_mode: on | off")
    return {"step": "event_mode", "key": _key(title), "mode": mode}


def place_fact(title: str, value: str, *, mode: str) -> dict[str, Any]:
    """Donor _accept_room / _venue_message: online → HTTPS room link, offline → venue address."""
    if mode == "on":
        url = normalize_session_join_url(value)
        if url is None:
            raise ValueError("join_url: только https://")
        return {"step": "event_place", "key": _key(title), "mode": mode, "place": url}
    text = " ".join(str(value or "").replace("\x00", " ").split())[:MAX_PLACE]
    if len(text) < 3 or "://" in text:
        raise ValueError("venue: укажите адрес текстом")
    return {"step": "event_place", "key": _key(title), "mode": "off", "place": text}


def places(payloads: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for p in payloads:
        if p.get("step") == "event_mode":
            out.setdefault(str(p["key"]), {})["mode"] = str(p["mode"])
        elif p.get("step") == "event_place":
            out.setdefault(str(p["key"]), {}).update(mode=str(p["mode"]), place=str(p["place"]))
    return out


__all__ = [
    "PREFIX",
    "draft",
    "draft_title",
    "mode_fact",
    "normalize_event_timezone",
    "normalize_session_join_url",
    "parse_session_count",
    "place_fact",
    "places",
    "step",
    "validate_session_sequence",
]
