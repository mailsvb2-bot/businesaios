"""Native event wizard: guided button flow that opens a bookable event slot.

Port of clientplatform ``native_event_wizard``. The wizard is stateless between
taps: every step's choices travel in compact callback data
``cpe:<YYYYMMDD>:<HHMM>:<minutes>:<warmup>`` (well under Telegram's 64-byte limit);
only the title draft is a fact (``event_series@v1`` ``wizard_draft``). The final
tap reuses ``bookings.parse_slot`` and ``event_series.parse_warmup_days`` - the
wizard has no slot or warm-up logic of its own.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from application.business_flows import bookings as bk
from application.business_flows import event_series as es

PREFIX = "cpe:"
DATE_DAYS = 14
TIMES = ("1000", "1200", "1500", "1800", "1900", "2000")
DURATIONS = ("30", "60", "90", "120")
WARMUPS = {"0": (), "1": (1,), "31": (3, 1), "731": (7, 3, 1)}
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
    return [p for p in parts if p][:5]


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
        return head + "Шаг 1/4 — дата:", [btns[i : i + 4] for i in range(0, len(btns), 4)], None
    if len(parts) == 1:
        return head + "Шаг 2/4 — время (МСК):", [[(f"{t[:2]}:{t[2:]}", f"{data}:{t}") for t in TIMES], back], None
    if len(parts) == 2:
        return head + "Шаг 3/4 — длительность:", [[(f"{m} мин", f"{data}:{m}") for m in DURATIONS], back], None
    if len(parts) == 3:
        labels = {"0": "без прогрева", "1": "за 1 день", "31": "за 3 и 1 день", "731": "за 7, 3, 1"}
        return head + "Шаг 4/4 — прогрев:", [[(labels[k], f"{data}:{k}") for k in WARMUPS], back], None
    d, t, m, w = parts[:4]
    if t not in TIMES or m not in DURATIONS or w not in WARMUPS or len(d) != 8:
        raise ValueError("wizard_choice_invalid")
    slot = bk.parse_slot(f"{d[:4]}-{d[4:6]}-{d[6:]} {t[:2]}:{t[2:]} {m} {title}", now_ms=now_ms, tz=tz)
    warm = es.parse_warmup_days(",".join(map(str, WARMUPS[w]))) if WARMUPS[w] else None
    return "", [], {"slot": slot, "warmup": warm}


__all__ = ["PREFIX", "draft", "draft_title", "step"]
