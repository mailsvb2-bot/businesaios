"""Customer chronology for the owner (partial port of ClientPlatform customer_timeline).

Pure. Only facts this port records carry a time: booked slots (their start) and the
attendance mark on them. Payments, attribution and external observations are not
customer-linked in the business-flow facts, so they are not invented here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

CANON_CUSTOMER_TIMELINE = True
MSK = timezone(timedelta(hours=3))
_ATT = {"attended": "пришёл", "no_show": "не пришёл"}


@dataclass(frozen=True)
class Entry:
    at_ms: int
    kind: str
    title: str
    detail: str = ""

    def __post_init__(self) -> None:  # donor CustomerTimelineEntry invariants
        if not self.kind or not self.title or self.at_ms < 0:
            raise ValueError("timeline entry needs kind, title and a non-negative time")


def build(customer_id: str, slots: list[Any], series: Any, *, now_ms: int) -> list[Entry]:
    att = getattr(series, "attendance", {}) or {}
    out: list[Entry] = []
    for x in slots:
        if x.customer_id != customer_id:
            continue
        title = getattr(x, "title", "") or "Встреча"
        out.append(Entry(x.starts_at_ms, "booking", "Запись", title[:120]))
        mark = att.get((x.slot_id, customer_id))
        if mark in _ATT:
            out.append(Entry(x.starts_at_ms + 1, f"attendance:{mark}", "Посещение", _ATT[mark]))
        elif x.starts_at_ms <= now_ms and x.status == "booked":
            out.append(Entry(x.starts_at_ms + 1, "attendance:unknown", "Посещение", "не отмечено"))
    return sorted(out, key=lambda e: (e.at_ms, e.kind))


def format_lines(entries: list[Entry], *, max_entries: int = 8) -> tuple[str, ...]:
    """Donor format_customer_timeline_lines: newest tail, hidden-count notice, dd.mm.yyyy dates (МСК)."""
    if isinstance(max_entries, bool) or not isinstance(max_entries, int) or max_entries < 1:
        raise ValueError("max_entries must be a positive integer")
    selected = entries[-max_entries:]
    lines = [f"• Показаны последние {len(selected)} из {len(entries)} событий"] if len(entries) > len(selected) else []
    for e in selected:
        day = datetime.fromtimestamp(e.at_ms / 1000, MSK).strftime("%d.%m.%Y")
        lines.append(f"• {day} · {e.title}" + (f" — {e.detail}" if e.detail else ""))
    return tuple(lines)


__all__ = ["CANON_CUSTOMER_TIMELINE", "Entry", "build", "format_lines"]
