"""Owner cockpit over business-flow projections (port of ClientPlatform native_member_interactions core).

Pure: parse a ``cpm:<screen>[:<page>]`` button, render ``(text, rows)`` from projection
snapshots, normalise navigation (parent Back + Home). Delivery is the executor's job.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

PREFIX = "cpm:"
PAGE_SIZE = 6
_ACTION = re.compile(r"[a-z][a-z0-9-]{0,40}")
HOME = ("🏠 Главное меню", "cpm:menu")

# screen -> parent screen (donor _NATIVE_PARENT_COMMANDS, limited to screens this port renders)
PARENTS: dict[str, str] = {
    "work": "cpm:menu",
    "today": "cpm:work",
    "bookings": "cpm:work",
    "growth": "cpm:menu",
    "partners": "cpm:growth",
    "ladder": "cpm:growth",
    "manage": "cpm:menu",
    "messengers": "cpm:manage",
}


@dataclass(frozen=True)
class Parsed:
    action: str
    args: tuple[str, ...] = ()


@dataclass(frozen=True)
class Snapshot:
    business: str = "Ваш бизнес"
    slots: list[Any] = field(default_factory=list)  # upcoming bookings.Slot
    partners: list[Any] = field(default_factory=list)  # partners.Partner (ranked or insertion order)
    steps: list[Any] = field(default_factory=list)  # ladder.Step
    bots: list[Any] = field(default_factory=list)  # bot_provisioning.Provisioning
    fmt_slot: Any = str


def recognizes(data: object) -> bool:
    return isinstance(data, str) and data.startswith(PREFIX)


def parse(data: object) -> Parsed:
    """``cpm:action[:arg...]``; anything malformed becomes the stale screen (never raises)."""
    if not recognizes(data):
        return Parsed("stale")
    parts = str(data)[len(PREFIX) :].split(":")
    if not _ACTION.fullmatch(parts[0]) or len(parts) > 3 or any(len(p) > 40 for p in parts):
        return Parsed("stale")
    return Parsed(parts[0], tuple(parts[1:]))


def page_number(args: tuple[str, ...], *, default: int = 0) -> int:
    if not args:
        return default
    if not args[0].isdigit() or int(args[0]) > 10000:
        raise ValueError("invalid page")
    return int(args[0])


def _rows(*buttons: tuple[str, str]) -> list[list[tuple[str, str]]]:
    return [[(label[:40], cmd)] for label, cmd in buttons]


def _paged(items: list[Any], page: int, screen: str, label) -> tuple[list[str], list[list[tuple[str, str]]], str]:
    count = max(1, -(-len(items) // PAGE_SIZE))
    if page >= count:
        raise ValueError("page outside result set")
    lines = [f"• {label(x)}" for x in items[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]]
    nav = []
    if page > 0:
        nav.append(("◀️ Назад", f"cpm:{screen}:{page - 1}"))
    if page + 1 < count:
        nav.append(("Вперёд ➡️", f"cpm:{screen}:{page + 1}"))
    return lines, ([nav] if nav else []), f"\n\nСтраница {page + 1}/{count}"


def render(parsed: Parsed, snap: Snapshot, *, is_owner: bool) -> tuple[str, list[list[tuple[str, str]]]]:
    if not is_owner:
        return "Для Вашей роли этот раздел недоступен.", []
    try:
        text, rows = _screen(parsed, snap)
    except ValueError:
        text, rows = "Эта кнопка уже неактуальна. Откройте нужный раздел заново.", []
    return text, with_navigation(rows, parsed)


def with_navigation(rows: list[list[tuple[str, str]]], parsed: Parsed) -> list[list[tuple[str, str]]]:
    """Every non-home screen gets a parent-level Back and, when different, Home."""
    if parsed.action == "menu":
        return rows
    parent = PARENTS.get(parsed.action, "cpm:menu")
    nav = [("⬅️ Назад", parent)] + ([HOME] if parent != HOME[1] else [])
    return [r for r in rows if r] + [nav]


def _screen(parsed: Parsed, s: Snapshot) -> tuple[str, list[list[tuple[str, str]]]]:
    a = parsed.action
    if a == "menu":
        return f"🏠 {s.business}\n\nВыберите раздел.", _rows(
            ("📋 Работа", "cpm:work"), ("📈 Рост", "cpm:growth"), ("⚙️ Управление", "cpm:manage")
        )
    if a == "work":
        return "📋 Работа\n\nСегодняшняя сводка и запись клиентов.", _rows(
            ("📊 Что сегодня", "cpm:today"), ("📅 Запись", "cpm:bookings:0")
        )
    if a == "today":
        booked = [x for x in s.slots if x.status == "booked"]
        nearest = f"\nБлижайшая встреча: {s.fmt_slot(booked[0])}" if booked else ""
        return (
            "📊 Что сегодня происходит\n\n"
            f"Слоты впереди: {len(s.slots)} (занято {len(booked)}){nearest}\n"
            f"Партнёров: {len(s.partners)}\nСтупеней лестницы: {len(s.steps)}"
        ), _rows(("📅 Запись", "cpm:bookings:0"))
    if a == "bookings":
        if not s.slots:
            return "📅 Запись\n\nОткрытого времени нет. Добавьте слот: /add_slot", []
        lines, nav, foot = _paged(s.slots, page_number(parsed.args), "bookings", s.fmt_slot)
        return "📅 Запись\n\n" + "\n".join(lines) + foot, nav
    if a == "growth":
        return "📈 Рост\n\nПартнёры и лестница предложений.", _rows(
            ("🤝 Партнёры", "cpm:partners:0"), ("🪜 Лестница предложений", "cpm:ladder")
        )
    if a == "partners":
        if not s.partners:
            return "🤝 Партнёры\n\nБаза пуста. Добавьте: /partner_add", []
        lines, nav, foot = _paged(s.partners, page_number(parsed.args), "partners", lambda p: p.name)
        return "🤝 Партнёры\n\n" + "\n".join(lines) + foot, nav
    if a == "ladder":
        body = "\n".join(f"{i}. {x.title}" for i, x in enumerate(s.steps, 1)) or "Ступеней нет. Добавьте: /ladder_add"
        return "🪜 Лестница предложений\n\n" + body, []
    if a == "manage":
        return "⚙️ Управление", _rows(("💬 Мессенджеры", "cpm:messengers"))
    if a == "messengers":
        body = (
            "\n".join(f"• @{b.username} — {b.status}" for b in s.bots) or "Бот не подключён. Подключить: /connect_bot"
        )
        return "💬 Мессенджеры\n\n" + body, []
    raise ValueError(a)


def markup(rows: list[list[tuple[str, str]]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return {"inline_keyboard": [[{"text": t, "callback_data": c} for t, c in row] for row in rows]}
