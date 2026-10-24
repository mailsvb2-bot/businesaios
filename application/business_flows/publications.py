"""Owner content calendar: publication drafts, scheduling, publish marks, retirement.

Ported from clientplatform ``admin_ops`` publications onto ``business_admin@v1`` facts.
Nothing here posts anywhere: the owner publishes in his channel himself and marks the
post as published (the donor also only flipped a status). A draft's id is a stable
hash of channel+title+body, so repeating the same command never duplicates it.
Retirement keeps history (the donor never erases delivery state).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from application.business_flows.projection import stable_id

CHANNELS = {"telegram": "Telegram", "vk": "ВКонтакте", "max": "MAX", "other": "Другой канал"}
STATUS = {
    "draft": ("📝", "Черновик"),
    "scheduled": ("🗓", "Запланирована"),
    "published": ("✅", "Опубликована"),
    "retired": ("🗄", "В архиве"),
}
MAX_TITLE, MAX_BODY = 180, 4000


@dataclass
class Publication:
    pub_id: str
    channel: str
    title: str
    body: str
    created_ms: int
    status: str = "draft"
    scheduled_ms: int | None = None
    published_ms: int | None = None

    @property
    def effective_ms(self) -> int:
        return self.published_ms or self.scheduled_ms or self.created_ms


def replay(payloads: list[dict[str, Any]]) -> dict[str, Publication]:
    out: dict[str, Publication] = {}
    for p in payloads:
        step, pid = p.get("step"), str(p.get("pub_id") or "")
        if step == "pub_draft" and pid not in out:
            out[pid] = Publication(pid, p["channel"], p["title"], p["body"], int(p["at_ms"]))
            continue
        pub = out.get(pid)
        if pub is None or pub.status == "retired":
            continue
        if step == "pub_scheduled":
            pub.status, pub.scheduled_ms = "scheduled", int(p["at_ms"])
        elif step == "pub_unscheduled":
            pub.status, pub.scheduled_ms = "draft", None
        elif step == "pub_published":
            pub.status, pub.published_ms = "published", int(p["at_ms"])
        elif step == "pub_retired":
            pub.status = "retired"
    return out


def ordered(pubs: dict[str, Publication]) -> list[Publication]:
    return sorted(pubs.values(), key=lambda x: (x.status == "retired", x.effective_ms))


def draft(pubs: dict[str, Publication], arg: str, *, now_ms: int) -> dict[str, Any] | None:
    """``[канал] Заголовок | текст``; None when that exact draft already exists."""
    head, sep, body = str(arg or "").partition("|")
    words = head.split()
    channel = words[0].casefold() if words and words[0].casefold() in CHANNELS else "telegram"
    title = " ".join(words[1:] if words and words[0].casefold() in CHANNELS else words)
    body = body.strip()
    if not sep or not title or not body or len(title) > MAX_TITLE or len(body) > MAX_BODY:
        raise ValueError("post_format: /post_add [telegram|vk|max|other] Заголовок | текст")
    pid = stable_id("pub", channel, title, body)
    if pid in pubs:
        return None
    return {"step": "pub_draft", "pub_id": pid, "channel": channel, "title": title, "body": body, "at_ms": now_ms}


def _pick(pubs: dict[str, Publication], n: str, allowed: set[str]) -> Publication:
    items = ordered(pubs)
    if not n.isdigit() or not 0 < int(n) <= len(items):
        raise ValueError("post_number_invalid: номер из /posts")
    pub = items[int(n) - 1]
    if pub.status not in allowed:
        raise ValueError(f"post_status_{pub.status}")
    return pub


def schedule(pubs: dict[str, Publication], arg: str, *, now_ms: int, tz: str = "Europe/Moscow") -> dict[str, Any]:
    """Donor schedule_publication: business-local ``N YYYY-MM-DD HH:MM``, future only."""
    parts = str(arg or "").split()
    if len(parts) != 3:
        raise ValueError("post_schedule_format: /post_schedule N 2026-11-01 10:00")
    pub = _pick(pubs, parts[0], {"draft", "scheduled"})
    try:
        at = datetime.strptime(f"{parts[1]} {parts[2]}", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(tz))
    except ValueError as exc:
        raise ValueError("post_datetime_invalid") from exc
    at_ms = int(at.timestamp() * 1000)
    if at_ms <= now_ms:
        raise ValueError("post_in_past")
    return {"step": "pub_scheduled", "pub_id": pub.pub_id, "at_ms": at_ms}


def transition(pubs: dict[str, Publication], verb: str, n: str, *, now_ms: int) -> dict[str, Any] | None:
    allowed = {
        "unschedule": ({"scheduled"}, "pub_unscheduled"),
        "publish": ({"draft", "scheduled"}, "pub_published"),
        "retire": ({"draft", "scheduled", "published", "retired"}, "pub_retired"),
    }[verb]
    pub = _pick(pubs, str(n or "").strip(), allowed[0])
    if pub.status == "retired":
        return None  # retiring twice is a no-op
    return {"step": allowed[1], "pub_id": pub.pub_id, "at_ms": now_ms}


def due(pubs: dict[str, Publication], *, now_ms: int) -> list[Publication]:
    """Scheduled posts whose time has come (the owner is reminded to publish them)."""
    return [p for p in ordered(pubs) if p.status == "scheduled" and (p.scheduled_ms or 0) <= now_ms]


def fmt_ts(ms: int, tz: str = "Europe/Moscow") -> str:
    return datetime.fromtimestamp(ms / 1000, ZoneInfo(tz)).strftime("%d.%m %H:%M")


def calendar_lines(pubs: dict[str, Publication], *, tz: str = "Europe/Moscow", max_entries: int = 20) -> list[str]:
    """Donor format_publication_calendar_lines."""
    items = ordered(pubs)[:max_entries]
    if not items:
        return ["• Публикаций пока нет."]
    rows = []
    for i, p in enumerate(items, 1):
        icon, label = STATUS[p.status]
        title = p.title if len(p.title) <= 48 else p.title[:47].rstrip() + "…"
        rows.append(f"{i}. {icon} {fmt_ts(p.effective_ms, tz)} · {CHANNELS[p.channel]} · {label} · {title}")
    return rows


__all__ = ["Publication", "calendar_lines", "draft", "due", "ordered", "replay", "schedule", "transition"]
